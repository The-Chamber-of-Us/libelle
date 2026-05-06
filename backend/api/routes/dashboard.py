from fastapi import APIRouter

from api.models.dashboard import ReviewerSubmissionSnapshot
from services.dashboard_service import get_snapshot_records

router = APIRouter()


@router.get("/snapshot", response_model=list[ReviewerSubmissionSnapshot])
def get_snapshot():
    return get_snapshot_records()
