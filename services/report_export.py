"""Generate and deliver dashboard summary exports with verified completion."""

import os
from datetime import date

from .local_report_worker import generate_and_email_summary


class ReportExportUnavailableError(RuntimeError):
    """Raised when report generation or email delivery fails."""


class SummaryReportExporter:
    def enqueue(
        self,
        organization_ids: list[str],
        email: str,
        date_from: date,
        date_to: date,
        selected_date: str,
    ) -> str:
        del selected_date
        if not os.getenv("LEGACY_DASHBOARD_CONFIG_PATH", "").strip():
            raise ReportExportUnavailableError("Local report delivery is not configured")
        try:
            generate_and_email_summary(organization_ids, email, date_from, date_to)
        except Exception as error:
            raise ReportExportUnavailableError("Report generation or email delivery failed") from error
        return "delivered"
