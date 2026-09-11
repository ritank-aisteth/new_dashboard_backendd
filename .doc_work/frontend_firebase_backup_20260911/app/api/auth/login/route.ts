import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// Kept for compatibility with existing bookmarks. Firebase sign-in is rendered
// by the existing application login screen.
export function GET(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/", request.url), 303);
}
