import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import type { ReportingRange } from "@/lib/dashboard-contract";
import { authCookieNames } from "@/services/firebase-auth.server";
import { DashboardApiUnauthorizedError, DashboardApiUnavailableError, getScopedDashboardMetrics } from "@/services/dashboard-api.server";

const datePattern=/^\d{4}-\d{2}-\d{2}$/;
const headers={"Cache-Control":"no-store","Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'"};

export async function GET(request:NextRequest):Promise<NextResponse>{
  const token=request.cookies.get(authCookieNames.access)?.value;
  if(!token)return NextResponse.json({code:"authentication_required"},{status:401,headers});
  const query=request.nextUrl.searchParams;
  const kind=query.get("kind"); const id=query.get("id")?.trim(); const dateFrom=query.get("date_from"); const dateTo=query.get("date_to");
  if((kind!=="organization"&&kind!=="provider")||!id||!dateFrom||!dateTo||!datePattern.test(dateFrom)||!datePattern.test(dateTo)||dateFrom>dateTo)return NextResponse.json({code:"invalid_request"},{status:400,headers});
  try{
    const range:ReportingRange={dateFrom,dateTo};
    return NextResponse.json({metrics:await getScopedDashboardMetrics(kind,id,range,token)},{headers});
  }catch(error:unknown){
    if(error instanceof DashboardApiUnauthorizedError)return NextResponse.json({code:error.status===403?"access_denied":"authentication_required"},{status:error.status,headers});
    return NextResponse.json({code:"dashboard_unavailable"},{status:error instanceof DashboardApiUnavailableError?503:500,headers});
  }
}
