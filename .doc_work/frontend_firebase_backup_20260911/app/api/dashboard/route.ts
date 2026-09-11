import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import type { ReportingRange } from "@/lib/dashboard-contract";
import { authCookieNames } from "@/services/firebase-auth.server";
import { DashboardApiUnauthorizedError, DashboardApiUnavailableError, getDashboardSnapshot } from "@/services/dashboard-api.server";

const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const apiHeaders = {
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
};

function validDate(value: string | null): value is string {
  if (value === null || !datePattern.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const accessToken = request.cookies.get(authCookieNames.access)?.value;
  if (!accessToken) {
    return NextResponse.json({ code: "authentication_required", message: "Sign in to continue" }, { status: 401, headers: apiHeaders });
  }
  const query = new URL(request.url).searchParams;
  const dateFrom = query.get("date_from");
  const dateTo = query.get("date_to");
  if (!validDate(dateFrom) || !validDate(dateTo) || dateFrom > dateTo) {
    return NextResponse.json({ code: "invalid_date_range", message: "Select a valid reporting period" }, { status: 400, headers: apiHeaders });
  }
  const range: ReportingRange = { dateFrom, dateTo };
  try {
    const response = NextResponse.json(await getDashboardSnapshot(range, accessToken));
    Object.entries(apiHeaders).forEach(([key, value]) => response.headers.set(key, value));
    return response;
  } catch (error: unknown) {
    if (error instanceof DashboardApiUnauthorizedError) {
      const response = NextResponse.json(
        { code: error.status === 403 ? "access_denied" : "authentication_required", message: error.status === 403 ? "You do not have dashboard access" : "Sign in to continue" },
        { status: error.status, headers: apiHeaders },
      );
      if (error.status === 401) response.cookies.delete(authCookieNames.access);
      return response;
    }
    const status = error instanceof DashboardApiUnavailableError ? 503 : 500;
    return NextResponse.json(
      { code: "dashboard_unavailable", message: "Dashboard data is temporarily unavailable" },
      { status, headers: apiHeaders },
    );
  }
}
