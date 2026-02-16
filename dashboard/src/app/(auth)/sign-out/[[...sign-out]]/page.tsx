"use client";

import { authClient } from "@/lib/auth-client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SignOutPage() {
  const router = useRouter();

  useEffect(() => {
    authClient.signOut().then(() => {
      router.push("/");
    });
  }, [router]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "#FAF9F7" }}
    >
      <div className="text-center">
        <p
          className="text-[15px]"
          style={{ color: "var(--muted)" }}
        >
          Signing out...
        </p>
      </div>
    </div>
  );
}
