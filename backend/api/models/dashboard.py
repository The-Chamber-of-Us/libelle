from typing import Literal

from pydantic import BaseModel, ConfigDict

from ops_schema import VALID_OPS_STATUSES


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SnapshotRawData(SnapshotModel):
    created_at: str
    full_name: str
    email: str
    location_raw: str
    timezone: str
    skills_raw: str
    interests: str
    experience_level: str
    availability: str
    motivation: str
    linkedin_url: str
    github_url: str
    consent_given: str
    resume_filename: str
    resume_status: str


class SnapshotParsedData(SnapshotModel):
    parser_state: Literal["pending", "complete"]
    parser_run_id: str
    created_at: str
    parser_version: str
    parsed_skills_raw: str
    parsed_location_raw: str
    parser_confidence: str


class SnapshotResolvedData(SnapshotModel):
    resolver_state: Literal["not_run", "resolved", "zero_matches"]
    resolver_version: str
    aliases_version: str
    resolved_skill_ids: str
    unknown_skills: str
    resolver_coverage: str


class SnapshotOpsData(SnapshotModel):
    status: Literal[VALID_OPS_STATUSES]
    notes: str
    tags: str
    contact_tracking: str
    updated_at: str
    updated_by: str


class SnapshotErrorsData(SnapshotModel):
    has_error: bool
    latest_error_summary: str
    latest_error_stage: str
    latest_error_code: str


class ReviewerSubmissionSnapshot(SnapshotModel):
    submission_id: str
    raw: SnapshotRawData
    parsed: SnapshotParsedData
    resolved: SnapshotResolvedData
    ops: SnapshotOpsData
    errors: SnapshotErrorsData
