# Volunteer data retention and deletion

This is Libelle's initial product retention policy for issue #380, not a legal
retention determination. The deployment administrator owns execution and records
monthly completion. Before production, assign that owner and configure the
external retention controls below. There are no automatic expiry jobs. This is an offline, single-operator workflow.

Submissions expire 365 days after `created_at`, regardless of workflow status.
Run the expiry sweep at least monthly (maximum operational removal delay: 31
days). An authenticated volunteer deletion request triggers the same workflow
within 30 days. Verify the requester outside this tool. Identify **all** their
submission IDs, including duplicate submissions and changed email addresses;
email alone is not an identity proof. No indefinite extensions are supported.

| Category / system of record | Purpose | Retention and deletion |
| --- | --- | --- |
| Contact, consent, interests, links, free text / Sheets `submissions` | Intake and volunteer coordination | 365 days plus sweep delay; delete entire matching rows on expiry/request |
| Original PDF, original filename / Drive upload folder; references in submissions and jobs | Source evidence and reviewer access | Same lifecycle; permanently delete files before removing references; trash alone is insufficient |
| Parser evidence and Resolver interpretation / Sheets `parser_results` | Explain extracted skills/location and resolution | Same lifecycle, including every historical parser attempt; delete rows |
| Queue, leases, retries, authoritative run references / Sheets `parser_jobs` | Durable processing and recovery | Same lifecycle; delete all jobs while workers and reconciliation are stopped |
| Current status, notes, tags, contact tracking, actor / Sheets `ops` | Coordination | Same lifecycle; delete rows including notes |
| Reviewer events / Sheets `ops_events` | History while active, aggregate action counts after deletion | Identifying history lives only as long as submission; replace each matching row with only allowlisted `create`/`update` action (otherwise `anonymized`). Remove event/submission IDs, actor, timestamp, source, field and both values. Non-identifying aggregate counts may remain indefinitely for operational volume comparisons |
| Failure diagnostics / Sheets `errors` | Troubleshooting | Same lifecycle; delete complete matching rows, including summaries/details and run IDs |
| Snapshot and resume responses / backend and browser memory | Reviewer read models | Computed on request, no persisted backend snapshot; API sends `Cache-Control: no-store`. Restart backend and close/reload reviewer clients during deletion; future snapshots have no deleted submission |
| Runtime/access logs, journal, proxy logs, monitoring exports | Security and operational investigation | Restricted operator access, maximum 30 days. Configure rotation/expiry on every host and external sink; identifiers and filenames can occur. On deletion purge affected records or entire log segments if selective removal is unavailable, including archived copies |
| Downloads, exports, debugging PDFs, benchmark outputs using real data, local copies | Temporary operator work only | No production data in Git or benchmark fixtures. Remove controlled copies during deletion; synthetic fixtures are outside volunteer retention. Do not make unmanaged exports |
| Deletion manifests / restricted operator filesystem | Recovery after partial deletion and suppression during backup restore | Written before deletion, mode 0600. Contains submission/file IDs, store ID, timestamps, counts and confirmed progress; no contact information or source text. Keep unfinished receipts until recovery completes and investigate daily. After external cleanup, retain for 30 days (the backup window), then delete the manifest and remove identifiers from the administrator receipt |
| Backups, Google revision/provider history | Disaster recovery | Restrict access; maximum 30-day backup window where configurable. Never restore directly into a serving environment: replay deletions and expiry offline first. Provider-internal history is outside the row/file API guarantee; confirm provider controls before production |

Only minimized event counts outlive the source in the application store. Restricted
recovery manifests temporarily outlive it to prevent lost recovery references and
backup resurrection. Source
and derived data receive the same expiry; deleting only a PDF is not submission
deletion. This command deliberately overrides append-only evidence/history
conventions for privacy maintenance. It preserves event volume and action type,
not identifiable historical replay. This is minimization, not a guarantee against
correlation with independently retained external copies.

## Administrator procedure

Use the same Sheets and Drive credentials/configuration as the deployment. Run
from the repository root with backend dependencies installed. The command is
operator-only; it is not an HTTP endpoint. The command resolves default credential
files (`org_credentials.json`, `token.json`) and relative credential environment
paths from `backend/`, matching the existing backend setup. Absolute environment
paths are recommended for deployment. Manifest paths resolve from your original
working directory. Preview requires Sheets access only; apply also loads Drive
credentials. Never copy credentials into the repository root to run this command.

Create a private receipt directory **outside the repository**, on durable storage
available for recovery (for example `/var/lib/libelle/privacy`, owned by the
operator, mode 0700). Substitute its path in the examples. Do not use `/tmp` for
production recovery receipts. Run one deletion command at a time. The stopped
services precondition includes all other administrative deletion commands.

1. Verify the request and collect every submission ID. Inspect both submissions
   and jobs for file references. Inspect the configured Drive upload folder for
   orphan uploads (including files uploaded before an intake write failed) and
   copies belonging to the volunteer; permanently remove these separately.
   The command handles referenced files only, not arbitrary Drive searches.
2. Put the proxy/dashboard in maintenance mode. Stop **all** backend instances,
   parser workers, reconciliation jobs, scripts and manual Sheet editing on
   **every** host. Drain/terminate in-flight work. Close reviewer tabs and PDF
   windows. The flag below attests this operational precondition; it is not a
   distributed lock. Online deletion is unsupported.
