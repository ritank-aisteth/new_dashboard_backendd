import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authCookieNames } from "@/services/firebase-auth.server";
import { DashboardApiUnauthorizedError, getDashboardIdentity } from "@/services/dashboard-api.server";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const idToken = request.cookies.get(authCookieNames.access)?.value;
  if (!idToken) return NextResponse.json({ authenticated: false }, { headers: { "Cache-Control": "no-store" } });
  try {
    return NextResponse.json(
      { authenticated: true, user: await getDashboardIdentity(idToken) },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error: unknown) {
    const status = error instanceof DashboardApiUnauthorizedError ? error.status : 503;
    const response = NextResponse.json({ authenticated: false }, { status, headers: { "Cache-Control": "no-store" } });
    if (status === 401) response.cookies.delete(authCookieNames.access);
    return response;
  }
}
