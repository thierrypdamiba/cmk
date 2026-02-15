"use client";

import { useState } from "react";
import Link from "next/link";

const FEATURES = [
  { label: "5 memory gates", detail: "behavioral, relational, epistemic, promissory, correction" },
  { label: "Local or cloud", detail: "SQLite locally, or sync across devices with an account" },
  { label: "MCP native", detail: "works with any MCP-compatible client" },
];

export function Hero() {
  const [copied, setCopied] = useState(false);

  const installCmd = "uv tool install claude-memory-kit";

  function handleCopy() {
    navigator.clipboard.writeText(installCmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section className="max-w-6xl mx-auto px-6 pt-28 pb-24">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        {/* Left: copy */}
        <div>
          <h1
            className="text-[48px] md:text-[64px] font-normal tracking-tight leading-[1.0] mb-6"
            style={{
              fontFamily: "var(--font-serif)",
              animation: "drift-up 400ms ease 50ms both",
            }}
          >
            Persistent memory
            <br />
            for Claude.
          </h1>

          <p
            className="text-[18px] leading-[1.6] mb-10 max-w-lg"
            style={{
              color: "var(--muted)",
              animation: "drift-up 400ms ease 100ms both",
            }}
          >
            Claude forgets everything between sessions. CMK fixes that.
            Your preferences, decisions, and context persist across
            every conversation.
          </p>

          <div
            className="flex flex-col sm:flex-row items-start gap-3"
            style={{ animation: "drift-up 400ms ease 150ms both" }}
          >
            <Link
              href="/sign-up"
              className="px-6 py-3 rounded-[var(--radius)] text-[15px] font-medium"
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
              className="px-6 py-3 rounded-[var(--radius)] text-[15px] font-medium"
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
        </div>

        {/* Right: install card */}
        <div style={{ animation: "drift-up 500ms ease 200ms both" }}>
          <div
            className="rounded-[var(--radius-lg)] overflow-hidden"
            style={{
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-md)",
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
                quickstart
              </span>
            </div>

            {/* Terminal body */}
            <div
              className="px-5 py-5 font-mono text-[13px] leading-[1.8]"
              style={{ background: "var(--code-bg)", color: "var(--code-fg)" }}
            >
              {/* Step 1: install */}
              <div style={{ color: "rgba(255,255,255,0.35)" }}># install</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <span style={{ color: "#22c55e" }}>$</span>{" "}
                  <span>{installCmd}</span>
                </div>
                <button
                  onClick={handleCopy}
                  className="shrink-0 px-2 py-1 rounded text-[11px]"
                  style={{
                    background: "rgba(255,255,255,0.08)",
                    color: "rgba(255,255,255,0.5)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    cursor: "pointer",
                    transition: "all 140ms ease",
                  }}
                >
                  {copied ? "copied" : "copy"}
                </button>
              </div>

              {/* Step 2: connect */}
              <div className="mt-4" style={{ color: "rgba(255,255,255,0.35)" }}>
                # connect to your account (get key at cmk.dev/dashboard/setup)
              </div>
              <div>
                <span style={{ color: "#22c55e" }}>$</span>{" "}
                <span>cmk init</span>{" "}
                <span style={{ color: "rgba(255,255,255,0.35)" }}>your-api-key</span>
              </div>

              {/* Step 3: use */}
              <div className="mt-4" style={{ color: "rgba(255,255,255,0.35)" }}>
                # or just run locally, no account needed
              </div>
              <div>
                <span style={{ color: "#22c55e" }}>$</span>{" "}
                <span>claude</span>{" "}
                <span style={{ color: "rgba(255,255,255,0.35)" }}>
                  # CMK auto-activates as MCP server
                </span>
              </div>

              {/* Demo */}
              <div className="mt-5 pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                <div>
                  <span style={{ color: "#60a5fa" }}>you:</span>{" "}
                  I use tabs, not spaces. Deploy target is always Render.
                </div>
                <div className="mt-1">
                  <span style={{ color: "#a78bfa" }}>claude:</span>{" "}
                  Noted. I&apos;ll remember both preferences.
                </div>
                <div className="mt-3" style={{ color: "rgba(255,255,255,0.25)" }}>
                  ── next session ──
                </div>
                <div className="mt-1">
                  <span style={{ color: "#60a5fa" }}>you:</span>{" "}
                  Set up the project config.
                </div>
                <div className="mt-1">
                  <span style={{ color: "#a78bfa" }}>claude:</span>{" "}
                  Done. Used tabs for indentation and added render.yaml.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Feature strip */}
      <div
        className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-16"
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
