"""Ops workflow write service."""

from typing import Optional, TypedDict

from storage import sheets_repo


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
