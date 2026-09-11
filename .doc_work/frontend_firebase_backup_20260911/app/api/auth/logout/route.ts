import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authCookieNames, secureCookie } from "@/services/firebase-auth.server";

function clearAuthenticationCookies(response: NextResponse): void {
  response.cookies.set(authCookieNames.access, "", { httpOnly: true, secure: secureCookie(), sameSite: "lax", path: "/", maxAge: 0 });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const response = NextResponse.redirect(new URL("/", request.url), 303);
  clearAuthenticationCookies(response);
  response.headers.set("Cache-Control", "no-store");
  return response;
}
