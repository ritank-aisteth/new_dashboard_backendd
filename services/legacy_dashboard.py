"""Authenticated adapter for the deployed legacy DynamoDB write API."""

import os

import httpx

from schemas import OrganizationCreateRequest, ProviderCreateRequest

from .elasticsearch import ExternalServiceError


class LegacyDashboardGateway:
    def __init__(self) -> None:
        self._base_url = os.getenv("LEGACY_DASHBOARD_API_URL", "").strip().rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def create_organization(self, payload: OrganizationCreateRequest, access_token: str) -> None:
        self._post("/onboardtenant/", {
            "tenant_name": payload.name,
            "tenant_address": payload.address,
            "tenant_city": payload.city,
            "tenant_state": payload.state,
            "tenant_country": payload.country,
            "tenant_pincode": payload.pincode,
            "tenant_lat": payload.location.latitude,
            "tenant_lon": payload.location.longitude,
        }, access_token)

    def create_provider(self, payload: ProviderCreateRequest, tenant_name: str, access_token: str) -> None:
        email = next((item.value for item in payload.email if item.value), payload.login)
        phone = next((item.value for item in payload.phone if item.value), "")
        self._post("/onboardprovider/", {
            "provider_email_phone": payload.login,
            "selected_tenant_name": tenant_name,
            "selected_tenant_unique_id": payload.tenant_id,
            "provider_name": payload.name,
            "provider_email": email,
            "provider_phone_no": phone,
            "provider_state": payload.state,
            "provider_city": payload.city,
            "provider_country": payload.country,
            "provider_address": payload.address,
            "provider_pincode": payload.pincode,
            "provider_lat": payload.location.latitude,
            "provider_lon": payload.location.longitude,
            "device_id": 0,
            "subscription_plan": "3 Year" if payload.subscription_duration_years == 3 else "Yearly",
            "consumption_type": "aisteth",
            "renewal_type": "manual",
            "deduction_type": "unlimited",
        }, access_token)

    def _post(self, path: str, body: dict[str, object], access_token: str) -> None:
        if not self._base_url:
            raise ExternalServiceError("Legacy dashboard write API is not configured")
        token = access_token.removeprefix("Bearer ").strip()
        if not token:
            raise ExternalServiceError("Legacy dashboard authorization is missing")
        try:
            response = httpx.post(
                f"{self._base_url}{path}", json=body,
                headers={"Authorization": token, "Accept": "application/json"}, timeout=30.0,
            )
            response.raise_for_status()
            value = response.json()
            if not isinstance(value, dict) or value.get("Code") not in {None, "Success"}:
                raise ExternalServiceError("Legacy dashboard rejected the write")
        except (httpx.HTTPError, ValueError) as error:
            raise ExternalServiceError("Legacy dashboard write failed") from error
