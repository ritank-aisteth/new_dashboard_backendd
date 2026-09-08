"""Typed FastAPI dependencies shared by dashboard routes."""

import os
from datetime import date, timedelta
from typing import Annotated

from fastapi import HTTPException, Query, status

from schemas import DateRange
from services import (
    ConfiguredDashboardRepository,
    ConfiguredDashboardService,
    DashboardService,
    DynamoDBGateway,
    ElasticsearchGateway,
    LegacyDashboardGateway,
    MockDashboardRepository,
    SummaryReportExporter,
)
from settings import load_settings

DATA_MODE = os.getenv("DASHBOARD_DATA_MODE", "configured").casefold()

if DATA_MODE == "synthetic":
    repository = MockDashboardRepository()
    dashboard_service: DashboardService = DashboardService(repository)
    INTEGRATION_MODE = "synthetic-memory-only"
elif DATA_MODE == "configured":
    settings = load_settings()
    gateway = ElasticsearchGateway(settings)
    dynamodb = DynamoDBGateway(settings)
    legacy_writer = LegacyDashboardGateway()
    repository = ConfiguredDashboardRepository(gateway, dynamodb, legacy_writer)
    dashboard_service = ConfiguredDashboardService(repository, gateway)
    INTEGRATION_MODE = "configured-elasticsearch"
else:
    raise ValueError("DASHBOARD_DATA_MODE must be either 'configured' or 'synthetic'")


def get_repository() -> MockDashboardRepository:
    return repository


def get_dashboard_service() -> DashboardService:
    return dashboard_service


def get_summary_report_exporter() -> SummaryReportExporter:
    return SummaryReportExporter()


def resolve_date_range(
    date_from: Annotated[date | None, Query(description="Inclusive start date in YYYY-MM-DD format")] = None,
    date_to: Annotated[date | None, Query(description="Inclusive end date in YYYY-MM-DD format")] = None,
    all_time: Annotated[bool, Query(description="Allow the dashboard's full historical reporting window")] = False,
) -> DateRange:
    resolved_to = date_to or date.today()
    resolved_from = date(2018, 1, 1) if all_time else date_from or (resolved_to - timedelta(days=180))
    if resolved_from > resolved_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="date_from must be on or before date_to")
    if not all_time and (resolved_to - resolved_from).days > 730:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="date range cannot exceed 730 days")
    return DateRange(date_from=resolved_from, date_to=resolved_to)
