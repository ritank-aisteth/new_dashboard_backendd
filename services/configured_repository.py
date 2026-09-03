"""Elasticsearch-backed repository configured from the local dashboard config."""

import os
from datetime import date, datetime, timezone
from uuid import uuid4

from pydantic import JsonValue

from backend_dashboard.schemas import LocationSummary, OnboardingAcceptedResponse, OrganizationCreateRequest, OrganizationSummary, ProviderCreateRequest, ProviderSummary, SubscriptionRenewalResponse, SubscriptionStatus
from backend_dashboard.schemas.common import GeoPoint, RecordStatus

from .elasticsearch import ElasticsearchGateway, JsonObject, as_object, number_value, parse_date, string_value
from .dynamodb import DynamoDBGateway
from .legacy_dashboard import LegacyDashboardGateway
from .repository import MockDashboardRepository, ResourceNotFoundError


class ConfiguredDashboardRepository(MockDashboardRepository):
    """Reads the same Elasticsearch indices used by the legacy dashboard."""

    def __init__(self, gateway: ElasticsearchGateway, dynamodb: DynamoDBGateway, legacy_writer: LegacyDashboardGateway | None = None) -> None:
        self._gateway = gateway
        self._dynamodb = dynamodb
        self._legacy_writer = legacy_writer
        self._subscription_storage = os.getenv("DASHBOARD_SUBSCRIPTION_STORAGE", "transaction").strip().casefold()
        if self._subscription_storage not in {"transaction", "provider"}:
            raise ValueError("DASHBOARD_SUBSCRIPTION_STORAGE must be 'transaction' or 'provider'")

    def list_organizations(self) -> list[OrganizationSummary]:
        body: JsonObject = {"size": 1000, "query": {"match_all": {}}, "sort": [{"date_created": "desc"}]}
        return [self._organization(source) for source in self._gateway.records(self._gateway.index("tenant"), body)]

    def get_organization(self, organization_id: str) -> OrganizationSummary:
        body: JsonObject = {"size": 1, "query": {"term": {"unique_id.keyword": organization_id}}}
        records = self._gateway.records(self._gateway.index("tenant"), body)
        if not records:
            body = {"size": 1, "query": {"match_phrase": {"unique_id": organization_id}}}
            records = self._gateway.records(self._gateway.index("tenant"), body)
        if not records:
            raise ResourceNotFoundError("organization", organization_id)
        return self._organization(records[0])

    def list_providers(self, organization_id: str | None = None) -> list[ProviderSummary]:
        query: JsonObject = {"match_all": {}}
        if organization_id is not None:
            query = {"match_phrase": {"tenant_id": organization_id}}
        body: JsonObject = {"size": 2000, "query": query, "sort": [{"date_created": "desc"}]}
        sources = self._gateway.records(self._gateway.index("provider_registration"), body)
        subscriptions = self._subscription_map([required_string(source, "login") for source in sources])
        return [self._provider(source, subscriptions.get(required_string(source, "login"))) for source in sources]

    def get_provider(self, provider_id: str) -> ProviderSummary:
        body: JsonObject = {"size": 1, "query": {"term": {"unique_id.keyword": provider_id}}}
        records = self._gateway.records(self._gateway.index("provider_registration"), body)
        if not records:
            body = {"size": 1, "query": {"match_phrase": {"unique_id": provider_id}}}
            records = self._gateway.records(self._gateway.index("provider_registration"), body)
        if not records:
            raise ResourceNotFoundError("provider", provider_id)
        source = records[0]
        login = required_string(source, "login")
        return self._provider(source, self._subscription_map([login]).get(login))

    def provider_login_exists(self, login: str) -> bool:
        body: JsonObject = {"size": 1, "query": {"term": {"login.keyword": login}}}
        if self._gateway.records(self._gateway.index("provider_registration"), body):
            return True
        body = {"size": 1, "query": {"match_phrase": {"login": login}}}
        return bool(self._gateway.records(self._gateway.index("provider_registration"), body))

    def accept_organization(self, payload: OrganizationCreateRequest, actor: str, access_token: str = "") -> OnboardingAcceptedResponse:
        organization_id = str(uuid4())
        now = datetime.now(timezone.utc)
        document: JsonObject = {
            "unique_id": organization_id, "name": payload.name,
            "abdm_service_id": payload.abdm_service_id or "", "address": payload.address,
            "city": payload.city, "state": payload.state, "country": payload.country,
            "pincode": payload.pincode,
            "location": {"lat": payload.location.latitude, "lon": payload.location.longitude},
            "record_status": "active", "tags": "NONE",
            "date_created": now.isoformat(), "date_updated": now.isoformat(),
        }
        if self._legacy_writer is not None and self._legacy_writer.configured:
            self._legacy_writer.create_organization(payload, access_token)
        else:
            self._dynamodb.put_item(self._dynamodb.tenant_table, document)
        return self._accepted("organization", organization_id, "dynamodb")

    def accept_provider(self, payload: ProviderCreateRequest, actor: str, access_token: str = "") -> OnboardingAcceptedResponse:
        organization = self.get_organization(payload.tenant_id)
        provider_id = str(uuid4())
        now = datetime.now(timezone.utc)
        document: JsonObject = {
            "unique_id": provider_id, "login": payload.login, "name": payload.name,
            "role": payload.role, "specialty": payload.specialty, "record_type": "provider",
            "tenant_id": organization.id, "tenant_name": organization.name,
            "address": payload.address, "city": payload.city, "state": payload.state,
            "country": payload.country, "pincode": payload.pincode,
            "geo_point": {"lat": payload.location.latitude, "lon": payload.location.longitude},
            "email": [item.model_dump(exclude_none=True) for item in payload.email],
            "phone": [item.model_dump(exclude_none=True) for item in payload.phone],
            "record_status": "active", "tags": "None", "nickname": provider_id[:8],
            "created_by": actor, "updated_by": actor, "c_un_cre_by": actor, "c_un_upd_by": actor,
            "date_created": now.isoformat(), "date_updated": now.isoformat(),
        }
        subscription, plan_name, start_date, end_date = self._subscription_document(
            organization.id, payload.login, payload.subscription_duration_years, actor, now
        )
        if self._subscription_storage == "provider":
            document.update({
                "subscription_status": "active",
                "subscription_plan": plan_name,
                "subscription_start_date": start_date.isoformat(),
                "subscription_end_date": end_date.isoformat(),
            })
            self._dynamodb.put_item(self._dynamodb.provider_table, document)
            return self._accepted("provider", provider_id, "dynamodb")
        if self._legacy_writer is not None and self._legacy_writer.configured:
            self._legacy_writer.create_provider(payload, organization.name, access_token)
        else:
            self._dynamodb.put_provider_with_subscription(document, subscription)
        return self._accepted("provider", provider_id, "dynamodb")

    def renew_subscription(self, provider_id: str, duration_years: int, actor: str) -> SubscriptionRenewalResponse:
        provider = self.get_provider(provider_id)
        now = datetime.now(timezone.utc)
        start_date = max(now, provider.subscription_end_date or now)
        document, plan_name, start_date, end_date = self._subscription_document(
            provider.organization_id, self._provider_login(provider_id), duration_years, actor, start_date
        )
        if self._subscription_storage == "provider":
            source = self._provider_source(provider_id)
            source.update({
                "subscription_status": "active",
                "subscription_plan": plan_name,
                "subscription_start_date": start_date.isoformat(),
                "subscription_end_date": end_date.isoformat(),
                "date_updated": now.isoformat(),
                "updated_by": actor,
            })
            self._dynamodb.put_item(self._dynamodb.provider_table, source)
            return SubscriptionRenewalResponse(status="renewed", provider_id=provider_id, plan_name=plan_name, start_date=start_date, end_date=end_date)
        self._dynamodb.put_item(self._dynamodb.subscription_table, document)
        return SubscriptionRenewalResponse(status="renewed", provider_id=provider_id, plan_name=plan_name, start_date=start_date, end_date=end_date)

    @staticmethod
    def _subscription_document(
        tenant_id: str, login: str, duration_years: int, actor: str, start_date: datetime
    ) -> tuple[JsonObject, str, datetime, datetime]:
        try:
            end_date = start_date.replace(year=start_date.year + duration_years)
        except ValueError:
            end_date = start_date.replace(month=2, day=28, year=start_date.year + duration_years)
        transaction_id = str(uuid4())
        timestamp = int(start_date.timestamp())
        plan_name = "1 Years Plan" if duration_years == 1 else "3 Years Plan"
        plan_id = "dd5a0806-e329-42f6-99fd-091a5163e292" if duration_years == 1 else "eac2d3f8-018e-4693-b02f-4047b533ad2c"
        document: JsonObject = {
            "tenant_id": tenant_id,
            "login": login,
            "unique_id": transaction_id,
            "info_type_key": f"subscription~add--{timestamp}--{transaction_id}",
            "points": 10_000_000_000,
            "consumption_type": "aisteth",
            "description": [{
                "plan_name": plan_name,
                "consumption_type": "aisteth",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "period": (end_date - start_date).days,
                "renewal_type": "manual",
                "plan_id": plan_id,
                "deduction_type": "unlimited",
            }],
            "created_by": actor,
            "c_un_cre_by": actor,
            "c_un_upd_by": actor,
            "date_created": start_date.isoformat(),
            "date_updated": start_date.isoformat(),
            "updated_by": actor,
            "record_status": "active",
        }
        return document, plan_name, start_date, end_date

    def _provider_login(self, provider_id: str) -> str:
        return required_string(self._provider_source(provider_id), "login")

    def _provider_source(self, provider_id: str) -> JsonObject:
        body: JsonObject = {"size": 1, "query": {"term": {"unique_id.keyword": provider_id}}}
        records = self._gateway.records(self._gateway.index("provider_registration"), body)
        if not records:
            raise ResourceNotFoundError("provider", provider_id)
        return records[0]

    def _subscription_map(self, logins: list[str]) -> dict[str, JsonObject]:
        if not logins:
            return {}
        body: JsonObject = {
            "size": 10000,
            "query": {"bool": {"filter": [
                {"terms": {"login.keyword": list(dict.fromkeys(logins))}},
                {"prefix": {"info_type_key.keyword": "subscription~add"}},
            ]}},
            "sort": [{"date_created": "desc"}],
        }
        result: dict[str, JsonObject] = {}
        for source in self._gateway.records(self._gateway.index("subscription_transaction"), body):
            login = string_value(source.get("login"))
            if login and login not in result:
                result[login] = source
        return result

    def list_locations(self) -> list[LocationSummary]:
        items: list[LocationSummary] = []
        sources = self._gateway.records(self._gateway.index("tenant"), {"size": 1000, "query": {"exists": {"field": "location"}}})
        for source in sources:
            location = self._location(source)
            if location is None:
                continue
            organization = self._organization(source)
            items.append(LocationSummary(
                organization_id=organization.id,
                organization_name=organization.name,
                city=organization.city,
                state=organization.state,
                country=organization.country,
                location=location,
                provider_count=organization.provider_count,
            ))
        return items

    @staticmethod
    def _organization(source: JsonObject) -> OrganizationSummary:
        return OrganizationSummary(
            id=required_string(source, "unique_id"),
            name=required_string(source, "name", "Unnamed organization"),
            city=required_string(source, "city", "Unknown"),
            state=required_string(source, "state", "Unknown"),
            country=required_string(source, "country", "Unknown"),
            status=record_status(source.get("record_status")),
            provider_count=integer_value(source.get("provider_count")),
            patient_count=integer_value(source.get("patient_count")),
            recording_count=integer_value(source.get("recording_count")),
            date_created=source_date(source),
        )

    @staticmethod
    def _provider(source: JsonObject, subscription: JsonObject | None = None) -> ProviderSummary:
        subscription = subscription or {}
        descriptions = subscription.get("description")
        description = as_object(descriptions[0]) if isinstance(descriptions, list) and descriptions else {}
        end_date = datetime_value(description.get("end_date")) or datetime_value(source.get("subscription_end_date"))
        provider_active = record_status(source.get("record_status")) is RecordStatus.ACTIVE
        embedded_status = string_value(source.get("subscription_status")).casefold()
        subscription_active = record_status(subscription.get("record_status")) is RecordStatus.ACTIVE if subscription else embedded_status == "active"
        if not provider_active or not subscription_active:
            subscription_status = SubscriptionStatus.INACTIVE
        elif end_date is not None and end_date < datetime.now(timezone.utc):
            subscription_status = SubscriptionStatus.EXPIRED
        else:
            subscription_status = SubscriptionStatus.ACTIVE
        return ProviderSummary(
            id=required_string(source, "unique_id", required_string(source, "login")),
            name=required_string(source, "name", "Unnamed provider"),
            role=required_string(source, "role", "Provider"),
            specialty=required_string(source, "specialty", required_string(source, "record_type", "General")),
            organization_id=required_string(source, "tenant_id"),
            organization_name=required_string(source, "tenant_name", "Unknown organization"),
            status=record_status(source.get("record_status")),
            patient_count=integer_value(source.get("patient_count")),
            date_created=source_date(source),
            subscription_status=subscription_status,
            subscription_plan=string_value(description.get("plan_name")) or string_value(source.get("subscription_plan")) or None,
            subscription_end_date=end_date,
        )

    @staticmethod
    def _location(source: JsonObject) -> GeoPoint | None:
        location = as_object(source.get("location")) or as_object(source.get("geo_point"))
        latitude = number_value(location.get("latitude")) or number_value(location.get("lat"))
        longitude = number_value(location.get("longitude")) or number_value(location.get("lon"))
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None
        return GeoPoint(latitude=latitude, longitude=longitude)


def required_string(source: JsonObject, key: str, default: str = "unknown") -> str:
    return string_value(source.get(key), default).strip() or default


def integer_value(value: JsonValue | None) -> int:
    return max(0, int(number_value(value)))


def source_date(source: JsonObject) -> date:
    value = string_value(source.get("date_created"))
    return parse_date(value) if value else date.today()


def datetime_value(value: JsonValue | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def record_status(value: JsonValue | None) -> RecordStatus:
    raw = string_value(value, RecordStatus.ACTIVE.value).casefold()
    try:
        return RecordStatus(raw)
    except ValueError:
        return RecordStatus.ACTIVE
