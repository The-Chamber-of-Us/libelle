from fastapi import APIRouter, HTTPException, Response, status as http_status

from api.models.dashboard import (
    OpsDashboardUpdateRequest,
    OpsDashboardUpdateResponse,
    OpsStatusListResponse,
    OpsWorkflowStateCreateRequest,
    OpsWorkflowStateCreateResponse,
    OpsWorkflowStateUpdateRequest,
    OpsWorkflowStateUpdateResponse,
    ReviewerSubmissionSnapshot,
)
from api.ops_status_validation import validate_incoming_ops_status
from ops_schema import VALID_OPS_STATUSES
from services.dashboard_service import get_snapshot_records
from services.ops_write_service import create_first_ops_workflow_state, update_existing_ops_workflow_state

router = APIRouter()

OPS_DASHBOARD_ACTOR = "dashboard_ops_endpoint"


@router.get("/snapshot", response_model=list[ReviewerSubmissionSnapshot])
def get_snapshot():
    return get_snapshot_records()


@router.get("/ops/statuses", response_model=OpsStatusListResponse)
def get_ops_statuses():
    return {"statuses": list(VALID_OPS_STATUSES)}


@router.post(
    "/submissions/{submission_id}/ops",
    response_model=OpsWorkflowStateCreateResponse,
    status_code=201,
)
def create_ops_workflow_state(
    submission_id: str,
    payload: OpsWorkflowStateCreateRequest,
    response: Response,
):
    status = validate_incoming_ops_status(payload.status)
    created_row = create_first_ops_workflow_state(
        submission_id,
        {
            "status": status,
            "notes": payload.notes,
            "tags": payload.tags,
            "contact_tracking": payload.contact_tracking,
            "updated_by": payload.updated_by,
        },
    )

    if created_row is None:
        response.status_code = http_status.HTTP_200_OK
        return {
            "status": "already_exists",
            "submission_id": submission_id,
            "ops": None,
        }

    return {
        "status": "created",
        "submission_id": submission_id,
        "ops": {
            "status": created_row["status"],
            "notes": created_row["notes"],
            "tags": created_row["tags"],
            "contact_tracking": created_row["contact_tracking"],
            "updated_at": created_row["updated_at"],
            "updated_by": created_row["updated_by"],
        },
    }


@router.patch(
    "/submissions/{submission_id}/ops",
    response_model=OpsWorkflowStateUpdateResponse,
    status_code=200,
)
def update_ops_workflow_state(
    submission_id: str,
    payload: OpsWorkflowStateUpdateRequest,
):
    if payload.status is None and payload.notes is None:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": "At least one ops field must be provided.",
                "fields": {"ops": "Provide status and/or notes."},
            },
        )

    workflow_fields = {"updated_by": payload.updated_by}
    if payload.status is not None:
        workflow_fields["status"] = validate_incoming_ops_status(payload.status)
    if payload.notes is not None:
        workflow_fields["notes"] = payload.notes

    updated_row = update_existing_ops_workflow_state(submission_id, workflow_fields)
    if updated_row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "OPS_ROW_NOT_FOUND",
                "message": "No existing ops row found for submission_id.",
            },
        )

    return {
        "status": "updated",
        "submission_id": submission_id,
        "ops": {
            "status": updated_row["status"],
            "notes": updated_row["notes"],
            "tags": updated_row["tags"],
            "contact_tracking": updated_row["contact_tracking"],
            "updated_at": updated_row["updated_at"],
            "updated_by": updated_row["updated_by"],
        },
    }


@router.post(
    "/ops/update",
    response_model=OpsDashboardUpdateResponse,
    status_code=200,
)
def update_ops_dashboard_state(payload: OpsDashboardUpdateRequest):
    workflow_fields = {"updated_by": OPS_DASHBOARD_ACTOR}
    if payload.status is not None:
        workflow_fields["status"] = validate_incoming_ops_status(payload.status)
    if payload.notes is not None:
        workflow_fields["notes"] = payload.notes

    updated_row = update_existing_ops_workflow_state(payload.submission_id, workflow_fields)
    if updated_row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "OPS_ROW_NOT_FOUND",
                "message": "No existing ops row found for submission_id.",
            },
        )

    return {
        "status": "updated",
        "submission_id": payload.submission_id,
        "ops": {
            "status": updated_row["status"],
            "notes": updated_row["notes"],
            "tags": updated_row["tags"],
            "contact_tracking": updated_row["contact_tracking"],
            "updated_at": updated_row["updated_at"],
            "updated_by": updated_row["updated_by"],
        },
    }
