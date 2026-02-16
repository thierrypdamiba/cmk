import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";
  if (!authEnabled) return NextResponse.next();

  const { pathname } = request.nextUrl;

  // Public routes that don't require auth
  const publicPaths = [
    "/",
    "/home",
    "/product",
    "/memory-model",
    "/docs",
    "/security",
    "/sign-in",
    "/sign-up",
    "/sign-out",
    "/api/auth",
    "/api/v1/synthesize",
  ];
  const isPublic = publicPaths.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
  if (isPublic) return NextResponse.next();

  // Allow dashboard pages through (auth check happens client-side)
  if (pathname.startsWith("/dashboard")) return NextResponse.next();

  // Check for session cookie (BetterAuth default name)
  const sessionCookie =
    request.cookies.get("better-auth.session_token") ||
    request.cookies.get("__Secure-better-auth.session_token");

  if (!sessionCookie) {
    // Redirect signed-in check: if on landing page with session, go to dashboard
    return NextResponse.next();
  }

  // Redirect signed-in users from landing page to dashboard
  if (pathname === "/") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
