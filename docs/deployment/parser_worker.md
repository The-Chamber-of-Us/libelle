# Parser worker on staging / Raspberry Pi (#368)

The API and worker are independent systemd services. The API enqueues durable
`parser_jobs`; the worker polls that Sheet without an HTTP listener. Restarting
one service does not restart the other. Use one active worker per environment.

## Release prerequisite

The release candidate must include #363–#367, in particular
`backend/services/parser_worker.py` from #365 and its storage/schema changes.
#365 is included in `origin/main` at `329b9d3` and has been merged into this
branch. This configuration uses that implementation. Do not enable the service
on an older release without it: the launcher exits with
`startup_or_runtime_failed` and systemd retries.

The launcher calls the existing `ParserWorker.run_once()` with the existing
configuration defaults. It does not change claims, retries, leases, reconciliation,
Resolver execution, or authoritative-result selection. Reconciliation is a separate
one-shot maintenance operation; no reconciliation timer is installed.

## Configuration and isolation

Use the existing staging checkout `/opt/libelle-v03-staging`, its
`backend/.venv`, service account `tcus-admin`, and protected environment file
`/etc/libelle/libelle-v03-staging.env`. These historical v03 path names also apply
to the v0.4 candidate; they do not select a schema or environment automatically.
The backend `.env` symlink should point to this same file. Systemd loads it before
Python starts; backend dotenv loading does not override exported values.

Keep the environment file root-owned, group `tcus-admin`, and mode 0640. Both
systemd and backend dotenv loading must be able to read it: a root-only 0600
file behind the backend `.env` symlink causes startup to fail even when systemd
has already exported the variables. Keep secret files outside the checkout,
readable only by the service user/root. The OAuth token
must be writable by the service user because Google refreshes it. Do not print
secret files or `systemctl show ... -p Environment` in release evidence.

| Existing variable | Requirement / default |
| --- | --- |
| `GOOGLE_SHEET_ID` | Required: isolated staging Sheet, including canonical `parser_jobs` headers from `backend/sheet_schema.py`. |
| `GOOGLE_CREDENTIALS` | Service-account JSON path; default `org_credentials.json`. Use an absolute staging-only path. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Optional inline service-account JSON, takes precedence over `GOOGLE_CREDENTIALS`; prefer a protected file. |
| `TOKEN_FILE` | Drive user OAuth token; default `token.json`. Use an absolute staging-only writable path with a valid refresh token. |
| `GOOGLE_OAUTH_CLIENT` | OAuth client file; default `org_oauth_client.json`. Needed for API authorization/bootstrap, not ordinary worker polling. |
| `DRIVE_ROOT_FOLDER_ID` | Staging upload folder used by the API. It is **not** a download access boundary: the worker downloads the file referenced by the queued row. |
| `PARSER_WORKER_ID` | Optional; default `hostname:pid`, stable during a process lifetime and stored in `locked_by`. Leave unset to distinguish restarts. If supplied, use only an operational identifier, never PII or secrets. |
| `PARSER_WORKER_POLL_INTERVAL_SECONDS` | Default 5; finite positive seconds. |
| `PARSER_WORKER_LEASE_SECONDS` | Default 900; positive integer seconds. Select a lease longer than normal attempt duration using #365 guidance. |

There is no environment-selector variable or retry environment override. Existing
job rows control `max_attempts` (repository default 3); #365 uses retry delays of
60 seconds after the first failure and 300 seconds subsequently. Restarting the
service must never reset attempts or edit lease timestamps.

Before starting, privately compare the Sheet and folder with the approved staging
inventory, verify the `parser_jobs` schema, and confirm both Sheet service-account
access and Drive OAuth identity. Use a dedicated staging OAuth identity with no
live volunteer access, and confirm existing queued rows reference staging files.
A staging folder value alone cannot prevent reads of production file references.
Record isolation PASS/FAIL without copying credentials or Drive IDs into reports.

## Install on the designated single worker host

Follow [staging deployment](staging_deployment.md) to deploy the reviewed release
candidate and install backend requirements in `backend/.venv`. Stop the worker
before updating its checkout or virtual environment. Record `git rev-parse HEAD`.
Confirm the release includes the dependency files before proceeding:

```bash
cd /opt/libelle-v03-staging
test -f backend/services/parser_worker.py
test -f backend/parser_worker.py
git rev-parse HEAD
```

Inventory **all** hosts that can access this Sheet, including developer shells,
cron, containers, and other service managers. Stop/disable every old worker before
enabling this host. Never run `python parser_worker.py` alongside the service.
The non-template installed unit has one instance; do not create `@` instances or
replicas. The launcher also holds an exclusive nonblocking lock at
`/var/lib/libelle-parser-worker/worker.lock` before importing the worker. Copies of
this launcher on the same host share the lock. Never delete that lock file while
any launcher is running. The lock is local and advisory: it cannot protect against
a raw worker command or a second host. There is no distributed locking guarantee.

The checked-in unit targets the existing staging paths. If your Pi uses different
paths/user, edit the installed copy consistently; keep the same lock directory.
Do not point another installation at the same Sheet. This conservative host lock
also prevents two service launchers for different environments on one host.

```bash
sudo install -m 0644 infrastructure/systemd/libelle-parser-worker.service.template /etc/systemd/system/libelle-parser-worker.service
sudo systemd-analyze verify /etc/systemd/system/libelle-parser-worker.service
sudo systemctl daemon-reload
sudo systemctl enable libelle-v03-backend.service
sudo systemctl enable libelle-parser-worker.service
sudo systemctl restart libelle-v03-backend.service
sudo systemctl restart libelle-parser-worker.service
sudo systemctl is-enabled libelle-parser-worker.service
sudo systemctl status libelle-parser-worker.service --no-pager
```

