"""Dashboard aggregation service using only the mock repository."""

from datetime import date, datetime, timedelta, timezone

from backend_dashboard.schemas import (
    ActivitySummary,
    AihBuddyOverviewResponse,
    BackupHealth,
    DashboardMetric,
    DashboardMetricKey,
    DashboardOverviewResponse,
    DataQualitySummary,
    DateRange,
    FeedbackSummary,
    MetricPoint,
    OnboardingSummary,
    OperationsOverviewResponse,
    PipelineHealth,
    PatientBreakdown,
    ScopedDashboardResponse,
    SubscriptionSummary,
)

from .repository import MockDashboardRepository


class DashboardService:
    def __init__(self, repository: MockDashboardRepository) -> None:
        self._repository = repository

    def overview(self, report_range: DateRange, tenant_id: str | None = None) -> DashboardOverviewResponse:
        organizations = self._repository.list_organizations()
        providers = self._repository.list_providers(tenant_id)
        if tenant_id:
            organizations = [item for item in organizations if item.id == tenant_id]
        return DashboardOverviewResponse(
            generated_at=self._now(),
            range=report_range,
            metrics=self._metrics(report_range, 1.0, tenant_id),
            pipeline=self.pipeline_health(),
            backups=self.backup_health(),
            subscriptions=self.subscription_summary(),
            onboarding=self.onboarding_summary(),
            feedback=self.feedback_summary(),
            data_quality=self.data_quality_summary(),
            activity=ActivitySummary(records_created=823, records_updated=196, active_providers=sum(item.status.value == "active" for item in providers), active_organizations=sum(item.status.value == "active" for item in organizations)),
            patient_breakdown=PatientBreakdown(total=0),
        )

    def organization_dashboard(self, organization_id: str, report_range: DateRange) -> ScopedDashboardResponse:
        organization = self._repository.get_organization(organization_id)
        factor = max(organization.recording_count / 17628, 0.05)
        return ScopedDashboardResponse(scope_id=organization.id, scope_name=organization.name, generated_at=self._now(), range=report_range, metrics=[metric for metric in self._metrics(report_range, factor) if metric.key is not DashboardMetricKey.ORGANIZATIONS])

    def provider_dashboard(self, provider_id: str, report_range: DateRange) -> ScopedDashboardResponse:
        provider = self._repository.get_provider(provider_id)
        factor = max(provider.patient_count / 6524, 0.01)
        excluded = {DashboardMetricKey.ORGANIZATIONS, DashboardMetricKey.PROVIDERS}
        return ScopedDashboardResponse(scope_id=provider.id, scope_name=provider.name, generated_at=self._now(), range=report_range, metrics=[metric for metric in self._metrics(report_range, factor) if metric.key not in excluded])

    def aih_buddy(self, report_range: DateRange, tenant_id: str | None = None) -> AihBuddyOverviewResponse:
        qrisk = next(metric for metric in self._metrics(report_range, 1.0, tenant_id) if metric.key is DashboardMetricKey.QRISK_SCREENINGS)
        return AihBuddyOverviewResponse(generated_at=self._now(), range=report_range, total_screenings=2136, completed_screenings=1984, awaiting_review=94, high_risk_flags=58, active_providers=73, series=[qrisk])

    def operations(self, report_range: DateRange) -> OperationsOverviewResponse:
        return OperationsOverviewResponse(generated_at=self._now(), range=report_range, pipeline=self.pipeline_health(), backups=self.backup_health(), subscriptions=self.subscription_summary(), onboarding=self.onboarding_summary(), feedback=self.feedback_summary(), data_quality=self.data_quality_summary())

    @staticmethod
    def pipeline_health() -> PipelineHealth:
        return PipelineHealth(total=17628, completed=17042, processing=114, pending=286, failed=186, success_rate=96.68)

    @staticmethod
    def backup_health() -> BackupHealth:
        return BackupHealth(total_recordings=17628, backed_up_recordings=17214, missing_backups=414, coverage_percent=97.65, average_delay_seconds=46.2)

    @staticmethod
    def subscription_summary() -> SubscriptionSummary:
        return SubscriptionSummary(points_consumed=48620, transaction_count=17628, average_points_per_event=2.76)

    @staticmethod
    def onboarding_summary() -> OnboardingSummary:
        return OnboardingSummary(pending=17, approved=84, rejected=6, oldest_pending_days=9)

    @staticmethod
    def feedback_summary() -> FeedbackSummary:
        return FeedbackSummary(total=842, positive=719, neutral=82, negative=41, positive_percent=85.39)

    @staticmethod
    def data_quality_summary() -> DataQualitySummary:
        return DataQualitySummary(total_issues=131, missing_coordinates=7, missing_provider_contacts=19, orphaned_phr_records=11, unmatched_lab_reports=38, recordings_without_backup=56)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _points(report_range: DateRange, total: float) -> list[MetricPoint]:
        span = max((report_range.date_to - report_range.date_from).days, 1)
        weights = (0.09, 0.11, 0.12, 0.14, 0.16, 0.18, 0.20)
        return [MetricPoint(date=report_range.date_from + timedelta(days=round(span * index / 6)), value=round(total * weight, 2)) for index, weight in enumerate(weights)]

    def _metrics(self, report_range: DateRange, factor: float, tenant_id: str | None = None) -> list[DashboardMetric]:
        definitions = (
            (DashboardMetricKey.ORGANIZATIONS, "Organizations", 6.0, 4.2),
            (DashboardMetricKey.PROVIDERS, "Medical professionals", 126.0, 8.4),
            (DashboardMetricKey.PATIENTS, "Registered patients", 6524.0, 12.1),
            (DashboardMetricKey.HEART_RECORDINGS, "Heart recordings", 10742.0, 9.6),
            (DashboardMetricKey.LUNG_RECORDINGS, "Lung recordings", 6886.0, 7.8),
            (DashboardMetricKey.LAB_REPORTS, "Lab reports", 3248.0, 6.7),
            (DashboardMetricKey.QRISK_SCREENINGS, "QRisk screenings", 2136.0, 10.2),
            (DashboardMetricKey.NORMAL_HEART_SOUND_REPORTS, "Normal HS AI reports", 7904.0, 11.4),
            (DashboardMetricKey.MURMUR_HEART_SOUND_REPORTS, "Murmur HS AI reports", 1382.0, 5.9),
        )
        return [DashboardMetric(key=key, label=label, total=round(total * factor, 2), change_percent=change, series=self._points(report_range, total * factor)) for key, label, total, change in definitions]
