"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { api, type SetupInfo, type Memory } from "@/lib/api";

type Step = 1 | 2 | 3 | 4;

export function OnboardingModal({ onComplete }: { onComplete: () => void }) {
  const [show, setShow] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const [setup, setSetup] = useState<SetupInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [firstMemory, setFirstMemory] = useState<Memory | null>(null);
  const [mcpExpanded, setMcpExpanded] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Decide whether to show the modal
  useEffect(() => {
    if (localStorage.getItem("cmk-onboarded")) return;
    api.stats()
      .then((s) => {
        if (s.total === 0) setShow(true);
      })
      .catch(() => {});
  }, []);

  // Auto-generate key when entering step 2
  useEffect(() => {
    if (step !== 2 || setup) return;
    setError(null);
    api.getInitKey()
      .then(setSetup)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to generate key"));
  }, [step, setup]);

  // Poll for first memory on step 3
  const pollForMemory = useCallback(async () => {
    try {
      const res = await api.memories(1);
      if (res.memories.length > 0) {
        setFirstMemory(res.memories[0]);
        setStep(4);
        if (pollRef.current) clearInterval(pollRef.current);
      }
    } catch {}
  }, []);

  useEffect(() => {
    if (step !== 3) return;
    pollForMemory();
    pollRef.current = setInterval(pollForMemory, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [step, pollForMemory]);

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const finish = () => {
    localStorage.setItem("cmk-onboarded", "1");
    setShow(false);
    onComplete();
  };

  const skip = () => {
    localStorage.setItem("cmk-onboarded", "1");
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.4)", animation: "drift-in 200ms ease" }}
    >
      <div
        className="relative w-full max-w-lg mx-4 rounded-[var(--radius-lg)] overflow-hidden"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border-light)",
          boxShadow: "var(--shadow-md)",
          animation: "drift-up 200ms ease",
        }}
      >
        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 pt-6 pb-2">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-full transition-all"
                style={{
                  background:
                    step > s || step === 4
                      ? "var(--success)"
                      : step === s
                        ? "var(--accent)"
                        : "var(--border)",
                }}
              />
              {s < 3 && (
                <div
                  className="w-8 h-px"
                  style={{
                    background: step > s || step === 4 ? "var(--success)" : "var(--border)",
                  }}
                />
              )}
            </div>
          ))}
        </div>

        <div className="px-6 pb-6 pt-2">
          {/* Step 1: Install */}
          {step === 1 && (
            <div style={{ animation: "drift-up 140ms ease" }}>
              <h3 className="text-[18px] font-semibold tracking-tight mb-1">
                Install CMK
              </h3>
              <p className="text-[14px] mb-5" style={{ color: "var(--muted)" }}>
                Claude Memory Kit gives Claude persistent memory across sessions.
              </p>

              <p
                className="text-[13px] font-medium mb-2"
                style={{ color: "var(--muted)" }}
              >
                Run this in your terminal:
              </p>
              <CodeBlock
                code="uv tool install claude-memory-kit"
                onCopy={() => copyText("uv tool install claude-memory-kit", "install")}
                copied={copied === "install"}
              />

              <button
                onClick={() => setStep(2)}
                className="mt-5 w-full py-2.5 rounded-[var(--radius)] text-[14px] font-medium"
                style={{ background: "var(--accent)", color: "#fff" }}
              >
                I&apos;ve installed it
              </button>
            </div>
          )}

          {/* Step 2: Connect */}
          {step === 2 && (
            <div style={{ animation: "drift-up 140ms ease" }}>
              <h3 className="text-[18px] font-semibold tracking-tight mb-1">
                Connect your account
              </h3>
              <p className="text-[14px] mb-5" style={{ color: "var(--muted)" }}>
                Link Claude to your memory with a one-time init command.
              </p>

              {error && (
                <p className="text-[13px] mb-3" style={{ color: "var(--gate-correction)" }}>
                  {error}
                </p>
              )}

              {!setup && !error && (
                <div className="flex items-center gap-2 py-4">
                  <div
                    className="w-4 h-4 rounded-full border-2 animate-spin"
                    style={{
                      borderColor: "var(--border)",
                      borderTopColor: "var(--accent)",
                    }}
                  />
                  <span className="text-[13px]" style={{ color: "var(--muted)" }}>
                    Generating your key...
                  </span>
                </div>
              )}

              {setup && (
                <>
                  <p
                    className="text-[13px] font-medium mb-2"
                    style={{ color: "var(--muted)" }}
                  >
                    Run this in your terminal:
                  </p>
                  <CodeBlock
                    code={setup.command}
                    onCopy={() => copyText(setup.command, "init")}
                    copied={copied === "init"}
                  />

                  <div className="mt-3">
                    <button
                      onClick={() => setMcpExpanded(!mcpExpanded)}
                      className="text-[13px] cursor-pointer hover:underline"
                      style={{ color: "var(--dust)" }}
                    >
                      {mcpExpanded ? "Hide" : "Or add"} MCP config manually
                    </button>
                    {mcpExpanded && (
                      <div className="mt-2">
                        <CodeBlock
                          code={JSON.stringify(setup.mcp_config, null, 2)}
                          onCopy={() =>
                            copyText(JSON.stringify(setup.mcp_config, null, 2), "mcp")
                          }
                          copied={copied === "mcp"}
                        />
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => setStep(3)}
                    className="mt-5 w-full py-2.5 rounded-[var(--radius)] text-[14px] font-medium"
                    style={{ background: "var(--accent)", color: "#fff" }}
                  >
                    I&apos;ve run the command
                  </button>
                </>
              )}
            </div>
          )}

          {/* Step 3: Launch Claude */}
          {step === 3 && (
            <div style={{ animation: "drift-up 140ms ease" }}>
              <h3 className="text-[18px] font-semibold tracking-tight mb-1">
                Launch Claude
              </h3>
              <p className="text-[14px] mb-5" style={{ color: "var(--muted)" }}>
                Open a terminal and start a Claude session. We&apos;ll detect your
                first memory automatically.
              </p>

              <p
                className="text-[13px] font-medium mb-2"
                style={{ color: "var(--muted)" }}
              >
                Start Claude:
              </p>
              <CodeBlock
                code="claude"
                onCopy={() => copyText("claude", "claude")}
                copied={copied === "claude"}
              />

              <p
                className="text-[13px] mt-4 mb-4 leading-[1.6]"
                style={{ color: "var(--muted)" }}
              >
                Try telling Claude:{" "}
                <span
                  className="font-mono text-[12px] px-1.5 py-0.5 rounded"
                  style={{ background: "var(--warm-paper)" }}
                >
                  &quot;Remember that I prefer TypeScript and always use pnpm.&quot;
                </span>
              </p>

              <div
                className="flex items-center gap-3 rounded-[var(--radius)] p-4"
                style={{
                  background: "var(--warm-paper)",
                  border: "1px solid var(--border-light)",
                }}
              >
                <div
                  className="w-4 h-4 rounded-full border-2 animate-spin shrink-0"
                  style={{
                    borderColor: "var(--border)",
                    borderTopColor: "var(--accent)",
                  }}
                />
                <span className="text-[13px]" style={{ color: "var(--muted)" }}>
                  Waiting for your first memory...
                </span>
              </div>

              <button
                onClick={pollForMemory}
                className="mt-3 text-[13px] font-medium underline underline-offset-2"
                style={{ color: "var(--accent)" }}
              >
                Check now
              </button>
            </div>
          )}

          {/* Step 4: Completion */}
          {step === 4 && (
            <div style={{ animation: "drift-up 140ms ease" }}>
              <div className="flex flex-col items-center text-center pt-2 pb-2">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-[18px] mb-4"
                  style={{ background: "var(--success)", color: "#fff" }}
                >
                  &#10003;
                </div>
                <h3 className="text-[18px] font-semibold tracking-tight mb-1">
                  You&apos;re all set
                </h3>
                <p className="text-[14px]" style={{ color: "var(--muted)" }}>
                  Claude now has persistent memory. Here&apos;s what was just stored:
                </p>
              </div>

              {firstMemory && (
                <div
                  className="rounded-[var(--radius)] p-4 mt-4 mb-4"
                  style={{
                    background: "var(--warm-paper)",
                    border: "1px solid var(--border-light)",
                  }}
                >
                  <p
                    className="text-[13px] leading-[1.6]"
                    style={{ color: "var(--foreground)" }}
                  >
                    {firstMemory.content}
                  </p>
                  <p className="text-[11px] mt-2" style={{ color: "var(--dust)" }}>
                    {firstMemory.gate}
                  </p>
                </div>
              )}

              <button
                onClick={finish}
                className="w-full py-2.5 rounded-[var(--radius)] text-[14px] font-medium"
                style={{ background: "var(--accent)", color: "#fff" }}
              >
                Go to timeline
              </button>
            </div>
          )}

          {/* Skip link */}
          {step !== 4 && (
            <button
              onClick={skip}
              className="mt-4 w-full text-center text-[13px]"
              style={{ color: "var(--dust)" }}
            >
              Skip setup
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CodeBlock({
  code,
  onCopy,
  copied,
}: {
  code: string;
  onCopy: () => void;
  copied: boolean;
}) {
  return (
    <div
      className="relative rounded-[var(--radius-sm)] font-mono text-[13px]"
      style={{ background: "var(--code-bg)", color: "var(--code-fg)" }}
    >
      <pre className="p-3.5 pr-16 whitespace-pre-wrap break-all leading-[1.6]">
        {code}
      </pre>
      <button
        onClick={onCopy}
        className="absolute top-2.5 right-2.5 px-2 py-1 rounded text-[12px]"
        style={{
          background: copied ? "rgba(5, 150, 105, 0.3)" : "rgba(255,255,255,0.08)",
          color: copied ? "#6ee7b7" : "var(--code-fg)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
