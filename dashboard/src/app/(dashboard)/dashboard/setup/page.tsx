"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SetupInfo } from "@/lib/api";

interface CheckState {
  backend: "pending" | "checking" | "ok" | "fail";
  installed: "pending" | "done";
  key: "pending" | "generating" | "done";
  connected: "pending" | "checking" | "ok" | "fail";
  firstMemory: "pending" | "checking" | "ok";
}

export default function SetupPage() {
  const router = useRouter();
  const isCloud = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  useEffect(() => {
    if (isCloud) router.replace("/dashboard");
  }, [isCloud, router]);

  if (isCloud) return null;
  const [setup, setSetup] = useState<SetupInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [checks, setChecks] = useState<CheckState>({
    backend: "pending",
    installed: "pending",
    key: "pending",
    connected: "pending",
    firstMemory: "pending",
  });

  useEffect(() => {
    checkBackend();
  }, []);

  const checkBackend = async () => {
    setChecks((c) => ({ ...c, backend: "checking" }));
    try {
      await api.stats();
      setChecks((c) => ({ ...c, backend: "ok" }));
    } catch {
      setChecks((c) => ({ ...c, backend: "fail" }));
    }
  };

  const markInstalled = () => {
    setChecks((c) => ({ ...c, installed: "done" }));
  };

  const generateKey = async () => {
    setChecks((c) => ({ ...c, key: "generating" }));
    setError(null);
    try {
      const res = await api.getInitKey();
      setSetup(res);
      setChecks((c) => ({ ...c, key: "done" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate key");
      setChecks((c) => ({ ...c, key: "pending" }));
    }
  };

  const checkConnection = async () => {
    setChecks((c) => ({ ...c, connected: "checking" }));
    try {
      await api.stats();
      setChecks((c) => ({ ...c, connected: "ok" }));
      checkFirstMemory();
    } catch {
      setChecks((c) => ({ ...c, connected: "fail" }));
    }
  };

  const checkFirstMemory = async () => {
    setChecks((c) => ({ ...c, firstMemory: "checking" }));
    try {
      const res = await api.memories(1);
      if (res.memories.length > 0) {
        setChecks((c) => ({ ...c, firstMemory: "ok" }));
      }
    } catch {}
  };

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const allDone =
    checks.backend === "ok" &&
    checks.installed === "done" &&
    checks.key === "done" &&
    checks.connected === "ok";

  return (
    <div className="max-w-xl">
      <h2 className="text-[20px] font-semibold tracking-tight mb-1">
        Get started
      </h2>
      <p className="text-[14px] mb-8" style={{ color: "var(--muted)" }}>
        Walk through each step to connect Claude to your memory.
      </p>

      <div className="space-y-2">
        {/* 1. Backend running */}
        <CheckItem
          status={checks.backend}
          title="Backend is running"
          description={
            checks.backend === "ok"
              ? "Connected to CMK API on port 7749."
              : checks.backend === "fail"
                ? "Can't reach the backend."
                : "Checking connection..."
          }
        >
          {checks.backend === "fail" && (
            <div className="mt-3">
              <p className="text-[13px] mb-2" style={{ color: "var(--muted)" }}>
                Start the server in your terminal:
              </p>
              <CodeBlock
                code="cmk serve --port 7749"
                onCopy={() => copyText("cmk serve --port 7749", "serve")}
                copied={copied === "serve"}
              />
              <button
                onClick={checkBackend}
                className="mt-3 text-[13px] font-medium underline underline-offset-2"
                style={{ color: "var(--accent)" }}
              >
                Check again
              </button>
            </div>
          )}
        </CheckItem>

        {/* 2. Install CMK */}
        <CheckItem
          status={checks.installed === "done" ? "ok" : "pending"}
          title="Install CMK"
          description={
            checks.installed === "done"
              ? "CMK is installed."
              : "Install the CLI tool with uv."
          }
        >
          {checks.installed !== "done" && (
            <div className="mt-3">
              <CodeBlock
                code="uv tool install claude-memory-kit"
                onCopy={() =>
                  copyText("uv tool install claude-memory-kit", "install")
                }
                copied={copied === "install"}
              />
              <button
                onClick={markInstalled}
                className="mt-3 text-[13px] font-medium underline underline-offset-2"
                style={{ color: "var(--accent)" }}
              >
                I&apos;ve installed it
              </button>
            </div>
          )}
        </CheckItem>

        {/* 3. Generate API key */}
        <CheckItem
          status={
            checks.key === "done"
              ? "ok"
              : checks.key === "generating"
                ? "checking"
                : "pending"
          }
          title="Connect your account"
          description={
            checks.key === "done"
              ? "API key generated. Run the init command below."
              : "Generate an API key to link Claude to your account."
          }
        >
          {checks.key !== "done" && (
            <div className="mt-3">
              <button
                onClick={generateKey}
                disabled={checks.key === "generating"}
                className="px-4 py-2 rounded-[var(--radius)] text-[14px] font-medium"
                style={{
                  background: "var(--accent)",
                  color: "#fff",
                  opacity: checks.key === "generating" ? 0.6 : 1,
                }}
              >
                {checks.key === "generating"
                  ? "Generating..."
                  : "Generate API key"}
              </button>
              {error && (
                <p
                  className="mt-2 text-[13px]"
                  style={{ color: "var(--gate-correction)" }}
                >
                  {error}
                </p>
              )}
            </div>
          )}
          {checks.key === "done" && setup && (
            <div className="mt-3 space-y-3">
              <div>
                <p
                  className="text-[13px] mb-1.5 font-medium"
                  style={{ color: "var(--muted)" }}
                >
                  Run this in your terminal:
                </p>
                <CodeBlock
                  code={setup.command}
                  onCopy={() => copyText(setup.command, "init")}
                  copied={copied === "init"}
                />
              </div>
              <details className="text-[13px]" style={{ color: "var(--dust)" }}>
                <summary className="cursor-pointer hover:underline">
                  Or add MCP config manually
                </summary>
                <div className="mt-2">
                  <CodeBlock
                    code={JSON.stringify(setup.mcp_config, null, 2)}
                    onCopy={() =>
                      copyText(
                        JSON.stringify(setup.mcp_config, null, 2),
                        "mcp"
                      )
                    }
                    copied={copied === "mcp"}
                  />
                </div>
              </details>
            </div>
          )}
        </CheckItem>

        {/* 4. Verify connection */}
        <CheckItem
          status={
            checks.connected === "ok"
              ? "ok"
              : checks.connected === "checking"
                ? "checking"
                : checks.connected === "fail"
                  ? "fail"
                  : "pending"
          }
          title="Verify it works"
          description={
            checks.connected === "ok"
              ? "Claude is connected to your memory."
              : checks.connected === "fail"
                ? "Connection check failed. Make sure you ran the init command."
                : "Confirm everything is wired up correctly."
          }
        >
          {checks.connected !== "ok" && (
            <div className="mt-3">
              <button
                onClick={checkConnection}
                disabled={checks.connected === "checking"}
                className="px-4 py-2 rounded-[var(--radius)] text-[14px] font-medium"
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  color: "var(--foreground)",
                  opacity: checks.connected === "checking" ? 0.6 : 1,
                }}
              >
                {checks.connected === "checking"
                  ? "Checking..."
                  : "Run connection check"}
              </button>
            </div>
          )}
        </CheckItem>

        {/* 5. First memory */}
        <CheckItem
          status={
            checks.firstMemory === "ok"
              ? "ok"
              : checks.firstMemory === "checking"
                ? "checking"
                : "pending"
          }
          title="Create your first memory"
          description={
            checks.firstMemory === "ok"
              ? "You have memories. You're all set."
              : "Start a conversation with Claude. Memories will appear on the timeline."
          }
        >
          {checks.firstMemory !== "ok" && (
            <div className="mt-3">
              <p
                className="text-[13px] leading-[1.6]"
                style={{ color: "var(--muted)" }}
              >
                Open Claude and say something like: &quot;Remember that I prefer
                TypeScript and always use pnpm.&quot; CMK will store it automatically.
              </p>
              <button
                onClick={checkFirstMemory}
                className="mt-2 text-[13px] font-medium underline underline-offset-2"
                style={{ color: "var(--accent)" }}
              >
                Check for memories
              </button>
            </div>
          )}
        </CheckItem>
      </div>

      {/* Completion */}
      {allDone && (
        <div
          className="rounded-[var(--radius)] p-5 mt-6"
          style={{
            background: "rgba(5, 150, 105, 0.05)",
            border: "1px solid rgba(5, 150, 105, 0.15)",
          }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className="w-5 h-5 rounded-full flex items-center justify-center text-[12px]"
              style={{ background: "var(--success)", color: "#fff" }}
            >
              &#10003;
            </span>
            <p className="text-[15px] font-medium">You&apos;re all set.</p>
          </div>
          <p className="text-[14px] ml-7" style={{ color: "var(--muted)" }}>
            Claude now has persistent memory. Check the{" "}
            <a
              href="/dashboard"
              className="underline underline-offset-2"
              style={{ color: "var(--accent)" }}
            >
              timeline
            </a>{" "}
            to see what Claude remembers.
          </p>
        </div>
      )}
    </div>
  );
}

function CheckItem({
  status,
  title,
  description,
  children,
}: {
  status: "pending" | "checking" | "ok" | "fail";
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  const icon =
    status === "ok"
      ? "\u2713"
      : status === "fail"
        ? "!"
        : status === "checking"
          ? "\u00B7\u00B7"
          : "\u2022";

  const iconBg =
    status === "ok"
      ? "var(--success)"
      : status === "fail"
        ? "var(--gate-correction)"
        : status === "checking"
          ? "var(--accent)"
          : "var(--border)";

  const iconColor =
    status === "ok" || status === "fail" || status === "checking"
      ? "#fff"
      : "var(--sage)";

  return (
    <div
      className="rounded-[var(--radius)] p-4"
      style={{
        background: "var(--surface)",
        border: `1px solid ${status === "fail" ? "rgba(220, 38, 38, 0.15)" : "var(--border-light)"}`,
        boxShadow: "var(--shadow-xs)",
      }}
    >
      <div className="flex items-start gap-3">
        <span
          className="w-5 h-5 rounded-full flex items-center justify-center text-[12px] font-semibold shrink-0 mt-px"
          style={{ background: iconBg, color: iconColor }}
        >
          {status === "checking" ? (
            <span className="animate-spin text-[11px]">&#8635;</span>
          ) : (
            icon
          )}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-medium">{title}</p>
          <p
            className="text-[13px] mt-0.5"
            style={{ color: status === "ok" ? "var(--sage)" : "var(--muted)" }}
          >
            {description}
          </p>
          {children}
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
