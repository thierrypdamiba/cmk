"use client";

import Link from "next/link";

const INSTALL_CMD = "npx cmk init";

const FEATURES = [
  { label: "5 memory gates", detail: "behavioral, relational, epistemic, promissory, correction" },
  { label: "Local-first", detail: "SQLite + vector search on your machine" },
  { label: "MCP native", detail: "works with any MCP-compatible client" },
];

export function Hero() {
  return (
    <section className="max-w-5xl mx-auto px-6 pt-28 pb-24">
      {/* Badge */}
      <div
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-medium mb-8"
        style={{
          background: "var(--warm-paper)",
          color: "var(--muted)",
          border: "1px solid var(--border-light)",
          animation: "drift-up 300ms ease both",
        }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--gate-promissory)" }}
        />
        Now in public beta
      </div>

      {/* Headline */}
      <h1
        className="text-[48px] md:text-[72px] font-normal tracking-tight leading-[1.0] mb-6"
        style={{
          fontFamily: "var(--font-serif)",
          animation: "drift-up 400ms ease 50ms both",
        }}
      >
        Persistent memory
        <br />
        for Claude.
      </h1>

      {/* Subhead */}
      <p
        className="text-[18px] md:text-[20px] leading-[1.6] mb-12 max-w-2xl"
        style={{
          color: "var(--muted)",
          animation: "drift-up 400ms ease 100ms both",
        }}
      >
        Claude forgets everything between sessions. CMK fixes that. Your preferences,
        decisions, and context persist across every conversation, automatically.
      </p>

      {/* CTAs */}
      <div
        className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-16"
        style={{ animation: "drift-up 400ms ease 150ms both" }}
      >
        <Link
          href="/sign-up"
          className="px-7 py-3.5 rounded-[var(--radius)] text-[15px] font-medium"
          style={{
            background: "var(--foreground)",
            color: "var(--background)",
            transition: "opacity 140ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.opacity = "0.85";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.opacity = "1";
          }}
        >
          Get started free
        </Link>
        <Link
          href="/docs"
          className="px-7 py-3.5 rounded-[var(--radius)] text-[15px] font-medium"
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            color: "var(--foreground)",
            transition: "background 140ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--surface-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          Read the docs
        </Link>
      </div>

      {/* Terminal card */}
      <div
        className="rounded-[var(--radius-lg)] overflow-hidden"
        style={{
          border: "1px solid var(--border)",
          boxShadow: "var(--shadow-md)",
          animation: "drift-up 500ms ease 200ms both",
        }}
      >
        {/* Terminal header */}
        <div
          className="flex items-center gap-2 px-4 py-3"
          style={{
            background: "var(--code-bg)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#ef4444" }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#eab308" }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#22c55e" }} />
          </div>
          <span
            className="ml-2 text-[12px] font-mono"
            style={{ color: "rgba(255,255,255,0.35)" }}
          >
            terminal
          </span>
        </div>

        {/* Terminal body */}
        <div
          className="px-5 py-5 font-mono text-[13px] md:text-[14px] leading-[1.8]"
          style={{ background: "var(--code-bg)", color: "var(--code-fg)" }}
        >
          <div>
            <span style={{ color: "#22c55e" }}>$</span>{" "}
            <span style={{ color: "#e7e5e4" }}>{INSTALL_CMD}</span>
          </div>
          <div style={{ color: "rgba(255,255,255,0.45)" }}>
            Setting up Claude Memory Kit...
          </div>
          <div style={{ color: "rgba(255,255,255,0.45)" }}>
            Created memory store at ~/.claude-memory/store
          </div>
          <div style={{ color: "rgba(255,255,255,0.45)" }}>
            MCP server configured.
          </div>
          <div className="mt-3">
            <span style={{ color: "#22c55e" }}>$</span>{" "}
            <span style={{ color: "#e7e5e4" }}>claude</span>
          </div>
          <div className="mt-1">
            <span style={{ color: "#60a5fa" }}>you:</span>{" "}
            I always use tabs, not spaces. And my deploy target is Render.
          </div>
          <div className="mt-1">
            <span style={{ color: "#a78bfa" }}>claude:</span>{" "}
            Noted. I&apos;ll remember both preferences.{" "}
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px]"
              style={{ background: "rgba(5, 150, 105, 0.15)", color: "#34d399" }}
            >
              2 memories saved
            </span>
          </div>
          <div className="mt-3" style={{ color: "rgba(255,255,255,0.25)" }}>
            ── next day ──
          </div>
          <div className="mt-1">
            <span style={{ color: "#60a5fa" }}>you:</span>{" "}
            Set up the project config.
          </div>
          <div className="mt-1">
            <span style={{ color: "#a78bfa" }}>claude:</span>{" "}
            Done. Used tabs for indentation, added render.yaml for deployment.{" "}
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px]"
              style={{ background: "rgba(5, 150, 105, 0.15)", color: "#34d399" }}
            >
              recalled
            </span>
          </div>
        </div>
      </div>

      {/* Feature strip */}
      <div
        className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-10"
        style={{ animation: "drift-up 500ms ease 300ms both" }}
      >
        {FEATURES.map((f) => (
          <div
            key={f.label}
            className="px-5 py-4 rounded-[var(--radius)]"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border-light)",
            }}
          >
            <div
              className="text-[14px] font-medium mb-1"
              style={{ color: "var(--foreground)" }}
            >
              {f.label}
            </div>
            <div
              className="text-[13px]"
              style={{ color: "var(--muted)" }}
            >
              {f.detail}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
