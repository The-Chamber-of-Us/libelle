# Volunteer retention and deletion operations

This operator-only, offline procedure implements the lifecycle distinction in
[#408's domain contract](../architecture/coordination_lifecycle.md). It reuses the
manifest and deletion machinery from local `volunteer-data-retention` commit
`dc170b7` (the #380/#407 work), extending it with scoped lifecycle operations.
There is no background expiry job and no new retention duration. TCUS must approve
source eligibility, the period after a coordination purpose ends, external-copy
retention and the operator review cadence before applying the corresponding policy.

## Select the purpose of the operation

| Reason | Eligibility | Effect |
| --- | --- | --- |
| `volunteer_deletion` (default) | Explicitly verified volunteer deletion request and IDs | Delete all matching intake, processing and current coordination rows and referenced PDFs; minimize identifying reviewer history. Active purpose does not block this. |
| `source_expiry` | Operator selects IDs under an approved source policy | Delete intake, PDFs, parser jobs/results and errors; minimize old reviewer history; preserve current ops exactly. Existing ops must have valid explicit coordination intent; unassessed, malformed or duplicate ops require review first. |
| `coordination_expiry` | Ended purpose on/before the supplied approved cutoff | Delete current ops and minimize identifying history. Leave intake and PDFs on their own lifecycle. Every selected ID must be eligible; no partial eligibility batch. |

`--orphans` selects only IDs with **neither a submission nor an ops root**. An
ops-only record is intentional coordination, not an orphan. Unassessed/malformed
ops-only roots are also protected from automatic orphan selection and require
review. Neither age, workflow status, notes nor parser activity selects expiry.
Multiple submissions remain separate; equal email addresses never establish identity.

The application stores the current human-authored takeaway, STATE, WHY, NEXT
ACTION, REVISIT, notes, tags and contact context only in ops. Review these before
source expiry and remove detailed intake evidence that was manually copied there.
Do not preserve resumes, employment or education histories as coordination notes.
Old event values are not reviewed current context: the executor replaces matching
ops_events rows with action counts only (`create`, `update`, or `anonymized`). It
clears identifiers, actor, timestamps, field names and old/new values. This avoids
a second archive of superseded content. The command does not automatically copy
source fields into ops or infer that arbitrary free text is safe.

## Prepare and preview

1. Verify the request or approved expiry policy outside this tool. Collect every
   relevant submission ID, including ops-only IDs. Look up reviewed coordination
   name/contact where needed and verify identity; contact matching alone is not
   authority. Inventory controlled downloads, logs, exports, backups and orphan
   Drive uploads separately. The command handles referenced PDFs, not arbitrary
   Drive folder searches.
2. Put ingress and the dashboard into maintenance mode. Stop **all readers and
   writers on every host**: API instances, workers, reconciliation, scripts and
   manual Sheet edits. Drain or terminate in-flight work and close reviewer/PDF
   windows. Stop other deletion commands as well. The apply flag attests this
   precondition; it is not a distributed lock. Online deletion is unsupported.
3. Create a private durable receipt directory outside Git, owned by the operator,
   mode 0700, for example `/var/lib/libelle/privacy`. Do not use temporary storage
   for production recovery. Use a distinct manifest for each operation.
4. Run from the repository root with backend dependencies and the deployment's
   environment. Relative default credentials resolve from `backend/`; manifests
   resolve from the caller's directory. Preview performs only Sheets reads and
   does not load Drive credentials.

Examples (replace IDs, receipt paths and the illustrative cutoff with approved values):

```sh
# Explicit full deletion; repeat --submission-id for multiple verified IDs.
python scripts/delete_volunteer_data.py --submission-id ID_ONE

# Source evidence only, preserving reviewed coordination.
python scripts/delete_volunteer_data.py --submission-id ID_ONE --reason source_expiry

# Independent coordination expiry; this date is an example, not a retention policy.
python scripts/delete_volunteer_data.py --submission-id ID_ONE --reason coordination_expiry --approved-coordination-cutoff 2026-01-01T00:00:00Z

# Derived artifacts with neither kind of root.
python scripts/delete_volunteer_data.py --orphans
```

Inspect counts. Unexpected tabs, headers, extra columns, nonempty unkeyed rows,
shared Drive references and uploaded resumes without references block deletion.
Repair the inventory offline. For lifecycle review errors, assess the purpose via
the coordination controls before entering maintenance; do not fabricate approval
from `ops.updated_at` or reset an ended timestamp to bypass expiry rules.

## Apply and recover

Append these flags to the reviewed preview command:

```sh
--apply --writers-and-readers-stopped --manifest /var/lib/libelle/privacy/operation-001.json
```

The executor writes a mode-0600 manifest before external deletion. It binds the
spreadsheet, exact selected IDs, file references, reason and approved cutoff.
Referenced Drive files are permanently deleted first, recording confirmed progress
after each deletion. Then one Sheets batch removes only the selected domains and
minimizes their history. It rereads the inventory and verifies absence in the
targeted domains; retained coordination is expected after source expiry. Duplicate
source and processing rows are all removed. Explicit full deletion also removes
all duplicate ops. Coordination expiry requires no Drive credentials or operations.

A crash or partial failure leaves a restricted receipt for retry. Keep maintenance
enabled and retain it. Resume inherits the original reason and cutoff, so a source
expiry retry cannot become full volunteer deletion:

```sh
python scripts/delete_volunteer_data.py --resume /var/lib/libelle/privacy/operation-001.json
python scripts/delete_volunteer_data.py --resume /var/lib/libelle/privacy/operation-001.json --apply --writers-and-readers-stopped
```

Changing the reason, cutoff, store or IDs fails. Newly introduced file references
also fail application against an existing receipt. A lost Sheets response is
recoverable even when the selected rows are already gone. Confirmed file deletions
are skipped. A Drive failure or timeout, including 404, is not proof of deletion;
the owner must distinguish missing files from lost access. Once permanent absence
is verified, add `--confirmed-absent-drive-id VERIFIED_ID` to the resume command.
Only receipt-listed IDs may be attested. Never discard an unfinished receipt to
work around a recovery failure.

Version-1 receipts from the predecessor tool mean **full volunteer deletion**.
They cannot be reused for scoped expiry. Review their original authorization
before resuming; an old receipt alone is not authorization for an age sweep.
Use a new receipt for a new authorized selection/reason. `--expired` remains
unsupported. No duration is inferred from a receipt or a timestamp.

Exit 0 with `applied: true` and receipt state `stores_deleted` means the selected
application-store operation was verified, not that all external copies vanished.
`external_cleanup_required: true` remains until the operator handles controlled
logs, downloads, backups, orphan uploads and provider history according to the
approved policy. Exit 1 is incomplete; exit 2 is invalid usage. Diagnostics use
safe stage descriptions and omit API payloads and volunteer identifiers.

## Completion and restore

Record operator completion without copying volunteer content. Keep recovery
receipts protected until recovery and the approved backup-suppression window are
complete, then remove identifying receipts according to policy. Backups must be
restored into an isolated environment; replay each operation's **original scope**
before serving it. Use new manifests for restored stores/files so old confirmed
Drive deletions are not incorrectly skipped. A restored source-expiry operation
must preserve coordination; a full deletion must remove both roots.

Restart behind maintenance and check the expected snapshot/resume behavior:
source expiry leaves coordination-only records and no mediated resume; full
deletion leaves neither; coordination expiry removes ops but may leave independently
retained intake. API responses carry `Cache-Control: no-store`; close/reload existing
clients and purge controlled downloaded copies. Restart workers only after
verification. Repository tests use fake APIs and do not establish production
isolation or Google permissions. Before release with real volunteer data, exercise
all three scopes in staging, force partial failure/retry, verify stopped-writer
isolation, apply the ops schema migration and record external cleanup controls.
