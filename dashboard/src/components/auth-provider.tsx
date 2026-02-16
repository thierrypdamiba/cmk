"use client";

import { useEffect } from "react";
import { authClient } from "@/lib/auth-client";
import { setTokenProvider } from "@/lib/api";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    setTokenProvider(async () => {
      try {
        const session = await authClient.getSession();
        return session?.data?.session?.token ?? null;
      } catch {
        return null;
      }
    });
  }, []);

  return <>{children}</>;
}
