from enum import Enum
from typing import Any, Mapping


class _StateValue(str, Enum):
    def __str__(self) -> str:
        return self.value


class ResumeState(_StateValue):
    NONE_PROVIDED = "none_provided"
    UPLOAD_PENDING = "upload_pending"
    UPLOADED = "uploaded"
    UPLOAD_FAILED = "upload_failed"


class ParserState(_StateValue):
    NOT_STARTED = "not_started"
    SKIPPED_NO_RESUME = "skipped_no_resume"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ResolverState(_StateValue):
    NOT_STARTED = "not_started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED_NO_PARSER_OUTPUT = "skipped_no_parser_output"


class ReviewStatus(_StateValue):
    NEW = "new"
    REVIEWED = "reviewed"
    CONTACTED = "contacted"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    CLOSED = "closed"


class SubmissionHealthState(_StateValue):
    COMPLETE = "complete"
    PARTIAL_SUCCESS = "partial_success"
    NO_RESUME_OK = "no_resume_ok"
    PARSER_FAILED = "parser_failed"
    RESOLVER_FAILED = "resolver_failed"
    PENDING_PROCESSING = "pending_processing"
    BROKEN_PIPELINE = "broken_pipeline"


VALID_RESUME_STATES = tuple(state.value for state in ResumeState)
VALID_PARSER_STATES = tuple(state.value for state in ParserState)
VALID_RESOLVER_STATES = tuple(state.value for state in ResolverState)
VALID_REVIEW_STATUSES = tuple(status.value for status in ReviewStatus)
VALID_SUBMISSION_HEALTH_STATES = tuple(state.value for state in SubmissionHealthState)
TRACEABLE_ORIGINS = (
    "intake",
    "file_upload",
    "parser",
    "resolver",
    "snapshot",
    "ops",
    "audit_error_logging",
)

USER_ENTERED_FIELDS = (
    "submission_id",
    "name",
    "email",
    "phone",
    "location",
    "availability",
    "interests",
)
RAW_PARSER_FIELDS = (
    "parser_output",
    "raw_parser_output",
    "parsed_resume",
    "parser_result",
)
FAILURE_STATES = {
    ParserState.FAILED.value,
    ResolverState.FAILED.value,
    ResumeState.UPLOAD_FAILED.value,
}


def validate_review_status(status: Any) -> str:
    if isinstance(status, ReviewStatus):
        return status.value
    if isinstance(status, str) and status in VALID_REVIEW_STATUSES:
        return status
    allowed_statuses = ", ".join(VALID_REVIEW_STATUSES)
    raise ValueError(f"Invalid review status. Expected one of: {allowed_statuses}.")


def derive_submission_health_state(record: Mapping[str, Any]) -> str:
    resume_state = _state_value(record, "resume_state", ResumeState)
    parser_state = _state_value(record, "parser_state", ParserState)
    resolver_state = _state_value(record, "resolver_state", ResolverState)

    if resume_state is None or parser_state is None or resolver_state is None:
        return SubmissionHealthState.BROKEN_PIPELINE.value

    if resume_state == ResumeState.NONE_PROVIDED:
        if parser_state in {
            ParserState.NOT_STARTED,
            ParserState.SKIPPED_NO_RESUME,
        } and resolver_state in {
            ResolverState.NOT_STARTED,
            ResolverState.SKIPPED_NO_PARSER_OUTPUT,
        }:
            return SubmissionHealthState.NO_RESUME_OK.value
        return SubmissionHealthState.BROKEN_PIPELINE.value

    if resume_state in {ResumeState.UPLOAD_PENDING, ResumeState.UPLOAD_FAILED}:
        if (
            parser_state == ParserState.NOT_STARTED
            and resolver_state == ResolverState.NOT_STARTED
        ):
            return SubmissionHealthState.PENDING_PROCESSING.value
        return SubmissionHealthState.BROKEN_PIPELINE.value

    if resume_state != ResumeState.UPLOADED:
        return SubmissionHealthState.BROKEN_PIPELINE.value

    if parser_state in {ParserState.NOT_STARTED, ParserState.STARTED}:
        if resolver_state == ResolverState.NOT_STARTED:
            return SubmissionHealthState.PENDING_PROCESSING.value
        return SubmissionHealthState.BROKEN_PIPELINE.value

    if parser_state == ParserState.SUCCEEDED:
        if resolver_state == ResolverState.NOT_STARTED:
            return SubmissionHealthState.PARTIAL_SUCCESS.value
        if resolver_state == ResolverState.SUCCEEDED:
            return SubmissionHealthState.COMPLETE.value
        if resolver_state == ResolverState.FAILED:
            return SubmissionHealthState.RESOLVER_FAILED.value
        return SubmissionHealthState.BROKEN_PIPELINE.value

    if parser_state == ParserState.FAILED:
        if resolver_state in {
            ResolverState.NOT_STARTED,
            ResolverState.FAILED,
            ResolverState.SKIPPED_NO_PARSER_OUTPUT,
        }:
            return SubmissionHealthState.PARSER_FAILED.value
        return SubmissionHealthState.BROKEN_PIPELINE.value

    return SubmissionHealthState.BROKEN_PIPELINE.value


