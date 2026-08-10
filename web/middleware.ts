import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware(req) {
    const role = req.nextauth.token?.role as string | undefined;
    const sessionTenant = (req.nextauth.token?.tenantId as string | null) || null;
    const path = req.nextUrl.pathname;

    if (path.startsWith("/admin") && role !== "platform_owner") {
      const url = req.nextUrl.clone();
      url.pathname = role === "org_admin" ? "/app" : "/login";
      return NextResponse.redirect(url);
    }

    if (path.startsWith("/app") && role !== "org_admin" && role !== "platform_owner") {
      const url = req.nextUrl.clone();
      url.pathname = "/login";
      return NextResponse.redirect(url);
    }

    // Org admins should not use platform admin shell
    if (path.startsWith("/app") && role === "platform_owner") {
      const url = req.nextUrl.clone();
      url.pathname = "/admin";
      return NextResponse.redirect(url);
    }

    // OR-09: strip query spoofing of a foreign tenant for org admins
    if (role === "org_admin" && path.startsWith("/app")) {
      const spoof =
        req.nextUrl.searchParams.get("tenant_id") ||
        req.nextUrl.searchParams.get("client_id") ||
        req.nextUrl.searchParams.get("tenant");
      if (spoof && sessionTenant && spoof.toLowerCase() !== sessionTenant.toLowerCase()) {
        const url = req.nextUrl.clone();
        url.searchParams.delete("tenant_id");
        url.searchParams.delete("client_id");
        url.searchParams.delete("tenant");
        return NextResponse.redirect(url);
      }
    }

    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        const path = req.nextUrl.pathname;
        if (path.startsWith("/admin") || path.startsWith("/app")) {
          return !!token;
        }
        return true;
      },
    },
  },
);

export const config = {
  matcher: ["/admin/:path*", "/app/:path*"],
};