3. Preview one or multiple IDs:

   ```sh
   python scripts/delete_volunteer_data.py --submission-id ID_ONE --submission-id ID_TWO
   ```

   Or preview the retention sweep:

   ```sh
   python scripts/delete_volunteer_data.py --expired
   ```

   Inspect counts against the selected records. Invalid dates, unknown tabs,
   unexpected headers/columns, shared file references and uploaded resumes with
   missing references block deletion. Repair/reconcile these offline; do not
   bypass schema validation. Dates accept existing UTC timestamps and ISO 8601
   with an explicit timezone. Expiry also selects orphan derived/ops/error/job/event
   rows whose submission no longer exists: these have no remaining source purpose
   and must be removed during the next sweep. Nonempty rows without an ID block
   inventory (except already minimized audit rows); reconcile them manually before
   proceeding. Drive orphan files still require the folder inspection in step 1,
   including on every monthly sweep, because they may have no Sheets reference.
4. Apply with the same selection:

   ```sh
   python scripts/delete_volunteer_data.py --submission-id ID_ONE --apply --writers-and-readers-stopped --manifest /var/lib/libelle/privacy/request-001.json
   python scripts/delete_volunteer_data.py --expired --apply --writers-and-readers-stopped --manifest /var/lib/libelle/privacy/sweep-001.json
   ```

   Use a distinct manifest path for each new selection. Before deleting any file,
   the command durably writes the selected IDs, file references and counts to a
   mode-0600 manifest; failure to persist it blocks deletion. File deletion happens
   in sorted ID order, recording each confirmed deletion before proceeding. Only
   after every Drive operation succeeds does one Sheets `batchUpdate` delete source/derived/ops/error/job rows
   and minimize event rows atomically. Duplicate rows are all handled. A fresh
   read must find no selected submission references before `applied: true`.
   The manifest then records `stores_deleted`. Output also reports
   `external_cleanup_required: true`: this is **not** whole-request completion.
   A preview or empty expiry sweep is not evidence of completed deletion.
5. Purge controlled logs, downloads, exports, backups and orphan uploads above.
   The manifest already preserves the exact selection, including for `--expired`.
   Record the request reference, administrator, external completion date and cleanup
   status in your restricted administrator record. Do not edit the recovery
   manifest to record these. Do not add names, emails or resume content. Keep both
   the manifest and ID-bearing administrator record for 30 days after external
   completion to suppress resurrection from backups, then delete the manifest and
   remove IDs/request linkage from the administrator record. Retain only aggregate
   completion dates/counts. A restore must use the retained manifests to delete
   restored submissions and derived artifacts **before** enabling readers/writers.
   File progress in an old manifest describes the old store: when restoring a
   backup, use its submission IDs with a **new** manifest, so restored Drive files
   are not skipped as previously deleted.
6. Restart the backend behind the maintenance boundary, verify its API no longer
   returns the submission or its resume, then restart workers and reopen access.
   Reload clients. Only declare the **whole request**
   complete after external cleanup, not merely after the script succeeds.

## Partial failure and recovery

Exit status 1 means incomplete; usage errors return 2. Output includes safe
repository-owned reasons (schema mismatch, invalid timestamp, shared reference,
unkeyed row, manifest mismatch/write failure, Drive failure, or Sheets failure).
Unexpected credential/transport errors expose only a safe stage label, never API
payloads or identifiers. **Keep readers and writers stopped.**

There is no cross-service transaction: files can already be permanently deleted
while Sheets still contains their references. Never restore PDFs to roll back
privacy deletion. Resume the exact selection from its manifest, including after a
lost Sheets response or an interrupted expiry sweep:

```sh
python scripts/delete_volunteer_data.py --resume /var/lib/libelle/privacy/request-001.json
python scripts/delete_volunteer_data.py --resume /var/lib/libelle/privacy/request-001.json --apply --writers-and-readers-stopped
```

Confirmed Drive deletions are skipped on resume. A crash/timeout between the Drive
operation and the progress write is ambiguous. Inspect that reference in the
restricted manifest using the owner account. A Drive 404 can mean lost permission;
restore access if the file exists. If the owner verifies permanent absence, attest
that exact manifest-listed ID:

```sh
python scripts/delete_volunteer_data.py --resume /var/lib/libelle/privacy/request-001.json --apply --writers-and-readers-stopped --confirmed-absent-drive-id VERIFIED_FILE_ID
```

Repeat the option for multiple verified IDs. Unlisted attestations, a different
spreadsheet, or newly introduced file references are rejected. Never attest lost
access as deletion. Do not put sensitive command history in shared logs. Do not
edit/delete an unfinished receipt or change its selection. A corrupted receipt
requires owner-led reconciliation; it must not be treated as completed. A completed
resume is harmless; the stored selection remains available after Sheets removal.

For `MANIFEST_WRITE_FAILED`, restore writable private durable storage before retry.
For `MANIFEST_MISMATCH`, check configuration and stopped-writer isolation before
continuing. For invalid timestamps, schema mismatches or unkeyed rows, reconcile the
underlying data while offline and preview again. For access errors, verify the
appropriate Sheets service account or Drive OAuth owner credentials. If request
size exceeds Google limits, keep maintenance enabled and process smaller explicit
ID groups with distinct manifests; account for every ID in the original receipt.

The automated tests use fake APIs. Production acceptance still requires a staging
exercise with real Drive/Sheets permissions, a forced partial failure/retry,
verification of maintenance isolation and absent dashboard/resume data, and
recorded external log/backup expiry settings. API deletion does not claim physical
erasure from Google infrastructure or revoke copies already downloaded by others.
