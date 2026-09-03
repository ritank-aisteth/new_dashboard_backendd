"""Typed dashboard API routes backed by deterministic synthetic data."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend_dashboard.api.dependencies import get_dashboard_service, get_repository, get_summary_report_exporter, resolve_date_range
from backend_dashboard.auth import AuthenticatedDashboardUser, require_dashboard_access
from backend_dashboard.schemas import (
    AihBuddyOverviewResponse,
    DashboardOverviewResponse,
    DateRange,
    LocationListResponse,
    OnboardingAcceptedResponse,
    OperationsOverviewResponse,
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationSummary,
    ProviderCreateRequest,
    ProviderListResponse,
    ProviderSummary,
    ScopedDashboardResponse,
    SummaryExportAcceptedResponse,
    SummaryExportRequest,
    SubscriptionRenewalRequest,
    SubscriptionRenewalResponse,
)
from backend_dashboard.schemas.common import RecordStatus
from backend_dashboard.services import DashboardService, MockDashboardRepository, ReportExportUnavailableError, SummaryReportExporter

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_dashboard_access)])

Service = Annotated[DashboardService, Depends(get_dashboard_service)]
Repository = Annotated[MockDashboardRepository, Depends(get_repository)]
ReportRange = Annotated[DateRange, Depends(resolve_date_range)]
DashboardUser = Annotated[AuthenticatedDashboardUser, Depends(require_dashboard_access)]
ReportExporter = Annotated[SummaryReportExporter, Depends(get_summary_report_exporter)]


def tenant_scope(user: AuthenticatedDashboardUser) -> str | None:
    return None if user.role.casefold() == "superadmin" else user.tenant_id


def require_superadmin(user: AuthenticatedDashboardUser) -> None:
    if user.role.casefold() != "superadmin" or user.tenant_id != "all":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin access is required")


def require_tenant(user: AuthenticatedDashboardUser, organization_id: str) -> None:
    if tenant_scope(user) is not None and user.tenant_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This organization is outside your tenant scope")


@router.get("/auth/me", response_model=AuthenticatedDashboardUser, summary="Get the authenticated dashboard identity", tags=["Authentication"])
def authenticated_identity(user: DashboardUser) -> AuthenticatedDashboardUser:
    return user


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewResponse,
    summary="Get the global AiSteth dashboard",
    description="Typed replacement for the production global monthly-statistics endpoints.",
    tags=["Dashboard"],
)
def get_dashboard_overview(service: Service, report_range: ReportRange, user: DashboardUser) -> DashboardOverviewResponse:
    return service.overview(report_range, tenant_scope(user))


@router.get(
    "/dashboard/aih-buddy",
    response_model=AihBuddyOverviewResponse,
    summary="Get the AiH Buddy QRisk dashboard",
    description="Combines the legacy AiH Buddy monthly and report statistics into one response.",
    tags=["Dashboard"],
)
def get_aih_buddy_overview(service: Service, report_range: ReportRange, user: DashboardUser) -> AihBuddyOverviewResponse:
    require_superadmin(user)
    return service.aih_buddy(report_range, tenant_scope(user))


@router.get(
    "/organizations",
    response_model=OrganizationListResponse,
    summary="List organizations",
    tags=["Organizations"],
)
def list_organizations(
    repository: Repository,
    user: DashboardUser,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    record_status: Annotated[RecordStatus | None, Query(alias="status")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 25,
) -> OrganizationListResponse:
    items = repository.list_organizations()
    if tenant_scope(user) is not None:
        items = [item for item in items if item.id == user.tenant_id]
    if search is not None:
        needle = search.casefold()
        items = [item for item in items if needle in f"{item.name} {item.city} {item.state} {item.country}".casefold()]
    if record_status is not None:
        items = [item for item in items if item.status is record_status]
    total = len(items)
    page = items[offset : offset + limit]
    next_cursor = str(offset + limit) if offset + limit < total else None
    return OrganizationListResponse(items=page, total=total, next_cursor=next_cursor)


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationSummary,
    summary="Get an organization",
    tags=["Organizations"],
)
def get_organization(organization_id: str, repository: Repository, user: DashboardUser) -> OrganizationSummary:
    require_tenant(user, organization_id)
    return repository.get_organization(organization_id)


@router.get(
    "/organizations/{organization_id}/dashboard",
    response_model=ScopedDashboardResponse,
    summary="Get organization-scoped statistics",
    description="Replaces the legacy tenant-specific provider, patient, recording, lab, and heart-sound endpoints.",
    tags=["Organizations"],
)
def get_organization_dashboard(organization_id: str, service: Service, report_range: ReportRange, user: DashboardUser) -> ScopedDashboardResponse:
    require_tenant(user, organization_id)
    return service.organization_dashboard(organization_id, report_range)


@router.get(
    "/organizations/{organization_id}/providers",
    response_model=ProviderListResponse,
    summary="List providers for an organization",
    tags=["Organizations", "Providers"],
)
def list_organization_providers(organization_id: str, repository: Repository, user: DashboardUser) -> ProviderListResponse:
    require_tenant(user, organization_id)
    items = repository.list_providers(organization_id)
    return ProviderListResponse(items=items, total=len(items), next_cursor=None)


@router.get(
    "/providers",
    response_model=ProviderListResponse,
    summary="List medical professionals",
    tags=["Providers"],
)
def list_providers(
    repository: Repository,
    user: DashboardUser,
    organization_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 25,
) -> ProviderListResponse:
    scope = tenant_scope(user)
    if scope is not None and organization_id is not None and organization_id != scope:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This organization is outside your tenant scope")
    items = repository.list_providers(scope or organization_id)
    if search is not None:
        needle = search.casefold()
        items = [item for item in items if needle in f"{item.name} {item.role} {item.specialty} {item.organization_name}".casefold()]
    total = len(items)
    page = items[offset : offset + limit]
    next_cursor = str(offset + limit) if offset + limit < total else None
    return ProviderListResponse(items=page, total=total, next_cursor=next_cursor)


@router.get(
    "/providers/{provider_id}",
    response_model=ProviderSummary,
    summary="Get a medical professional",
    tags=["Providers"],
)
def get_provider(provider_id: str, repository: Repository, user: DashboardUser) -> ProviderSummary:
    provider = repository.get_provider(provider_id)
    if tenant_scope(user) is not None and provider.organization_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This provider is outside your tenant scope")
    return provider


@router.post(
    "/providers/{provider_id}/subscription/renew",
    response_model=SubscriptionRenewalResponse,
    summary="Renew a provider subscription",
    tags=["Providers", "Subscriptions"],
)
def renew_provider_subscription(
    provider_id: str,
    payload: SubscriptionRenewalRequest,
    user: DashboardUser,
    repository: Repository,
) -> SubscriptionRenewalResponse:
    provider = repository.get_provider(provider_id)
    if tenant_scope(user) is not None and provider.organization_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This provider is outside your tenant scope")
    return repository.renew_subscription(provider_id, payload.duration_years, user.login)


@router.get(
    "/providers/{provider_id}/dashboard",
    response_model=ScopedDashboardResponse,
    summary="Get provider-scoped statistics",
    description="Replaces the legacy associated-tenant provider statistics endpoints.",
    tags=["Providers"],
)
def get_provider_dashboard(provider_id: str, service: Service, report_range: ReportRange, repository: Repository, user: DashboardUser) -> ScopedDashboardResponse:
    provider = repository.get_provider(provider_id)
    if tenant_scope(user) is not None and provider.organization_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This provider is outside your tenant scope")
    return service.provider_dashboard(provider_id, report_range)


@router.get(
    "/locations",
    response_model=LocationListResponse,
    summary="List organization map points",
    tags=["Locations"],
)
def list_locations(repository: Repository, user: DashboardUser) -> LocationListResponse:
    items = repository.list_locations()
    if tenant_scope(user) is not None:
        items = [item for item in items if item.organization_id == user.tenant_id]
    return LocationListResponse(items=items, total=len(items))


@router.get(
    "/operations/overview",
    response_model=OperationsOverviewResponse,
    summary="Get pipeline, backup, subscription, onboarding, feedback, and data-quality health",
    tags=["Operations"],
)
def get_operations_overview(service: Service, report_range: ReportRange, user: DashboardUser) -> OperationsOverviewResponse:
    require_superadmin(user)
    return service.operations(report_range)


@router.post(
    "/reports/summary",
    response_model=SummaryExportAcceptedResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and email a patient summary export",
    description="Returns success only after the selected organizations' patient report has been accepted by the mail server.",
    tags=["Reports"],
)
def export_summary(
    payload: SummaryExportRequest,
    user: DashboardUser,
    repository: Repository,
    exporter: ReportExporter,
) -> SummaryExportAcceptedResponse:
    if payload.date_from > payload.date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="date_from must be on or before date_to")
    selected_ids = list(dict.fromkeys(payload.organization_ids))
    if tenant_scope(user) is not None and any(item != user.tenant_id for item in selected_ids):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The export contains an organization outside your tenant scope")
    known_ids = {organization.id for organization in repository.list_organizations()}
    if any(organization_id not in known_ids for organization_id in selected_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="One or more organizations are invalid")
    if "@" not in user.login:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The signed-in account has no report email address")
    try:
        exporter.enqueue(selected_ids, user.login, payload.date_from, payload.date_to, payload.selected_date)
    except ReportExportUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Report export is temporarily unavailable") from error
    return SummaryExportAcceptedResponse(status="delivered", organization_count=len(selected_ids))


@router.post(
    "/onboarding/organizations",
    response_model=OnboardingAcceptedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
    description="Creates an organization in the configured dashboard data store.",
    tags=["Onboarding"],
)
def onboard_organization(payload: OrganizationCreateRequest, request: Request, user: DashboardUser, repository: Repository) -> OnboardingAcceptedResponse:
    require_superadmin(user)
    if any(item.name.casefold() == payload.name.casefold() for item in repository.list_organizations()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An organization with this name already exists")
    return repository.accept_organization(payload, user.login, request.headers.get("authorization", ""))


@router.post(
    "/onboarding/providers",
    response_model=OnboardingAcceptedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite and onboard a provider",
    description="Creates the provider under the selected organization and starts the selected subscription.",
    tags=["Onboarding"],
)
def onboard_provider(payload: ProviderCreateRequest, request: Request, user: DashboardUser, repository: Repository) -> OnboardingAcceptedResponse:
    require_tenant(user, payload.tenant_id)
    if repository.provider_login_exists(payload.login):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A provider with this login already exists")
    return repository.accept_provider(payload, user.login, request.headers.get("authorization", ""))
