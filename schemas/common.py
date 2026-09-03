"""Shared strict schema primitives.

Raw DynamoDB values are parsed at the service boundary. These schemas intentionally
forbid undeclared fields so schema drift fails loudly instead of silently leaking data.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

NonEmptyString = Annotated[str, Field(min_length=1)]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class RecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    PENDING = "pending"


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PipelineStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FeedbackSentiment(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class GeoPoint(StrictSchema):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]


class ContactPoint(StrictSchema):
    type: str | None = None
    value: str | None = None
    country_code: str | None = None
    is_primary: bool | None = None


class AuditFields(StrictSchema):
    created_by: NonEmptyString
    date_created: datetime
    updated_by: NonEmptyString | None = None
    date_updated: datetime | None = None


class JsonMapList(StrictSchema):
    """Typed wrapper for document-shaped DynamoDB lists using JSON-safe values."""

    items: list[dict[str, JsonValue]] = Field(default_factory=list)


def require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return value


class TimezoneAwareSchema(StrictSchema):
    @field_validator("*", mode="after")
    @classmethod
    def validate_datetime_timezone(cls, value: object) -> object:
        if isinstance(value, datetime):
            return require_timezone(value)
        return value
