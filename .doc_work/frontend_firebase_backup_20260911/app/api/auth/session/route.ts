import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authCookieNames, secureCookie } from "@/services/firebase-auth.server";
import { DashboardApiUnauthorizedError, verifyDashboardAccess } from "@/services/dashboard-api.server";

function isTokenPayload(value: unknown): value is { idToken: string } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const token = Reflect.get(value, "idToken");
  return typeof token === "string" && token.length >= 100 && token.length <= 16_384;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return NextResponse.json({ code: "invalid_request", message: "A JSON request is required" }, { status: 415 });
  }
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ code: "invalid_request", message: "Authentication could not be completed" }, { status: 400 });
  }
  if (!isTokenPayload(payload)) {
    return NextResponse.json({ code: "invalid_request", message: "Authentication could not be completed" }, { status: 400 });
  }
  try {
    await verifyDashboardAccess(payload.idToken);
    const response = new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    response.cookies.set(authCookieNames.access, payload.idToken, {
      httpOnly: true,
      secure: secureCookie(),
      sameSite: "lax",
      path: "/",
      maxAge: 3600,
    });
    return response;
  } catch (error: unknown) {
    const status = error instanceof DashboardApiUnauthorizedError ? error.status : 503;
    return NextResponse.json(
      { code: status === 403 ? "access_denied" : "authentication_failed", message: status === 403 ? "Dashboard access is denied" : "Authentication could not be completed" },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  }
}
