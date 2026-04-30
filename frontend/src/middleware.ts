import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const hostname = request.headers.get("host") || "";

  // plaster.qbc.network → rewrite to /plaster
  if (hostname.startsWith("plaster.")) {
    const url = request.nextUrl.clone();
    if (url.pathname === "/") {
      url.pathname = "/plaster";
      return NextResponse.rewrite(url);
    }
    // Allow static assets and API routes through
    if (url.pathname.startsWith("/_next") || url.pathname.startsWith("/api")) {
      return NextResponse.next();
    }
    // Block access to other pages from plaster subdomain
    if (!url.pathname.startsWith("/plaster")) {
      url.pathname = "/plaster";
      return NextResponse.rewrite(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