Systemd creates the private persistent lock directory. Network-online ordering
avoids local boot races, but does not prove Google is reachable. The worker has no
API health dependency. `Restart=always`, a five-second delay, and disabled start
rate limiting keep retrying after failure; explicit `systemctl stop` remains stopped.
SIGTERM requests exit after the current attempt; after 60 seconds systemd kills the
service control group. An interrupted attempt remains durable until lease recovery.

## Operations and diagnosis

```bash
sudo systemctl restart libelle-v03-backend.service
sudo systemctl restart libelle-parser-worker.service
sudo systemctl stop libelle-parser-worker.service
sudo systemctl start libelle-parser-worker.service
sudo systemctl show libelle-parser-worker.service -p MainPID -p NRestarts -p ActiveState -p SubState
sudo journalctl -u libelle-parser-worker.service --since '10 minutes ago' --no-pager
pgrep -af 'parser_worker|run_parser_worker_service'
sudo systemctl list-units --all 'libelle*worker*'
```

Expected: one Python launcher process on the designated host, no other worker
processes locally or on other hosts. Repeat the host inventory after every move.
When migrating hosts, stop and disable the old unit and verify its process exited
before starting the new one. Do not interpret lease protection as concurrency support.

Journal events are `started`, `stopped`, `attempts_processed`, `poll_failed`,
`already_running`, and `startup_or_runtime_failed`. Systemd records forced stops,
exit status, and restarts. An attempt event does not mean parsing succeeded; inspect
durable job state and the authorized reviewer snapshot for the outcome. Legacy
Python stdout/stderr during imports and attempts are suppressed to avoid resume,
Drive ID, and credential leakage. Durable error writes remain unchanged.
For startup failures check dependency presence, installed paths, file permissions,
required configuration and numeric settings privately. For repeated `poll_failed`,
check Google reachability, access and schema. Never enable raw tracebacks in the
service journal to diagnose credentials. An active unit alone is not a queue-health
check: prove a synthetic job completes.

## Bounded staging validation (record actual results)

Use synthetic resumes only. Record SHA, date, operator, designated host, isolation
result, enablement state, initial/final PID and restart count, job ID, status,
attempt counts, run IDs, authority and timestamps in a private release record.
Do not record file IDs, raw resumes, tokens or full environment output.

1. **Startup and queued recovery:** stop the worker, submit one synthetic resume
   through staging intake, and confirm its durable job is `queued`. Record its
   job ID and attempts. Restart the API and verify the same row survives. Start
   the worker and observe `started`, then polling and eventual success with a
   resolvable authoritative result. Allow two minutes for a normal synthetic PDF;
   otherwise record failure and inspect coarse state. Check no extra logical job
   was created and restart the worker again to verify the succeeded authority and
   attempts remain unchanged.
2. **Controlled failure:** while the worker is idle, record `MainPID` and
   `NRestarts`, then run:

   ```bash
   sudo systemctl kill --kill-whom=main --signal=SIGKILL libelle-parser-worker.service
   ```

   Within 30 seconds, require an active service, a new PID, increased restart
   count, and another `started` event. Submit another synthetic job and require
   completion within two minutes. `systemctl stop` is not a crash test because it
   deliberately disables automatic restart for that stop.
3. **Interrupted running attempt:** with a fresh synthetic job and attempts below
   its cap, observe `running` in the private staging Sheet and kill the main
   process as above. Capture the row before and after restart. It must survive
   with its attempts, error evidence and old run ID intact until reclaim. Wait
   until the recorded lease expiry plus two polling intervals plus two minutes
   (default roughly 17 minutes from claim). Require a fresh run ID on reclaim,
   an incremented attempt count, and eventual valid authority. Never manually
   clear a lease, reset attempts, or overwrite a result. If the job completes
   before termination, record this case as not exercised and repeat with a new
   synthetic job. Jobs already at the attempt cap are not eligible for reclaim;
   record that outcome without bypassing policy.
4. **Independent restart:** record worker PID, restart only the API, and require
   the worker PID to stay unchanged. Restart only the worker and verify API
   `/health` at `http://127.0.0.1:8003/health` remains available.
5. **Pi reboot:** in the staging maintenance window, reboot the Pi. After SSH is
   back (allow five minutes), require both units enabled and active, exactly one
   worker, a new boot's `started` journal event, and completion of a synthetic job.
   Retain a queued synthetic job across reboot if practical. A missed deadline
   is a failed check, not permission to start a second worker.
6. **Isolation and privacy:** confirm the approved staging Sheet was updated and
   live resources were not touched. Review the service journal for only coarse
   events and systemd lifecycle entries; no resume text, email, tokens or Drive
   IDs. Record PASS/FAIL for every check in the v0.4 release record.

These are deployment acceptance checks, not results claimed by repository tests.
They require the designated Linux host and staging credentials.

## Rollback

Stop the worker before rolling back code or dependencies. Keep durable rows,
results and errors intact. Roll back only to a release compatible with the current
queue schema and #365 semantics, then restart the API and worker separately and
repeat the smoke check. If that is unavailable, leave the worker stopped, record
queued work and the incident, and restore a compatible release; do not run an
older in-process parser against the same queue. Never delete durable work as part
of service cleanup. Use `systemctl disable --now libelle-parser-worker.service`
when retiring a host.
