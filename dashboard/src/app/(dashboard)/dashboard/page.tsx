"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Memory, type Stats } from "@/lib/api";
import { MemoryCard } from "@/components/memory-card";
import { MemoryDetailPanel } from "@/components/memory-detail-panel";
import { ClaimBanner } from "@/components/claim-banner";
import { OnboardingModal } from "@/components/onboarding-modal";

export default function TimelinePage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Memory | null>(null);

  const fetchData = useCallback(() => {
    Promise.all([api.memories(100), api.stats()])
      .then(([memRes, statsRes]) => {
        setMemories(memRes.memories);
        setStats(statsRes);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleForget = async (id: string) => {
    try {
      await api.forget(id, "deleted from timeline");
      setMemories((prev) => prev.filter((m) => m.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch {}
  };

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <OnboardingModal onComplete={fetchData} />
      <ClaimBanner />
      <div className="flex items-center justify-between mb-10">
        <div>
          <h2 className="text-[20px] font-semibold tracking-tight">Timeline</h2>
          <p className="text-[14px] mt-1" style={{ color: "var(--muted)" }}>
            {stats?.total || 0} memories across{" "}
            {Object.keys(stats?.by_gate || {}).length} gates
          </p>
        </div>
        {stats && stats.total > 0 && <GateBar stats={stats} />}
      </div>

      {memories.length === 0 ? (
        <Empty />
      ) : (
        <div className="flex gap-6">
          <div className="max-w-[640px] flex-1 min-w-0">
            {memories.map((m) => (
              <MemoryCard
                key={m.id}
                memory={m}
                onClick={setSelected}
                onForget={handleForget}
              />
            ))}
          </div>
          {selected && (
            <MemoryDetailPanel
              memory={selected}
              onClose={() => setSelected(null)}
              onForget={(id) => {
                setMemories((prev) => prev.filter((m) => m.id !== id));
              }}
              onUpdate={(id, updates) => {
                setMemories((prev) =>
                  prev.map((m) =>
                    m.id === id ? { ...m, ...updates } : m
                  )
                );
                setSelected((s) =>
                  s?.id === id ? { ...s, ...updates } : s
                );
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}

function GateBar({ stats }: { stats: Stats }) {
  const gates = Object.entries(stats.by_gate);
  const total = stats.total || 1;
  return (
    <div className="flex items-center gap-3">
      <div
        className="flex h-1.5 w-40 rounded-full overflow-hidden"
        style={{ background: "var(--warm-paper)" }}
      >
        {gates.map(([gate, count]) => (
          <div
            key={gate}
            style={{
              width: `${(count / total) * 100}%`,
              background: `var(--gate-${gate})`,
            }}
          />
        ))}
      </div>
      <span
        className="text-[12px] tabular-nums"
        style={{ color: "var(--dust)" }}
      >
        {stats.total}
      </span>
    </div>
  );
}

function Loading() {
  return (
    <div
      className="flex items-center justify-center h-64"
      style={{ animation: "drift-up 140ms ease" }}
    >
      <div className="flex flex-col items-center gap-3">
        <div
          className="w-5 h-5 rounded-full border-2 animate-spin"
          style={{
            borderColor: "var(--border)",
            borderTopColor: "var(--accent)",
          }}
        />
        <p className="text-[14px]" style={{ color: "var(--muted)" }}>
          Loading memories...
        </p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  const isCloud = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

  return (
    <div className="max-w-md mx-auto mt-24">
      <div
        className="rounded-[var(--radius)] p-6"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border-light)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        {isCloud ? (
          <>
            <h3 className="text-[16px] font-semibold mb-2">
              Something went wrong
            </h3>
            <p className="text-[14px] leading-[1.6] mb-4" style={{ color: "var(--sage)" }}>
              We couldn&apos;t load your memories. This is usually temporary.
              Try refreshing the page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-[var(--radius)] text-[14px] font-medium"
              style={{
                background: "var(--accent)",
                color: "#fff",
              }}
            >
              Refresh
            </button>
          </>
        ) : (
          <>
            <h3 className="text-[16px] font-semibold mb-2">
              Can&apos;t reach the backend
            </h3>
            <p className="text-[14px] leading-[1.6] mb-4" style={{ color: "var(--sage)" }}>
              The dashboard needs the CMK API server running to display your
              memories. This usually means the backend isn&apos;t started yet.
            </p>

            <p
              className="text-[13px] font-medium mb-2"
              style={{ color: "var(--sage)" }}
            >
              Run this in your terminal:
            </p>
            <div
              className="rounded-[var(--radius-sm)] px-3.5 py-2.5 mb-4 font-mono text-[13px]"
              style={{ background: "var(--code-bg)", color: "var(--code-fg)" }}
            >
              cmk serve --port 7749
            </div>

            <p
              className="text-[13px] leading-[1.6] mb-4"
              style={{ color: "var(--dust)" }}
            >
              Then refresh this page. If you&apos;re still stuck, make sure CMK is
              installed (<code className="font-mono">uv tool install claude-memory-kit</code>) and
              check the{" "}
              <a
                href="https://github.com/thierrydamiba/claude-memory#faq"
                className="underline underline-offset-2"
                style={{ color: "var(--accent)" }}
              >
                FAQ
              </a>
              .
            </p>
          </>
        )}

        <details className="text-[12px] mt-4" style={{ color: "var(--dust)" }}>
          <summary className="cursor-pointer hover:underline">
            Error details
          </summary>
          <pre className="mt-2 font-mono whitespace-pre-wrap break-all">
            {message}
          </pre>
        </details>
      </div>
    </div>
  );
}

function Empty() {
  return (
    <div
      className="flex flex-col items-center justify-center h-64 gap-3"
      style={{ animation: "drift-up 140ms ease" }}
    >
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
        style={{ background: "var(--surface-hover)", color: "var(--muted)" }}
      >
        &#9671;
      </div>
      <div className="text-center">
        <p
          className="text-[16px] font-medium"
          style={{ color: "var(--muted)", fontFamily: "var(--font-serif)" }}
        >
          No memories yet
        </p>
        <p className="text-[13px] mt-1" style={{ color: "var(--dust)" }}>
          Start a Claude session with CMK connected and memories will appear here.
        </p>
      </div>
    </div>
  );
}
