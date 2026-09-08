"""Dashboard aggregation backed by configured Elasticsearch queries."""

from schemas import DashboardMetric, DashboardMetricKey, DateRange, MetricPoint, ScopedDashboardResponse

from .dashboard import DashboardService
from .elasticsearch import ElasticsearchGateway, JsonObject
from .repository import MockDashboardRepository


class ConfiguredDashboardService(DashboardService):
    def __init__(self, repository: MockDashboardRepository, gateway: ElasticsearchGateway) -> None:
        super().__init__(repository)
        self._gateway = gateway

    def _metrics(self, report_range: DateRange, factor: float, tenant_id: str | None = None, provider_login: str | None = None) -> list[DashboardMetric]:
        definitions: tuple[tuple[DashboardMetricKey, str, str, list[JsonObject]], ...] = (
            (DashboardMetricKey.ORGANIZATIONS, "Organizations", self._gateway.index("tenant"), []),
            (DashboardMetricKey.PROVIDERS, "Medical professionals", self._gateway.index("provider_registration"), []),
            (DashboardMetricKey.PATIENTS, "Registered patients", self._gateway.index("patient_registration"), []),
            (DashboardMetricKey.HEART_RECORDINGS, "Heart recordings", self._gateway.index("phr"), [{"match_phrase": {"info_type_key": "examinations~heart"}}]),
            (DashboardMetricKey.LUNG_RECORDINGS, "Lung recordings", self._gateway.index("phr"), [{"match_phrase": {"info_type_key": "examinations~lungs"}}]),
            (DashboardMetricKey.LAB_REPORTS, "Lab reports", self._gateway.index("phr"), [{"prefix": {"info_type_key.keyword": "labreport~"}}]),
            (DashboardMetricKey.QRISK_SCREENINGS, "QRisk screenings", self._gateway.index("phr"), [{"match_phrase": {"info_type_key": "vitals~qrscore"}}]),
            (DashboardMetricKey.NORMAL_HEART_SOUND_REPORTS, "Normal HS AI reports", self._gateway.index("phr"), [{"prefix": {"info_type_key.keyword": "ai_analysis~heart"}}, {"terms": {"form_data.ai_analysis.keyword": ["Normal", "Normal ", "normal", "Normal, no murmur detected.", "Normal, no murmur detected. ", "Normal, but noisy background", "Normal, but noisy background "]}}]),
            (DashboardMetricKey.MURMUR_HEART_SOUND_REPORTS, "Murmur HS AI reports", self._gateway.index("phr"), [{"prefix": {"info_type_key.keyword": "ai_analysis~heart"}}, {"terms": {"form_data.ai_analysis.keyword": ["Murmur", "Murmur ", "Murmur, background is very noisy.", "Murmur.", "Murmur. "]}}]),
        )
        metrics: list[DashboardMetric] = []
        for key, label, index, filters in definitions:
            scoped_filters = list(filters)
            if tenant_id:
                field = "unique_id.keyword" if key is DashboardMetricKey.ORGANIZATIONS else "tenant_id.keyword"
                scoped_filters.append({"term": {field: tenant_id}})
            if provider_login and key not in {DashboardMetricKey.ORGANIZATIONS, DashboardMetricKey.PROVIDERS}:
                scoped_filters.append({"term": {"created_by.keyword": provider_login}})
            total, series = self._gateway.metric(index, report_range, scoped_filters)
            metrics.append(
                DashboardMetric(
                    key=key,
                    label=label,
                    total=round(total * factor, 2),
                    change_percent=change_percent(series),
                    series=[point.model_copy(update={"value": round(point.value * factor, 2)}) for point in series],
                )
            )
        return metrics

    def organization_dashboard(self, organization_id: str, report_range: DateRange) -> ScopedDashboardResponse:
        organization = self._repository.get_organization(organization_id)
        metrics = [metric for metric in self._metrics(report_range, 1.0, organization_id) if metric.key is not DashboardMetricKey.ORGANIZATIONS]
        provider_count = len(self._repository.list_providers(organization_id))
        metrics = [
            metric.model_copy(update={"total": provider_count})
            if metric.key is DashboardMetricKey.PROVIDERS else metric
            for metric in metrics
        ]
        return ScopedDashboardResponse(scope_id=organization.id, scope_name=organization.name, generated_at=self._now(), range=report_range, metrics=metrics)

    def provider_dashboard(self, provider_id: str, report_range: DateRange) -> ScopedDashboardResponse:
        provider = self._repository.get_provider(provider_id)
        records = self._gateway.records(self._gateway.index("provider_registration"), {"size": 1, "_source": ["login"], "query": {"term": {"unique_id.keyword": provider_id}}})
        provider_login = str(records[0].get("login", "")) if records else ""
        excluded = {DashboardMetricKey.ORGANIZATIONS, DashboardMetricKey.PROVIDERS}
        metrics = [metric for metric in self._metrics(report_range, 1.0, provider.organization_id, provider_login) if metric.key not in excluded]
        return ScopedDashboardResponse(scope_id=provider.id, scope_name=provider.name, generated_at=self._now(), range=report_range, metrics=metrics)

    def overview(self, report_range: DateRange, tenant_id: str | None = None):
        response = super().overview(report_range, tenant_id)
        heart_distribution, lung_distribution = self._gateway.clinical_analysis_breakdowns(report_range, tenant_id)
        return response.model_copy(update={
            "patient_breakdown": self._gateway.patient_breakdown(report_range, tenant_id),
            "murmur_breakdown": self._gateway.murmur_breakdown(report_range, tenant_id),
            "heart_sound_distribution": heart_distribution,
            "lung_sound_distribution": lung_distribution,
        })


def change_percent(series: list[MetricPoint]) -> float | None:
    if len(series) < 2 or series[-2].value == 0:
        return None
    return round(((series[-1].value - series[-2].value) / series[-2].value) * 100, 2)
