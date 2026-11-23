from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from .device_schemas import Wire

Operation = Literal["install", "uninstall"]
TargetState = Literal["queued", "leased", "running", "not_executed", "cancelled", "failed"]


class JobInput(Wire):
    version_id: UUID
    operation: Operation
    device_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]
    request_id: UUID

    @field_validator("device_ids")
    @classmethod
    def distinct_devices(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("device IDs must be unique")
        return value


class JobView(Wire):
    id: UUID
    version_id: UUID
    package_name: str
    version: str
    operation: Operation
    created_at: datetime
    counts: dict[TargetState, int]


class JobPage(Wire):
    items: list[JobView]
    total: int
    active: int


class TargetView(Wire):
    id: UUID
    device_id: UUID
    hostname: str
    state: TargetState
    cancel_requested: bool
    attempt: int | None
    lease_expires_at: datetime | None
    recovery_required: bool


class JobDetail(JobView):
    targets: list[TargetView]


class EventView(Wire):
    id: int
    target_id: UUID | None
    attempt_id: UUID | None
    action: str
    created_at: datetime


class Assignment(Wire):
    target_id: UUID
    attempt_id: UUID
    version_id: UUID
    operation: Operation
    lease_expires_at: datetime
    mode: Literal["transport_only"] = "transport_only"


class PollReply(Wire):
    assignment: Assignment | None = None
    recovery_required: bool = False


class Lease(Wire):
    attempt_id: UUID


class LeaseReply(Wire):
    lease_expires_at: datetime
    cancel_requested: bool


class Result(Lease):
    outcome: Literal["not_executed", "cancelled"]
