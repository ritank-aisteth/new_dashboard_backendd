"""Request and response models for the dashboard HTTP API."""

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field

from .common import ContactPoint, GeoPoint, Identifier, NonEmptyString, RecordStatus, StrictSchema
from .dashboard import (
    BackupHealth,
    DashboardMetric,
    DataQualitySummary,
    DateRange,
    FeedbackSummary,
    OnboardingSummary,
    PipelineHealth,
    SubscriptionSummary,
)


class ApiError(StrictSchema):
    code: NonEmptyString
    message: NonEmptyString
    request_id: str | None = None


class HealthResponse(StrictSchema):
    status: str
    service: str
    version: str
    integration_mode: str
    timestamp: datetime


class OrganizationSummary(StrictSchema):
    id: Identifier
    name: NonEmptyString
    city: NonEmptyString
    state: NonEmptyString
    country: NonEmptyString
    status: RecordStatus
    provider_count: Annotated[int, Field(ge=0)]
    patient_count: Annotated[int, Field(ge=0)]
    recording_count: Annotated[int, Field(ge=0)]
    date_created: date


class OrganizationListResponse(StrictSchema):
    items: list[OrganizationSummary]
    total: Annotated[int, Field(ge=0)]
    next_cursor: str | None = None


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class ProviderSummary(StrictSchema):
    id: Identifier
    name: NonEmptyString
    role: NonEmptyString
    specialty: NonEmptyString
    organization_id: Identifier
    organization_name: NonEmptyString
    status: RecordStatus
    patient_count: Annotated[int, Field(ge=0)]
    date_created: date
    subscription_status: SubscriptionStatus = SubscriptionStatus.INACTIVE
    subscription_plan: str | None = None
    subscription_end_date: datetime | None = None
class ProviderListResponse(StrictSchema):
    items: list[ProviderSummary]
    total: Annotated[int, Field(ge=0)]
    next_cursor: str | None = None


class LocationSummary(StrictSchema):
    organization_id: Identifier
    organization_name: NonEmptyString
    city: NonEmptyString
    state: NonEmptyString
    country: NonEmptyString
    location: GeoPoint
    provider_count: Annotated[int, Field(ge=0)]


class LocationListResponse(StrictSchema):
    items: list[LocationSummary]
    total: Annotated[int, Field(ge=0)]


class ScopedDashboardResponse(StrictSchema):
    scope_id: Identifier
    scope_name: NonEmptyString
    generated_at: datetime
    range: DateRange
    metrics: list[DashboardMetric]


class AihBuddyOverviewResponse(StrictSchema):
    generated_at: datetime
    range: DateRange
    total_screenings: Annotated[int, Field(ge=0)]
    completed_screenings: Annotated[int, Field(ge=0)]
    awaiting_review: Annotated[int, Field(ge=0)]
    high_risk_flags: Annotated[int, Field(ge=0)]
    active_providers: Annotated[int, Field(ge=0)]
    series: list[DashboardMetric]


class OperationsOverviewResponse(StrictSchema):
    generated_at: datetime
    range: DateRange
    pipeline: PipelineHealth
    backups: BackupHealth
    subscriptions: SubscriptionSummary
    onboarding: OnboardingSummary
    feedback: FeedbackSummary
    data_quality: DataQualitySummary


class OrganizationCreateRequest(StrictSchema):
    name: NonEmptyString
    abdm_service_id: str | None = None
    address: NonEmptyString
    city: NonEmptyString
    state: NonEmptyString
    country: NonEmptyString
    pincode: NonEmptyString
    location: GeoPoint


class ProviderCreateRequest(StrictSchema):
    login: Identifier
    name: NonEmptyString
    role: NonEmptyString
    specialty: NonEmptyString
    tenant_id: Identifier
    address: NonEmptyString
    city: NonEmptyString
    state: NonEmptyString
    country: NonEmptyString
    pincode: NonEmptyString
    location: GeoPoint
    email: list[ContactPoint] = Field(default_factory=list)
    phone: list[ContactPoint] = Field(default_factory=list)
    subscription_duration_years: Literal[1, 3] = 1


class OnboardingAcceptedResponse(StrictSchema):
    request_id: Identifier
    resource_type: str
    status: str
    persistence: str
    submitted_at: datetime


class SummaryExportRequest(StrictSchema):
    organization_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    date_from: date
    date_to: date
    selected_date: NonEmptyString = "Custom"


class SummaryExportAcceptedResponse(StrictSchema):
    status: str
    organization_count: Annotated[int, Field(ge=1)]


class SubscriptionRenewalRequest(StrictSchema):
    duration_years: Literal[1, 3]


class SubscriptionRenewalResponse(StrictSchema):
    status: str
    provider_id: Identifier
    plan_name: NonEmptyString
    start_date: datetime
    end_date: datetime
