import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import type { ReportingRange } from "@/lib/dashboard-contract";
import { authCookieNames } from "@/services/firebase-auth.server";
import { DashboardApiUnauthorizedError, exportDashboardSummary } from "@/services/dashboard-api.server";

const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const headers = { "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'" };

function validPayload(value: unknown): value is { organizationIds: string[]; range: ReportingRange } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const ids = Reflect.get(value, "organizationIds");
  const range = Reflect.get(value, "range");
  if (!Array.isArray(ids) || ids.length < 1 || ids.length > 100 || !ids.every((id) => typeof id === "string" && id.length > 0)) return false;
  if (typeof range !== "object" || range === null || Array.isArray(range)) return false;
  const dateFrom = Reflect.get(range, "dateFrom");
  const dateTo = Reflect.get(range, "dateTo");
  return typeof dateFrom === "string" && typeof dateTo === "string"
    && datePattern.test(dateFrom) && datePattern.test(dateTo) && dateFrom <= dateTo;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const idToken = request.cookies.get(authCookieNames.access)?.value;
  if (!idToken) return NextResponse.json({ code: "authentication_required" }, { status: 401, headers });
  let payload: unknown;
  try { payload = await request.json(); } catch { payload = null; }
  if (!validPayload(payload)) return NextResponse.json({ code: "invalid_export_request" }, { status: 400, headers });
  try {
    await exportDashboardSummary([...new Set(payload.organizationIds)], payload.range, idToken);
    return NextResponse.json({ status: "delivered" }, { status: 200, headers });
  } catch (error: unknown) {
    if (error instanceof DashboardApiUnauthorizedError) {
      const response = NextResponse.json({ code: error.status === 403 ? "access_denied" : "authentication_required" }, { status: error.status, headers });
      if (error.status === 401) response.cookies.delete(authCookieNames.access);
      return response;
    }
    return NextResponse.json({ code: "export_unavailable" }, { status: 503, headers });
  }
}
