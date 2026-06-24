"""Ops workflow write service."""

from typing import Optional, TypedDict

from ops_schema import OPS_STATUS_NEW
from storage import sheets_repo


class OpsSubmissionNotFoundError(Exception):
    """Raised when an ops row cannot be created for an unknown submission."""


class OpsWorkflowFields(TypedDict):
    status: str
    notes: str
    tags: str
    contact_tracking: str
    updated_by: str


def create_first_ops_workflow_state(
    submission_id: str,
    workflow_fields: OpsWorkflowFields,
) -> Optional[dict[str, str]]:
    """
    Persist the first ops workflow state for a submission.

    Existing ops rows are intentionally left untouched for this create-only
    path; update-in-place belongs to a separate workflow.
    """
    return sheets_repo.create_ops_row_if_missing(
        submission_id=submission_id,
        status=workflow_fields["status"],
        notes=workflow_fields.get("notes", ""),
        tags=workflow_fields.get("tags", ""),
        contact_tracking=workflow_fields.get("contact_tracking", ""),
        updated_by=workflow_fields["updated_by"],
    )


class OpsWorkflowUpdateFields(TypedDict, total=False):
    status: str
    notes: str
    updated_by: str


def update_existing_ops_workflow_state(
    submission_id: str,
    workflow_fields: OpsWorkflowUpdateFields,
) -> Optional[dict[str, str]]:
    """
    Update the mutable ops workflow state for an existing submission row.

    Missing ops rows are intentionally left missing for this update-only path.
    """
    return sheets_repo.update_ops_row_if_exists(
        submission_id=submission_id,
        status=workflow_fields.get("status"),
        notes=workflow_fields.get("notes"),
        updated_by=workflow_fields["updated_by"],
    )


def update_or_create_ops_workflow_state(
    submission_id: str,
    workflow_fields: OpsWorkflowUpdateFields,
) -> dict[str, str]:
    """
    Update the dashboard ops state, creating the first row when needed.

    Dashboard snapshots can show a default "new" ops state before a mutable ops
    row exists. The dashboard writeback path should therefore upsert so the
    first reviewer status or notes save has somewhere to land.
    """
    updated_row = update_existing_ops_workflow_state(submission_id, workflow_fields)
    if updated_row is not None:
        return updated_row

    normalized_submission_id = str(submission_id).strip()
    if normalized_submission_id not in sheets_repo.load_submission_records():
        raise OpsSubmissionNotFoundError("No submission found for submission_id.")

    created_row = create_first_ops_workflow_state(
        normalized_submission_id,
        {
            "status": workflow_fields.get("status", OPS_STATUS_NEW),
            "notes": workflow_fields.get("notes", ""),
            "tags": "",
            "contact_tracking": "",
            "updated_by": workflow_fields["updated_by"],
        },
    )
    if created_row is not None:
        return created_row

    # If another writer created the row between update and create, finish as an
    # update so omitted fields are preserved.
    updated_after_create_race = update_existing_ops_workflow_state(submission_id, workflow_fields)
    if updated_after_create_race is not None:
        return updated_after_create_race

    raise RuntimeError("Unable to update or create ops row")
