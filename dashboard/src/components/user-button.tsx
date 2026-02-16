"use client";

import { authClient } from "@/lib/auth-client";
import Link from "next/link";

export function UserButton() {
  const hasAuth = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";
  if (!hasAuth) return null;

  return <AuthAwareButton />;
}

function AuthAwareButton() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) return null;

  if (!session) {
    return (
      <Link
        href="/sign-in"
        className="text-[13px] font-medium px-2.5 py-1 rounded-[var(--radius-sm)]"
        style={{
          color: "var(--accent)",
          background: "rgba(122, 134, 154, 0.08)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(122, 134, 154, 0.14)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "rgba(122, 134, 154, 0.08)";
        }}
      >
        Sign in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-medium"
        style={{
          background: "var(--surface-active)",
          color: "var(--foreground)",
        }}
      >
        {(session.user.name?.[0] || session.user.email?.[0] || "?").toUpperCase()}
      </div>
      <Link
        href="/sign-out"
        className="text-[12px]"
        style={{ color: "var(--muted)" }}
      >
        Sign out
      </Link>
    </div>
  );
}
