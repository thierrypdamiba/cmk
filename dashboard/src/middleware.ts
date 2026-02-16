import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/home(.*)",
  "/product(.*)",
  "/memory-model(.*)",
  "/docs(.*)",
  "/security(.*)",
  "/dashboard(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/sign-out(.*)",
  "/api/v1/synthesize",
]);

export default clerkMiddleware(async (auth, request) => {
  const hasClerk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!hasClerk) return;

  // Redirect signed-in users from landing page to dashboard
  const { userId } = await auth();
  if (userId && request.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
