import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authCookieNames } from "@/services/firebase-auth.server";
import { createDashboardOrganization, DashboardApiUnauthorizedError, DashboardApiUnavailableError } from "@/services/dashboard-api.server";

const headers = { "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'" };

export async function POST(request: NextRequest): Promise<NextResponse> {
  const accessToken = request.cookies.get(authCookieNames.access)?.value;
  if (!accessToken) return NextResponse.json({ code: "authentication_required" }, { status: 401, headers });
  let payload: unknown;
  try { payload = await request.json(); } catch { return NextResponse.json({ code: "invalid_request" }, { status: 400, headers }); }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) return NextResponse.json({ code: "invalid_request" }, { status: 400, headers });
  try {
    const result = await createDashboardOrganization(payload, accessToken);
    return NextResponse.json(result, { status: 201, headers });
  } catch (error: unknown) {
    if (error instanceof DashboardApiUnauthorizedError) return NextResponse.json({ code: "authentication_required" }, { status: error.status, headers });
    if (error instanceof DashboardApiUnavailableError && [400, 409, 422].includes(error.status)) return NextResponse.json({ code: "organization_creation_rejected" }, { status: error.status, headers });
    return NextResponse.json({ code: "organization_creation_failed" }, { status: 503, headers });
  }
}
