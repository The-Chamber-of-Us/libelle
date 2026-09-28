"""Intentional coordination lifecycle, independent of storage and intake age."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CoordinationIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal["preserve", "end"]
    purpose: str = Field(min_length=1, max_length=500)
    takeaway: str = Field(default="", max_length=1000)
    why: str = Field(default="", max_length=500)
    next_action: str = Field(default="", max_length=500)
    revisit: date | None = None
    display_name: str = Field(default="", max_length=200)
    contact: str = Field(default="", max_length=300)
    context_reviewed: Literal[True]


class CoordinationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    state: Literal["active", "ended"]
    purpose: str = Field(min_length=1, max_length=500)
    takeaway: str = Field(default="", max_length=1000)
    why: str = Field(default="", max_length=500)
    next_action: str = Field(default="", max_length=500)
    revisit: date | None = None
    display_name: str = Field(default="", max_length=200)
    contact: str = Field(default="", max_length=300)
    purpose_started_at: datetime
    purpose_ended_at: datetime | None = None
    decided_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_lifecycle(self):
        if self.purpose_started_at.tzinfo is None:
            raise ValueError("Lifecycle timestamps must include timezone")
        if (self.state == "ended") != (self.purpose_ended_at is not None):
            raise ValueError("Only ended coordination has an end timestamp")
        if self.purpose_ended_at is not None:
            if self.purpose_ended_at.tzinfo is None or self.purpose_ended_at < self.purpose_started_at:
                raise ValueError("Invalid purpose end timestamp")
        return self


def read_coordination(value: str | None) -> CoordinationRecord | None:
    """Blank legacy state is unassessed; malformed nonblank state raises."""
    return CoordinationRecord.model_validate_json(value) if value else None


def apply_intent(
    current: CoordinationRecord | None,
    intent: CoordinationIntent,
    actor: str,
    now: datetime,
) -> CoordinationRecord:
    if now.tzinfo is None:
        raise ValueError("A timezone-aware decision time is required")
    if intent.action == "end" and current is None:
        raise ValueError("Coordination must be preserved before its purpose can end")
    started = current.purpose_started_at if current else now
    ended = None
    if intent.action == "preserve" and current and current.state == "ended":
        started = now  # An explicit new purpose, never an incidental edit.
    if intent.action == "end":
        ended = current.purpose_ended_at or now
    return CoordinationRecord(
        **intent.model_dump(exclude={"action", "context_reviewed"}),
        state="active" if intent.action == "preserve" else "ended",
        purpose_started_at=started, purpose_ended_at=ended, decided_by=actor,
    )


def retention_scope(
    reason: Literal["source_expiry", "coordination_expiry", "volunteer_deletion"],
    coordination_json: str = "",
    *,
    approved_coordination_cutoff: datetime | None = None,
) -> tuple[str, ...]:
    """Return deletion targets, not an executor or a duration policy.

    The caller establishes source eligibility and fences writers through #407.
    Explicit deletion overrides retention purpose, even with malformed metadata.
    """
    source = ("intake_evidence", "reviewer_history")
    coordination = ("coordination_context",)
    if reason == "volunteer_deletion":
        return source + coordination
    if reason == "source_expiry":
        # Never interpret absent/malformed approval as permission to cascade ops.
        return source
    if reason != "coordination_expiry":
        raise ValueError("Unknown retention reason")
    record = read_coordination(coordination_json)
    if not record or record.state != "ended" or approved_coordination_cutoff is None:
        return ()
    if approved_coordination_cutoff.tzinfo is None:
        raise ValueError("An approved timezone-aware cutoff is required")
    if record.purpose_ended_at <= approved_coordination_cutoff:
        return coordination + ("reviewer_history",)
    return ()
