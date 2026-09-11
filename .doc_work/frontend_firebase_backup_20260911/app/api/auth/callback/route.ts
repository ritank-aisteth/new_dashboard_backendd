import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// Kept so the old public route does not become a 404 after the provider change.
export function GET(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/", request.url), 303);
}
