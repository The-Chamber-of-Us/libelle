import pytest

from core.state_contract import (
    ParserState,
    ResolverState,
    ResumeState,
    ReviewStatus,
    SubmissionHealthState,
    TRACEABLE_ORIGINS,
    assert_no_raw_data_overwrite,
    can_materialize_snapshot,
    can_run_resolver,
    can_skip_parser,
    can_start_parser,
    can_update_ops,
    derive_submission_health_state,
    require_error_log_for_failure,
    validate_review_status,
)


def record(**overrides):
    base = {
        "submission_id": "sub_123",
        "resume_state": ResumeState.UPLOADED.value,
        "parser_state": ParserState.NOT_STARTED.value,
        "resolver_state": ResolverState.NOT_STARTED.value,
        "review_status": ReviewStatus.NEW.value,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "parser_state,resolver_state",
    [
        (ParserState.NOT_STARTED.value, ResolverState.NOT_STARTED.value),
        (ParserState.SKIPPED_NO_RESUME.value, ResolverState.SKIPPED_NO_PARSER_OUTPUT.value),
    ],
)
def test_no_resume_derives_visible_no_resume_health(parser_state, resolver_state) -> None:
    health = derive_submission_health_state(
        record(
            resume_state=ResumeState.NONE_PROVIDED.value,
            parser_state=parser_state,
            resolver_state=resolver_state,
        )
    )

    assert health == SubmissionHealthState.NO_RESUME_OK.value


def test_complete_derives_visible_complete_health() -> None:
    health = derive_submission_health_state(
        record(
            parser_state=ParserState.SUCCEEDED.value,
            resolver_state=ResolverState.SUCCEEDED.value,
        )
    )

    assert health == SubmissionHealthState.COMPLETE.value


@pytest.mark.parametrize(
    "resolver_state",
    [
        ResolverState.NOT_STARTED.value,
        ResolverState.FAILED.value,
        ResolverState.SKIPPED_NO_PARSER_OUTPUT.value,
    ],
)
def test_parser_failed_remains_visible(resolver_state) -> None:
    health = derive_submission_health_state(
        record(
            parser_state=ParserState.FAILED.value,
            resolver_state=resolver_state,
        )
    )

    assert health == SubmissionHealthState.PARSER_FAILED.value


def test_resolver_failed_preserves_parser_success_as_visible_failure() -> None:
    health = derive_submission_health_state(
        record(
            parser_state=ParserState.SUCCEEDED.value,
            resolver_state=ResolverState.FAILED.value,
        )
    )

    assert health == SubmissionHealthState.RESOLVER_FAILED.value


@pytest.mark.parametrize(
    "input_record",
    [
        record(),
        record(parser_state=ParserState.STARTED.value),
        record(
            parser_state=ParserState.SUCCEEDED.value,
            resolver_state=ResolverState.NOT_STARTED.value,
        ),
        record(
            resume_state=ResumeState.UPLOAD_PENDING.value,
            parser_state=ParserState.NOT_STARTED.value,
            resolver_state=ResolverState.NOT_STARTED.value,
        ),
    ],
)
def test_pending_and_partial_records_stay_materializable(input_record) -> None:
    assert derive_submission_health_state(input_record) in {
        SubmissionHealthState.PENDING_PROCESSING.value,
        SubmissionHealthState.PARTIAL_SUCCESS.value,
    }
    assert can_materialize_snapshot(input_record) is True


@pytest.mark.parametrize(
    "input_record",
    [
        record(parser_state="wat"),
        record(resolver_state=ResolverState.SUCCEEDED.value),
        record(
            resume_state=ResumeState.NONE_PROVIDED.value,
            parser_state=ParserState.SUCCEEDED.value,
            resolver_state=ResolverState.SUCCEEDED.value,
        ),
        {"submission_id": "sub_123"},
    ],
)
def test_broken_pipeline_cases_are_explicit(input_record) -> None:
    assert (
        derive_submission_health_state(input_record)
        == SubmissionHealthState.BROKEN_PIPELINE.value
    )
    assert can_materialize_snapshot(input_record) is False


@pytest.mark.parametrize("status", [status.value for status in ReviewStatus])
def test_validate_review_status_accepts_contract_values(status) -> None:
    assert validate_review_status(status) == status


@pytest.mark.parametrize("status", ["pending", "NEW", "in progress", "", None, 7])
def test_validate_review_status_rejects_invalid_values(status) -> None:
    with pytest.raises(ValueError, match="Invalid review status"):
        validate_review_status(status)


def test_transition_validators_allow_expected_next_steps() -> None:
    assert can_start_parser(record()) is True
    assert can_skip_parser(record(resume_state=ResumeState.NONE_PROVIDED.value)) is True
    assert can_run_resolver(record(parser_state=ParserState.SUCCEEDED.value)) is True
    assert can_update_ops(record(parser_state=ParserState.FAILED.value)) is True


def test_transition_validators_reject_contradictory_or_incomplete_records() -> None:
    assert (
        can_start_parser(
            record(
                parser_state=ParserState.SUCCEEDED.value,
                resolver_state=ResolverState.NOT_STARTED.value,
            )
        )
        is False
    )
    assert can_run_resolver(record(parser_state=ParserState.FAILED.value)) is False
    assert can_update_ops(record(submission_id="")) is False
    assert can_update_ops(record(review_status="pending")) is False


