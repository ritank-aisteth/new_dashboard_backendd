import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authCookieNames } from "@/services/firebase-auth.server";
import { DashboardApiUnauthorizedError, renewProviderSubscription } from "@/services/dashboard-api.server";

const headers = { "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'" };

function validPayload(value: unknown): value is { providerId: string; durationYears: 1 | 3 } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const providerId = Reflect.get(value, "providerId");
  const durationYears = Reflect.get(value, "durationYears");
  return typeof providerId === "string" && providerId.length > 0 && (durationYears === 1 || durationYears === 3);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const idToken = request.cookies.get(authCookieNames.access)?.value;
  if (!idToken) return NextResponse.json({ code: "authentication_required" }, { status: 401, headers });
  let payload: unknown;
  try { payload = await request.json(); } catch { payload = null; }
  if (!validPayload(payload)) return NextResponse.json({ code: "invalid_renewal_request" }, { status: 400, headers });
  try {
    await renewProviderSubscription(payload.providerId, payload.durationYears, idToken);
    return NextResponse.json({ status: "renewed" }, { headers });
  } catch (error: unknown) {
    if (error instanceof DashboardApiUnauthorizedError) return NextResponse.json({ code: "access_denied" }, { status: error.status, headers });
    return NextResponse.json({ code: "renewal_unavailable" }, { status: 503, headers });
  }
}
