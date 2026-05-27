from fastapi import APIRouter, Response, status as http_status

from api.models.dashboard import (
    OpsWorkflowStateCreateRequest,
    OpsWorkflowStateCreateResponse,
    ReviewerSubmissionSnapshot,
)
from api.ops_status_validation import validate_incoming_ops_status
from services.dashboard_service import get_snapshot_records
from services.ops_write_service import create_first_ops_workflow_state

router = APIRouter()


@router.get("/snapshot", response_model=list[ReviewerSubmissionSnapshot])
def get_snapshot():
    return get_snapshot_records()


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
