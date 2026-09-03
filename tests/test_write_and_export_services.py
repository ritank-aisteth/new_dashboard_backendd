"""Regression tests for source-of-truth writes and repeat report delivery."""

import unittest
from datetime import date
from typing import Any
from unittest.mock import patch

from backend_dashboard.schemas import OrganizationCreateRequest, ProviderCreateRequest
from backend_dashboard.schemas.common import GeoPoint
from backend_dashboard.services.configured_repository import ConfiguredDashboardRepository
from backend_dashboard.services.report_export import SummaryReportExporter


class CapturingDynamoDB:
    tenant_table = "dev_tenant"
    provider_table = "dev_provider_registration"
    subscription_table = "dev_subscription_transaction"

    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, Any]]] = []

    def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        self.writes.append((table_name, item))


class RejectingElasticsearch:
    def index(self, suffix: str) -> str:
        return f"dev_{suffix}"

    def records(self, index: str, _body: dict[str, Any]) -> list[dict[str, Any]]:
        if index == "dev_tenant":
            return [{
                "unique_id": "org-1", "name": "Regression Clinic", "city": "Bengaluru",
                "state": "Karnataka", "country": "India", "record_status": "active",
                "date_created": "2026-08-31T00:00:00+00:00",
            }]
        return []

    def index_document(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("Onboarding must never write directly to Elasticsearch")


class WriteAndExportServiceTests(unittest.TestCase):
    def test_organization_creation_writes_only_to_dynamodb(self) -> None:
        dynamodb = CapturingDynamoDB()
        repository = ConfiguredDashboardRepository(RejectingElasticsearch(), dynamodb)  # type: ignore[arg-type]
        payload = OrganizationCreateRequest(
            name="Regression Clinic", address="1 Test Road", city="Bengaluru",
            state="Karnataka", country="India", pincode="560001",
            location=GeoPoint(latitude=12.97, longitude=77.59),
        )

        accepted = repository.accept_organization(payload, "admin@example.invalid")

        self.assertEqual(accepted.persistence, "dynamodb")
        self.assertEqual(len(dynamodb.writes), 1)
        self.assertEqual(dynamodb.writes[0][0], "dev_tenant")
        self.assertIn("location", dynamodb.writes[0][1])

    def test_provider_creation_writes_provider_and_subscription_state_to_dynamodb(self) -> None:
        dynamodb = CapturingDynamoDB()
        with patch.dict("os.environ", {"DASHBOARD_SUBSCRIPTION_STORAGE": "provider"}):
            repository = ConfiguredDashboardRepository(RejectingElasticsearch(), dynamodb)  # type: ignore[arg-type]
        payload = ProviderCreateRequest(
            login="doctor@example.invalid", name="Regression Doctor", role="Doctor", specialty="Cardiology",
            tenant_id="org-1", address="1 Test Road", city="Bengaluru", state="Karnataka",
            country="India", pincode="560001", location=GeoPoint(latitude=12.97, longitude=77.59),
            subscription_duration_years=1,
        )

        accepted = repository.accept_provider(payload, "admin@example.invalid")

        self.assertEqual(accepted.persistence, "dynamodb")
        self.assertEqual(len(dynamodb.writes), 1)
        table, document = dynamodb.writes[0]
        self.assertEqual(table, "dev_provider_registration")
        self.assertEqual(document["login"], "doctor@example.invalid")
        self.assertEqual(document["subscription_status"], "active")
        self.assertEqual(document["subscription_plan"], "1 Years Plan")
        self.assertIn("subscription_end_date", document)

    def test_repeated_exports_each_execute_delivery(self) -> None:
        exporter = SummaryReportExporter()
        with patch.dict("os.environ", {"LEGACY_DASHBOARD_CONFIG_PATH": "configured"}), patch(
            "backend_dashboard.services.report_export.generate_and_email_summary", return_value=12
        ) as deliver:
            first = exporter.enqueue(["org-1"], "admin@example.invalid", date(2026, 1, 1), date(2026, 8, 25), "Custom")
            second = exporter.enqueue(["org-1"], "admin@example.invalid", date(2026, 1, 1), date(2026, 8, 25), "Custom")

        self.assertEqual(first, "delivered")
        self.assertEqual(second, "delivered")
        self.assertEqual(deliver.call_count, 2)


if __name__ == "__main__":
    unittest.main()