def can_start_parser(record: Mapping[str, Any]) -> bool:
    return (
        _state_value(record, "resume_state", ResumeState) == ResumeState.UPLOADED
        and _state_value(record, "parser_state", ParserState) == ParserState.NOT_STARTED
        and _state_value(record, "resolver_state", ResolverState)
        == ResolverState.NOT_STARTED
    )


def can_skip_parser(record: Mapping[str, Any]) -> bool:
    return (
        _state_value(record, "resume_state", ResumeState) == ResumeState.NONE_PROVIDED
        and _state_value(record, "parser_state", ParserState)
        in {ParserState.NOT_STARTED, ParserState.SKIPPED_NO_RESUME}
        and _state_value(record, "resolver_state", ResolverState)
        in {ResolverState.NOT_STARTED, ResolverState.SKIPPED_NO_PARSER_OUTPUT}
    )


def can_run_resolver(record: Mapping[str, Any]) -> bool:
    return (
        _state_value(record, "resume_state", ResumeState) == ResumeState.UPLOADED
        and _state_value(record, "parser_state", ParserState) == ParserState.SUCCEEDED
        and _state_value(record, "resolver_state", ResolverState)
        == ResolverState.NOT_STARTED
    )


def can_materialize_snapshot(record: Mapping[str, Any]) -> bool:
    return (
        derive_submission_health_state(record)
        != SubmissionHealthState.BROKEN_PIPELINE.value
    )


def can_update_ops(record: Mapping[str, Any]) -> bool:
    if not isinstance(record.get("submission_id"), str) or not record["submission_id"]:
        return False

    try:
        validate_review_status(record.get("review_status"))
    except ValueError:
        return False

    return can_materialize_snapshot(record)


def assert_no_raw_data_overwrite(
    previous: Mapping[str, Any],
    next_record: Mapping[str, Any],
) -> None:
    overwritten_fields = [
        field
        for field in (*USER_ENTERED_FIELDS, *RAW_PARSER_FIELDS)
        if field in previous
        and field in next_record
        and next_record[field] != previous[field]
    ]

    if overwritten_fields:
        fields = ", ".join(overwritten_fields)
        raise ValueError(f"Raw data overwrite is not allowed for: {fields}.")


def require_error_log_for_failure(failure_event: Mapping[str, Any]) -> bool:
    state = failure_event.get("state")
    if isinstance(state, _StateValue):
        state = state.value

    if state not in FAILURE_STATES:
        return True

    return all(
        isinstance(failure_event.get(field), str) and bool(failure_event[field])
        for field in ("submission_id", "origin", "error_code", "message")
    ) and failure_event["origin"] in TRACEABLE_ORIGINS


def _state_value(
    record: Mapping[str, Any],
    key: str,
    enum_type: type[_StateValue],
) -> _StateValue | None:
    value = record.get(key)
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            return None
    return None
