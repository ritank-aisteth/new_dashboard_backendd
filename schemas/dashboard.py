"""PII-minimized response contracts intended for FastAPI dashboard endpoints."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field

from .common import StrictSchema


class DashboardMetricKey(StrEnum):
    ORGANIZATIONS = "organizations"
    PROVIDERS = "providers"
    PATIENTS = "patients"
    HEART_RECORDINGS = "heart_recordings"
    LUNG_RECORDINGS = "lung_recordings"
    LAB_REPORTS = "lab_reports"
    QRISK_SCREENINGS = "qrisk_screenings"
    NORMAL_HEART_SOUND_REPORTS = "normal_heart_sound_reports"
    MURMUR_HEART_SOUND_REPORTS = "murmur_heart_sound_reports"


class DateRange(StrictSchema):
    date_from: date
    date_to: date


class MetricPoint(StrictSchema):
    date: date
    value: Annotated[float, Field(ge=0)]


class DashboardMetric(StrictSchema):
    key: DashboardMetricKey
    label: str
    total: Annotated[float, Field(ge=0)]
    change_percent: float | None = None
    series: list[MetricPoint] = Field(default_factory=list)


class BreakdownItem(StrictSchema):
    label: str
    count: Annotated[int, Field(ge=0)]
    percentage: Annotated[float, Field(ge=0, le=100)]


class PatientBreakdown(StrictSchema):
    total: Annotated[int, Field(ge=0)]
    auscultation_type: list[BreakdownItem] = Field(default_factory=list)
    gender_distribution: list[BreakdownItem] = Field(default_factory=list)
    age_group_distribution: list[BreakdownItem] = Field(default_factory=list)


class MurmurBreakdown(StrictSchema):
    total_reports: Annotated[int, Field(ge=0)]
    gender_distribution: list[BreakdownItem] = Field(default_factory=list)
    age_group_distribution: list[BreakdownItem] = Field(default_factory=list)


class PipelineHealth(StrictSchema):
    total: Annotated[int, Field(ge=0)]
    completed: Annotated[int, Field(ge=0)]
    processing: Annotated[int, Field(ge=0)]
    pending: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]
    success_rate: Annotated[float, Field(ge=0, le=100)]


class BackupHealth(StrictSchema):
    total_recordings: Annotated[int, Field(ge=0)]
    backed_up_recordings: Annotated[int, Field(ge=0)]
    missing_backups: Annotated[int, Field(ge=0)]
    coverage_percent: Annotated[float, Field(ge=0, le=100)]
    average_delay_seconds: Annotated[float, Field(ge=0)] | None = None


class SubscriptionSummary(StrictSchema):
    points_consumed: Annotated[float, Field(ge=0)]
    transaction_count: Annotated[int, Field(ge=0)]
    average_points_per_event: Annotated[float, Field(ge=0)]


class OnboardingSummary(StrictSchema):
    pending: Annotated[int, Field(ge=0)]
    approved: Annotated[int, Field(ge=0)]
    rejected: Annotated[int, Field(ge=0)]
    oldest_pending_days: Annotated[int, Field(ge=0)] | None = None


class FeedbackSummary(StrictSchema):
    total: Annotated[int, Field(ge=0)]
    positive: Annotated[int, Field(ge=0)]
    neutral: Annotated[int, Field(ge=0)]
    negative: Annotated[int, Field(ge=0)]
    positive_percent: Annotated[float, Field(ge=0, le=100)]


class DataQualitySummary(StrictSchema):
    total_issues: Annotated[int, Field(ge=0)]
    missing_coordinates: Annotated[int, Field(ge=0)]
    missing_provider_contacts: Annotated[int, Field(ge=0)]
    orphaned_phr_records: Annotated[int, Field(ge=0)]
    unmatched_lab_reports: Annotated[int, Field(ge=0)]
    recordings_without_backup: Annotated[int, Field(ge=0)]


class ActivitySummary(StrictSchema):
    records_created: Annotated[int, Field(ge=0)]
    records_updated: Annotated[int, Field(ge=0)]
    active_providers: Annotated[int, Field(ge=0)]
    active_organizations: Annotated[int, Field(ge=0)]


class DashboardOverviewResponse(StrictSchema):
    generated_at: datetime
    range: DateRange
    metrics: list[DashboardMetric]
    pipeline: PipelineHealth
    backups: BackupHealth
    subscriptions: SubscriptionSummary
    onboarding: OnboardingSummary
    feedback: FeedbackSummary
    data_quality: DataQualitySummary
    activity: ActivitySummary
    patient_breakdown: PatientBreakdown | None = None
    murmur_breakdown: MurmurBreakdown | None = None
    heart_sound_distribution: list[BreakdownItem] = Field(default_factory=list)
    lung_sound_distribution: list[BreakdownItem] = Field(default_factory=list)
