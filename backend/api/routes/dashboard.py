from fastapi import APIRouter

from services.dashboard_service import get_snapshot_records

router = APIRouter()


@router.get("/snapshot")
def get_snapshot():
    return get_snapshot_records()
