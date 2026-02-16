"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function ModeBadge() {
  const [isCloud, setIsCloud] = useState(
    process.env.NEXT_PUBLIC_AUTH_ENABLED === "true"
  );

  useEffect(() => {
    api
      .mode()
      .then((res) => setIsCloud(res.mode === "cloud"))
      .catch(() => {});
  }, []);

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-medium"
      style={{
        background: isCloud
          ? "rgba(37, 99, 235, 0.08)"
          : "rgba(5, 150, 105, 0.08)",
        color: isCloud ? "var(--gate-relational)" : "var(--success)",
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{
          background: isCloud ? "var(--gate-relational)" : "var(--success)",
        }}
      />
      {isCloud ? "Cloud Sync" : "Local"}
    </span>
  );
}
