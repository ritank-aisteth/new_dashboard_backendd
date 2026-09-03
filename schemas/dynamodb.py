"""Strict record schemas derived from `DynamoDB Tables (1).pdf`.

These are persistence-boundary models. They should not be returned directly from
dashboard routes because several records contain patient or provider identifiers.
"""

from datetime import datetime
from typing import Annotated

from pydantic import Field, JsonValue

from .common import (
    ContactPoint,
    FeedbackSentiment,
    GeoPoint,
    Identifier,
    NonEmptyString,
    PipelineStatus,
    RecordStatus,
    RequestStatus,
    TimezoneAwareSchema,
)


class TenantRecord(TimezoneAwareSchema):
    unique_id: Identifier
    name: NonEmptyString
    abdm_service_id: str | None = None
    city: NonEmptyString
    country: NonEmptyString
    date_created: datetime
    date_updated: datetime
    location: GeoPoint | None = None
    pincode: NonEmptyString
    record_status: RecordStatus
    state: NonEmptyString
    tags: str | None = None


class ProviderRegistrationRecord(TimezoneAwareSchema):
    login: Identifier
    unique_id: Identifier
    tenant_id: Identifier
    tenant_name: str | None = None
    name: NonEmptyString
    address: str | None = None
    created_by: str | None = None
    c_un_cre_by: str | None = None
    c_un_upd_by: str | None = None
    date_created: datetime
    date_updated: datetime
    device_id: str | None = None
    email: list[ContactPoint] = Field(default_factory=list)
    geo_point: GeoPoint | None = None
    nickname: str | None = None
    phone: list[ContactPoint] = Field(default_factory=list)
    record_status: RecordStatus
    record_type: NonEmptyString
    role: NonEmptyString
    tags: str | None = None
    updated_by: str | None = None


class PatientRegistrationRecord(TimezoneAwareSchema):
    unique_id: Identifier
    file_number: Identifier
    tenant_id: Identifier
    created_by: Identifier
    c_un_cre_by: str | None = None
    date_created: datetime
    date_of_birth: str | None = None
    date_updated: datetime
    first_name: NonEmptyString
    gender: NonEmptyString
    record_status: RecordStatus
    updated_by: Identifier


class PhrRecord(TimezoneAwareSchema):
    patient_unique_id: Identifier
    info_type_key: Identifier
    unique_id: Identifier
    tenant_id: Identifier
    created_by: Identifier
    updated_by: Identifier
    date_created: datetime
    date_updated: datetime
    file_uploads: list[dict[str, JsonValue]] = Field(default_factory=list)
    form_data: list[dict[str, JsonValue]] = Field(default_factory=list)


class PhrMetadataRecord(TimezoneAwareSchema):
    patient_unique_id: Identifier
    info_type_key: Identifier
    unique_id: Identifier
    tenant_id: Identifier
    created_by: Identifier
    login: Identifier
    date_created: datetime
    form_data: list[dict[str, JsonValue]]


class AistethAudioBackupRecord(TimezoneAwareSchema):
    unique_id: Identifier
    savedas_filename: NonEmptyString
    original_filename: NonEmptyString
    tenant_id: Identifier
    created_by: Identifier
    login: Identifier
    date_created: datetime
    date_file_created: datetime


class MlPipelineStatusRecord(TimezoneAwareSchema):
    unique_id: Identifier
    filename: NonEmptyString
    info_type_key: NonEmptyString
    created_by: Identifier
    login: Identifier
    status: PipelineStatus
    tenant_id: Identifier
    ttl_timestamp: Annotated[int, Field(ge=0)] | None = None
    date_created: datetime


class SubscriptionTransactionRecord(TimezoneAwareSchema):
    tenant_id: Identifier
    info_type_key: Identifier
    unique_id: Identifier
    consumption_type: NonEmptyString
    created_by: Identifier
    c_un_cre_by: str | None = None
    c_un_upd_by: str | None = None
    date_created: datetime
    date_updated: datetime
    description: list[dict[str, JsonValue]]
    login: Identifier
    points: float
    record_status: RecordStatus
    updated_by: Identifier


class AistethFeedbackRecord(TimezoneAwareSchema):
    patient_unique_id: Identifier
    info_type_key: Identifier
    unique_id: Identifier
    login: Identifier
    comments: str | None = None
    created_by: Identifier
    date_created: datetime
    date_updated: datetime
    feedback: FeedbackSentiment
    filename: NonEmptyString
    tenant_id: Identifier
    updated_by: Identifier


class LabReportPiiRecord(TimezoneAwareSchema):
    patient_unique_id: Identifier
    unique_id: Identifier
    filename: NonEmptyString
    created_by: Identifier
    date_created: datetime
    date_updated: datetime
    pii: list[dict[str, JsonValue]]
    tenant_id: Identifier
    updated_by: Identifier


class LabReportExtractorRecord(TimezoneAwareSchema):
    patient_unique_id: Identifier
    unique_id: Identifier
    report_id: Identifier
    created_by: Identifier
    date_created: datetime
    date_updated: datetime
    form_data: list[dict[str, JsonValue]]
    tenant_id: Identifier
    updated_by: Identifier


class RegistrationRequestBase(TimezoneAwareSchema):
    login: Identifier
    unique_id: Identifier
    created_by: Identifier
    date_created: datetime
    date_updated: datetime
    email: list[ContactPoint] = Field(default_factory=list)
    name: NonEmptyString
    phone: list[ContactPoint]
    status: RequestStatus
    updated_by: Identifier


class ProviderRegistrationRequestRecord(RegistrationRequestBase):
    pass


class UserRequestRecord(RegistrationRequestBase):
    pass

