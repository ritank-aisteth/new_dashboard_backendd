"""End-to-end contract tests for the synthetic FastAPI service."""

import os
import unittest
from datetime import date

from fastapi.testclient import TestClient

os.environ["DASHBOARD_DATA_MODE"] = "synthetic"

from auth import AuthenticatedDashboardUser, require_dashboard_access
from api.dependencies import get_summary_report_exporter
from main import app
from schemas import (
    AihBuddyOverviewResponse,
    DashboardOverviewResponse,
    HealthResponse,
    LocationListResponse,
    OnboardingAcceptedResponse,
    OperationsOverviewResponse,
    OrganizationListResponse,
    ProviderListResponse,
    ScopedDashboardResponse,
    SummaryExportAcceptedResponse,
    SubscriptionRenewalResponse,
)
from services import SummaryReportExporter


class CapturingReportExporter(SummaryReportExporter):
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def enqueue(
        self,
        organization_ids: list[str],
        email: str,
        date_from: date,
        date_to: date,
        selected_date: str,
    ) -> str:
        self.requests.append(
            {
                "manager_tenant_list": organization_ids,
                "email": email,
                "date_from": date_from,
                "date_to": date_to,
                "selected_date": selected_date,
            }
        )
        return "synthetic-message-id"


class DashboardApiTests(unittest.TestCase):
    client: TestClient
    report_exporter: CapturingReportExporter

    @classmethod
    def setUpClass(cls) -> None:
        app.dependency_overrides[require_dashboard_access] = lambda: AuthenticatedDashboardUser(
            subject="synthetic-test-subject",
            login="admin@example.invalid",
            name="Synthetic Test Admin",
            role="superadmin",
            tenant_id="all",
        )
        cls.report_exporter = CapturingReportExporter()
        app.dependency_overrides[get_summary_report_exporter] = lambda: cls.report_exporter
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()

    def test_api_rejects_missing_authentication(self) -> None:
        override = app.dependency_overrides.pop(require_dashboard_access)
        try:
            response = self.client.get("/api/v1/dashboard/overview")
        finally:
            app.dependency_overrides[require_dashboard_access] = override
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_authenticated_identity_is_sanitized_and_typed(self) -> None:
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        identity = AuthenticatedDashboardUser.model_validate(response.json())
        self.assertEqual(identity.role, "superadmin")
        self.assertEqual(identity.tenant_id, "all")

    def test_tenant_admin_is_scoped_and_cannot_create_organizations(self) -> None:
        app.dependency_overrides[require_dashboard_access] = lambda: AuthenticatedDashboardUser(
            subject="tenant-admin-subject",
            login="tenant-admin@example.invalid",
            name="Tenant Admin",
            role="admin",
            tenant_id="org-001",
            tenant_name="Northstar Medical Centre",
        )
        try:
            organizations = OrganizationListResponse.model_validate(self.client.get("/api/v1/organizations").json())
            self.assertEqual([item.id for item in organizations.items], ["org-001"])
            self.assertEqual(self.client.get("/api/v1/organizations/org-002").status_code, 403)
            self.assertEqual(self.client.get("/api/v1/providers?organization_id=org-002").status_code, 403)
            self.assertEqual(self.client.post("/api/v1/onboarding/organizations", json={
                "name": "Forbidden Tenant Clinic", "address": "1 Test Road", "city": "Test City", "state": "Test State",
                "country": "India", "pincode": "000000", "location": {"latitude": 12.9, "longitude": 77.5},
            }).status_code, 403)
        finally:
            app.dependency_overrides[require_dashboard_access] = lambda: AuthenticatedDashboardUser(
                subject="synthetic-test-subject", login="admin@example.invalid", name="Synthetic Test Admin", role="superadmin", tenant_id="all"
            )

    def test_health_and_security_headers(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        health = HealthResponse.model_validate(response.json())
        self.assertEqual(health.integration_mode, "server-managed")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(response.headers["x-request-id"])

    def test_swagger_redoc_and_openapi_are_available(self) -> None:
        swagger = self.client.get("/docs")
        self.assertEqual(swagger.status_code, 200)
        self.assertIn('/docs-assets/swagger-ui-bundle.js', swagger.text)
        self.assertIn('/static/swagger-initializer.js', swagger.text)
        initializer = self.client.get("/static/swagger-initializer.js")
        self.assertEqual(initializer.status_code, 200)
        self.assertIn('input.type = "date"', initializer.text)
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        document = response.json()
        self.assertEqual(document["openapi"], "3.0.3")
        self.assertEqual(document["info"]["title"], "AiSteth Dashboard API")
        self.assertIn("/api/v1/dashboard/overview", document["paths"])
        self.assertIn("/api/v1/onboarding/providers", document["paths"])
        self.assertIn("CognitoIdToken", document["components"]["securitySchemes"])
        self.assertEqual(document["components"]["securitySchemes"]["CognitoIdToken"]["scheme"], "bearer")
        login_operation = document["paths"]["/api/v1/auth/me"]["post"]
        login_schema = login_operation["requestBody"]["content"]["application/json"]["schema"]
        login_schema_name = login_schema["$ref"].rsplit("/", maxsplit=1)[-1]
        self.assertEqual(set(document["components"]["schemas"][login_schema_name]["properties"]), {"email", "password"})
        self.assertEqual(
            document["paths"]["/api/v1/dashboard/overview"]["get"]["security"],
            [{"CognitoIdToken": []}],
        )
        self.assertIn("/api/v1/reports/summary", document["paths"])

    def test_global_dashboard_uses_requested_range(self) -> None:
        response = self.client.get("/api/v1/dashboard/overview?date_from=2026-01-01&date_to=2026-06-30")
        self.assertEqual(response.status_code, 200)
        dashboard = DashboardOverviewResponse.model_validate(response.json())
        self.assertEqual(dashboard.range.date_from.isoformat(), "2026-01-01")
        self.assertEqual(dashboard.range.date_to.isoformat(), "2026-06-30")
        self.assertEqual(len(dashboard.metrics), 9)

    def test_invalid_and_excessive_date_ranges_are_rejected(self) -> None:
        reversed_response = self.client.get("/api/v1/dashboard/overview?date_from=2026-06-30&date_to=2026-01-01")
        long_response = self.client.get("/api/v1/dashboard/overview?date_from=2020-01-01&date_to=2026-01-01")
        self.assertEqual(reversed_response.status_code, 422)
        self.assertEqual(long_response.status_code, 422)

    def test_explicit_all_time_range_is_accepted(self) -> None:
        response = self.client.get("/api/v1/dashboard/overview?date_from=2018-01-01&date_to=2026-09-02&all_time=true")
        self.assertEqual(response.status_code, 200)
        dashboard = DashboardOverviewResponse.model_validate(response.json())
        self.assertEqual(dashboard.range.date_from.isoformat(), "2018-01-01")
        self.assertEqual(dashboard.range.date_to.isoformat(), "2026-09-02")

    def test_aih_buddy_dashboard(self) -> None:
        response = self.client.get("/api/v1/dashboard/aih-buddy")
        self.assertEqual(response.status_code, 200)
        dashboard = AihBuddyOverviewResponse.model_validate(response.json())
        self.assertEqual(dashboard.total_screenings, 2136)
        self.assertEqual(len(dashboard.series), 1)

    def test_organization_search_filter_and_pagination(self) -> None:
        search_response = self.client.get("/api/v1/organizations?search=harbor")
        status_response = self.client.get("/api/v1/organizations?status=pending")
        page_response = self.client.get("/api/v1/organizations?offset=0&limit=2")
        search_page = OrganizationListResponse.model_validate(search_response.json())
        status_page = OrganizationListResponse.model_validate(status_response.json())
        page = OrganizationListResponse.model_validate(page_response.json())
        self.assertEqual(search_page.total, 1)
        self.assertEqual(status_page.total, 1)
        self.assertEqual(len(page.items), 2)
        self.assertEqual(page.next_cursor, "2")

    def test_organization_and_provider_drilldowns(self) -> None:
        organization_response = self.client.get("/api/v1/organizations/org-001/dashboard")
        provider_response = self.client.get("/api/v1/providers/provider-001/dashboard")
        providers_response = self.client.get("/api/v1/organizations/org-001/providers")
        organization = ScopedDashboardResponse.model_validate(organization_response.json())
        provider = ScopedDashboardResponse.model_validate(provider_response.json())
        providers = ProviderListResponse.model_validate(providers_response.json())
        self.assertEqual(organization.scope_id, "org-001")
        self.assertEqual(provider.scope_id, "provider-001")
        self.assertGreaterEqual(providers.total, 1)
        self.assertNotIn("organizations", {metric.key.value for metric in organization.metrics})

    def test_missing_resources_return_sanitized_404(self) -> None:
        response = self.client.get("/api/v1/providers/not-present")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["code"], "resource_not_found")
        self.assertNotIn("not-present", body["message"])

    def test_locations_and_operations(self) -> None:
        locations_response = self.client.get("/api/v1/locations")
        operations_response = self.client.get("/api/v1/operations/overview")
        locations = LocationListResponse.model_validate(locations_response.json())
        operations = OperationsOverviewResponse.model_validate(operations_response.json())
        self.assertEqual(locations.total, 6)
        self.assertLessEqual(operations.pipeline.success_rate, 100)
        self.assertLessEqual(operations.backups.coverage_percent, 100)

    def test_onboarding_creates_organization_and_provider(self) -> None:
        organization_payload = {
            "name": "Synthetic Test Clinic",
            "address": "100 Example Avenue",
            "city": "Test City",
            "state": "Test State",
            "country": "India",
            "pincode": "000000",
            "location": {"latitude": 12.9, "longitude": 77.5},
        }
        provider_payload = {
            "login": "synthetic-login",
            "name": "Dr. Synthetic Example",
            "role": "Doctor",
            "specialty": "Cardiology",
            "tenant_id": "org-001",
            "address": "200 Example Avenue",
            "city": "Test City",
            "state": "Test State",
            "country": "India",
            "pincode": "000000",
            "location": {"latitude": 12.9, "longitude": 77.5},
            "email": [{"type": "work", "value": "doctor@example.invalid"}],
            "phone": [],
        }
        organization_response = self.client.post("/api/v1/onboarding/organizations", json=organization_payload)
        provider_response = self.client.post("/api/v1/onboarding/providers", json=provider_payload)
        organization = OnboardingAcceptedResponse.model_validate(organization_response.json())
        provider = OnboardingAcceptedResponse.model_validate(provider_response.json())
        self.assertEqual(organization_response.status_code, 201)
        self.assertEqual(provider_response.status_code, 201)
        self.assertEqual(organization.persistence, "in-memory")
        self.assertEqual(provider.persistence, "in-memory")
        self.assertEqual(self.client.get(f"/api/v1/organizations/{organization.request_id}").status_code, 200)
        created_provider = self.client.get(f"/api/v1/providers/{provider.request_id}")
        self.assertEqual(created_provider.status_code, 200)
        self.assertEqual(created_provider.json()["subscription_status"], "active")

    def test_invalid_onboarding_payload_is_rejected(self) -> None:
        response = self.client.post("/api/v1/onboarding/organizations", json={"name": "Incomplete"})
        self.assertEqual(response.status_code, 422)

    def test_summary_export_queues_selected_organizations_for_signed_in_email(self) -> None:
        response = self.client.post(
            "/api/v1/reports/summary",
            json={
                "organization_ids": ["org-001", "org-002", "org-001"],
                "date_from": "2026-02-20",
                "date_to": "2026-08-20",
                "selected_date": "Custom",
            },
        )
        accepted = SummaryExportAcceptedResponse.model_validate(response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(accepted.status, "delivered")
        self.assertEqual(accepted.organization_count, 2)
        queued = self.report_exporter.requests[-1]
        self.assertEqual(queued["manager_tenant_list"], ["org-001", "org-002"])
        self.assertEqual(queued["email"], "admin@example.invalid")

    def test_summary_export_rejects_unknown_organization(self) -> None:
        response = self.client.post(
            "/api/v1/reports/summary",
            json={"organization_ids": ["not-present"], "date_from": "2026-02-20", "date_to": "2026-08-20"},
        )
        self.assertEqual(response.status_code, 422)

    def test_provider_subscription_can_be_renewed(self) -> None:
        response = self.client.post("/api/v1/providers/provider-002/subscription/renew", json={"duration_years": 1})
        renewal = SubscriptionRenewalResponse.model_validate(response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(renewal.provider_id, "provider-002")
        self.assertGreater(renewal.end_date, renewal.start_date)
        provider = self.client.get("/api/v1/providers/provider-002").json()
        self.assertEqual(provider["subscription_status"], "active")

    def test_provider_subscription_rejects_invalid_duration(self) -> None:
        response = self.client.post("/api/v1/providers/provider-001/subscription/renew", json={"duration_years": 2})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