def test_transition_validators_are_pure_and_idempotent() -> None:
    input_record = record(
        parser_state=ParserState.SUCCEEDED.value,
        resolver_state=ResolverState.NOT_STARTED.value,
    )
    before = input_record.copy()

    assert can_run_resolver(input_record) is True
    assert can_run_resolver(input_record) is True
    assert derive_submission_health_state(input_record) == SubmissionHealthState.PARTIAL_SUCCESS.value
    assert derive_submission_health_state(input_record) == SubmissionHealthState.PARTIAL_SUCCESS.value
    assert input_record == before


def test_raw_data_overwrite_is_rejected() -> None:
    previous = {
        "submission_id": "sub_123",
        "full_name": "Asha",
        "parsed_skills_raw": "python",
    }
    next_record = {
        "submission_id": "sub_123",
        "full_name": "Asha Renamed",
        "parsed_skills_raw": "python, sql",
    }

    with pytest.raises(ValueError, match="full_name, parsed_skills_raw"):
        assert_no_raw_data_overwrite(previous, next_record)


def test_raw_data_guard_allows_derived_and_ops_fields_to_change() -> None:
    assert_no_raw_data_overwrite(
        {"submission_id": "sub_123", "full_name": "Asha", "review_status": "new"},
        {
            "submission_id": "sub_123",
            "full_name": "Asha",
            "review_status": "contacted",
            "submission_health_state": "complete",
        },
    )


def test_parser_write_cannot_overwrite_user_entered_fields() -> None:
    previous = {
        "submission_id": "sub_123",
        "skills_raw": "python",
        "location_raw": "Lisbon",
    }
    parser_writeback = {
        "submission_id": "sub_123",
        "skills_raw": "python, sql",
        "location_raw": "Lisbon, Portugal",
        "parsed_skills_raw": "python, sql",
    }

    with pytest.raises(ValueError, match="location_raw, skills_raw"):
        assert_no_raw_data_overwrite(previous, parser_writeback)


def test_resolver_write_cannot_overwrite_raw_parser_fields() -> None:
    previous = {
        "submission_id": "sub_123",
        "parsed_skills_raw": "python, reactjs",
        "parser_confidence": "0.82",
        "resolved_skill_ids": "",
    }
    resolver_writeback = {
        "submission_id": "sub_123",
        "parsed_skills_raw": "python, react",
        "parser_confidence": "0.82",
        "resolved_skill_ids": "skill_python, skill_react",
    }

    with pytest.raises(ValueError, match="parsed_skills_raw"):
        assert_no_raw_data_overwrite(previous, resolver_writeback)


def test_resolver_may_fill_its_own_fields_without_touching_parser_output() -> None:
    assert_no_raw_data_overwrite(
        {
            "submission_id": "sub_123",
            "parsed_skills_raw": "python, reactjs",
            "resolved_skill_ids": "",
            "resolver_coverage": "",
        },
        {
            "submission_id": "sub_123",
            "parsed_skills_raw": "python, reactjs",
            "resolved_skill_ids": "skill_python, skill_react",
            "resolver_coverage": "1.0",
        },
    )


def test_intake_system_fields_are_immutable_after_append() -> None:
    previous = {
        "submission_id": "sub_123",
        "resume_filename": "sub_123-resume.pdf",
        "created_at": "2026-06-26T10:00:00",
    }
    next_record = {
        "submission_id": "sub_123",
        "resume_filename": "renamed.pdf",
        "created_at": "2026-06-26T10:00:00",
    }

    with pytest.raises(ValueError, match="resume_filename"):
        assert_no_raw_data_overwrite(previous, next_record)


def test_field_ownership_groups_match_sheet_schema() -> None:
    from sheet_schema import SHEET_SCHEMA
    from core.state_contract import (
        AUDIT_ERROR_FIELDS,
        INTAKE_SYSTEM_FIELDS,
        RAW_PARSER_FIELDS,
        RESOLVER_OWNED_FIELDS,
        REVIEWER_OWNED_FIELDS,
        OPS_ATTRIBUTION_FIELDS,
        USER_ENTERED_FIELDS,
    )

    assert set(USER_ENTERED_FIELDS + INTAKE_SYSTEM_FIELDS) == set(
        SHEET_SCHEMA["submissions"]
    )
    assert set(RAW_PARSER_FIELDS + RESOLVER_OWNED_FIELDS) | {
        "submission_id",
        "created_at",
    } == set(SHEET_SCHEMA["parser_results"])
    assert set(REVIEWER_OWNED_FIELDS + OPS_ATTRIBUTION_FIELDS) | {
        "submission_id"
    } == set(SHEET_SCHEMA["ops"])
    assert set(AUDIT_ERROR_FIELDS) == set(SHEET_SCHEMA["errors"])


def test_failure_events_require_traceable_error_log_fields() -> None:
    for origin in TRACEABLE_ORIGINS:
        assert (
            require_error_log_for_failure(
                {
                    "submission_id": "sub_123",
                    "origin": origin,
                    "state": ParserState.FAILED.value,
                    "error_code": "PARSER_FAILED",
                    "message": "Parser failed.",
                }
            )
            is True
        )

    assert require_error_log_for_failure({"state": ParserState.FAILED.value}) is False
    assert (
        require_error_log_for_failure(
            {
                "submission_id": "sub_123",
                "origin": "unowned_worker",
                "state": ParserState.FAILED.value,
                "error_code": "PARSER_FAILED",
                "message": "Parser failed.",
            }
        )
        is False
    )
    assert require_error_log_for_failure({"state": ParserState.SUCCEEDED.value}) is True
