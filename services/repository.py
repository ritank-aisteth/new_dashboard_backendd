"""In-memory repository used until a reviewed production adapter is introduced."""

from datetime import date, datetime, timezone
from uuid import uuid4

from schemas import (
    LocationSummary,
    OnboardingAcceptedResponse,
    OrganizationCreateRequest,
    OrganizationSummary,
    ProviderCreateRequest,
    ProviderSummary,
    SubscriptionRenewalResponse,
    SubscriptionStatus,
)
from schemas.common import GeoPoint, RecordStatus


class ResourceNotFoundError(LookupError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(f"{resource} was not found")
        self.resource = resource
        self.resource_id = resource_id


class MockDashboardRepository:
    """Deterministic synthetic records; never reads production systems."""

    def __init__(self) -> None:
        self._organizations = [
            OrganizationSummary(id="org-001", name="Northstar Medical Centre", city="Bengaluru", state="Karnataka", country="India", status=RecordStatus.ACTIVE, provider_count=24, patient_count=1284, recording_count=3678, date_created=date(2026, 7, 12)),
            OrganizationSummary(id="org-002", name="Cedar Grove Clinic", city="Mysuru", state="Karnataka", country="India", status=RecordStatus.ACTIVE, provider_count=16, patient_count=846, recording_count=2105, date_created=date(2026, 7, 3)),
            OrganizationSummary(id="org-003", name="Harborview Health", city="Kochi", state="Kerala", country="India", status=RecordStatus.ACTIVE, provider_count=31, patient_count=1630, recording_count=4512, date_created=date(2026, 6, 28)),
            OrganizationSummary(id="org-004", name="Blueleaf Community Care", city="Chennai", state="Tamil Nadu", country="India", status=RecordStatus.PENDING, provider_count=9, patient_count=412, recording_count=928, date_created=date(2026, 6, 19)),
            OrganizationSummary(id="org-005", name="Summit Heart Institute", city="Hyderabad", state="Telangana", country="India", status=RecordStatus.ACTIVE, provider_count=28, patient_count=1390, recording_count=3984, date_created=date(2026, 6, 8)),
            OrganizationSummary(id="org-006", name="Willowbrook Hospital", city="Pune", state="Maharashtra", country="India", status=RecordStatus.ACTIVE, provider_count=18, patient_count=962, recording_count=2421, date_created=date(2026, 5, 22)),
        ]
        self._providers = [
            ProviderSummary(id="provider-001", name="Dr. Anaya Rao", role="Doctor", specialty="Cardiology", organization_id="org-001", organization_name="Northstar Medical Centre", status=RecordStatus.ACTIVE, patient_count=184, date_created=date(2026, 7, 15)),
            ProviderSummary(id="provider-002", name="Dr. Vihaan Sen", role="Doctor", specialty="Internal Medicine", organization_id="org-003", organization_name="Harborview Health", status=RecordStatus.ACTIVE, patient_count=159, date_created=date(2026, 7, 9)),
            ProviderSummary(id="provider-003", name="Nurse Mira Das", role="Nurse", specialty="Cardiac Care", organization_id="org-005", organization_name="Summit Heart Institute", status=RecordStatus.ACTIVE, patient_count=132, date_created=date(2026, 6, 30)),
            ProviderSummary(id="provider-004", name="Dr. Kabir Mehta", role="Doctor", specialty="Pulmonology", organization_id="org-002", organization_name="Cedar Grove Clinic", status=RecordStatus.ACTIVE, patient_count=118, date_created=date(2026, 6, 24)),
            ProviderSummary(id="provider-005", name="Dr. Tara Iyer", role="Doctor", specialty="Family Medicine", organization_id="org-006", organization_name="Willowbrook Hospital", status=RecordStatus.PENDING, patient_count=0, date_created=date(2026, 6, 18)),
            ProviderSummary(id="provider-006", name="Nurse Reva Nair", role="Nurse", specialty="Outpatient Care", organization_id="org-004", organization_name="Blueleaf Community Care", status=RecordStatus.ACTIVE, patient_count=86, date_created=date(2026, 6, 11)),
        ]
        self._provider_logins = {provider.id for provider in self._providers}
        synthetic_statuses = [SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.ACTIVE, SubscriptionStatus.INACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.ACTIVE]
        self._providers = [
            provider.model_copy(update={
                "subscription_status": synthetic_statuses[index],
                "subscription_plan": "1 Years Plan" if synthetic_statuses[index] is not SubscriptionStatus.INACTIVE else None,
                "subscription_end_date": datetime(2027, 8, 20, tzinfo=timezone.utc) if synthetic_statuses[index] is SubscriptionStatus.ACTIVE else datetime(2026, 1, 1, tzinfo=timezone.utc) if synthetic_statuses[index] is SubscriptionStatus.EXPIRED else None,
            })
            for index, provider in enumerate(self._providers)
        ]
        self._locations = [
            LocationSummary(organization_id="org-001", organization_name="Northstar Medical Centre", city="Bengaluru", state="Karnataka", country="India", location=GeoPoint(latitude=12.9716, longitude=77.5946), provider_count=24),
            LocationSummary(organization_id="org-002", organization_name="Cedar Grove Clinic", city="Mysuru", state="Karnataka", country="India", location=GeoPoint(latitude=12.2958, longitude=76.6394), provider_count=16),
            LocationSummary(organization_id="org-003", organization_name="Harborview Health", city="Kochi", state="Kerala", country="India", location=GeoPoint(latitude=9.9312, longitude=76.2673), provider_count=31),
            LocationSummary(organization_id="org-004", organization_name="Blueleaf Community Care", city="Chennai", state="Tamil Nadu", country="India", location=GeoPoint(latitude=13.0827, longitude=80.2707), provider_count=9),
            LocationSummary(organization_id="org-005", organization_name="Summit Heart Institute", city="Hyderabad", state="Telangana", country="India", location=GeoPoint(latitude=17.3850, longitude=78.4867), provider_count=28),
            LocationSummary(organization_id="org-006", organization_name="Willowbrook Hospital", city="Pune", state="Maharashtra", country="India", location=GeoPoint(latitude=18.5204, longitude=73.8567), provider_count=18),
        ]

    def list_organizations(self) -> list[OrganizationSummary]:
        return list(self._organizations)

    def get_organization(self, organization_id: str) -> OrganizationSummary:
        organization = next((item for item in self._organizations if item.id == organization_id), None)
        if organization is None:
            raise ResourceNotFoundError("organization", organization_id)
        return organization

    def list_providers(self, organization_id: str | None = None) -> list[ProviderSummary]:
        if organization_id is None:
            return list(self._providers)
        self.get_organization(organization_id)
        return [item for item in self._providers if item.organization_id == organization_id]

    def get_provider(self, provider_id: str) -> ProviderSummary:
        provider = next((item for item in self._providers if item.id == provider_id), None)
        if provider is None:
            raise ResourceNotFoundError("provider", provider_id)
        return provider

    def provider_login_exists(self, login: str) -> bool:
        return login.casefold() in {item.casefold() for item in self._provider_logins}

    def list_locations(self) -> list[LocationSummary]:
        return list(self._locations)

    def accept_organization(self, payload: OrganizationCreateRequest, actor: str, access_token: str = "") -> OnboardingAcceptedResponse:
        del actor
        del access_token
        organization_id = str(uuid4())
        self._organizations.insert(0, OrganizationSummary(
            id=organization_id, name=payload.name, city=payload.city, state=payload.state,
            country=payload.country, status=RecordStatus.ACTIVE, provider_count=0,
            patient_count=0, recording_count=0, date_created=date.today(),
        ))
        self._locations.insert(0, LocationSummary(
            organization_id=organization_id, organization_name=payload.name, city=payload.city,
            state=payload.state, country=payload.country, location=payload.location, provider_count=0,
        ))
        return self._accepted("organization", organization_id)

    def accept_provider(self, payload: ProviderCreateRequest, actor: str, access_token: str = "") -> OnboardingAcceptedResponse:
        del access_token
        organization = self.get_organization(payload.tenant_id)
        provider_id = str(uuid4())
        self._providers.insert(0, ProviderSummary(
            id=provider_id, name=payload.name, role=payload.role, specialty=payload.specialty,
            organization_id=organization.id, organization_name=organization.name,
            status=RecordStatus.ACTIVE, patient_count=0, date_created=date.today(),
        ))
        self._provider_logins.add(payload.login)
        self.renew_subscription(provider_id, payload.subscription_duration_years, actor)
        return self._accepted("provider", provider_id)

    def renew_subscription(self, provider_id: str, duration_years: int, actor: str) -> SubscriptionRenewalResponse:
        del actor
        provider = self.get_provider(provider_id)
        start_date = max(datetime.now(timezone.utc), provider.subscription_end_date or datetime.now(timezone.utc))
        end_date = start_date.replace(year=start_date.year + duration_years)
        plan_name = "1 Years Plan" if duration_years == 1 else "3 Years Plan"
        renewed = provider.model_copy(update={"subscription_status": SubscriptionStatus.ACTIVE, "subscription_plan": plan_name, "subscription_end_date": end_date})
        self._providers = [renewed if item.id == provider_id else item for item in self._providers]
        return SubscriptionRenewalResponse(status="renewed", provider_id=provider_id, plan_name=plan_name, start_date=start_date, end_date=end_date)

    @staticmethod
    def _accepted(resource_type: str, resource_id: str, persistence: str = "in-memory") -> OnboardingAcceptedResponse:
        from datetime import datetime, timezone

        return OnboardingAcceptedResponse(
            request_id=resource_id,
            resource_type=resource_type,
            status="accepted",
            persistence=persistence,
            submitted_at=datetime.now(timezone.utc),
        )
