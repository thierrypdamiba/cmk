export default function SecurityPage() {
  return (
    <div>
      {/* Hero */}
      <section
        className="max-w-4xl mx-auto px-6 pt-24 pb-16"
        style={{ animation: "drift-up 400ms ease both" }}
      >
        <h1
          className="text-[48px] md:text-[56px] font-normal tracking-tight leading-[1.08] mb-6"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Security and privacy
        </h1>
        <p
          className="text-[18px] leading-[1.65] max-w-2xl"
          style={{ color: "var(--muted)" }}
        >
          CMK is built with a local-first philosophy. Your memories live on
          your machine by default. No data leaves your device unless you
          explicitly configure cloud storage.
        </p>
      </section>

      {/* Local-first architecture */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Local-first by design
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-8"
          style={{ color: "var(--muted)" }}
        >
          Every component of CMK can run entirely on your machine. There are
          no mandatory cloud services, no telemetry, and no analytics.
        </p>

        <div className="space-y-4">
          {LOCAL_FIRST_POINTS.map((point, i) => (
            <div
              key={i}
              className="rounded-[var(--radius)] p-5 pl-7"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderLeft: `3px solid ${point.color}`,
                boxShadow: "var(--shadow-xs)",
                animation: `drift-up 300ms ease ${i * 80}ms both`,
              }}
            >
              <h3
                className="text-[15px] font-semibold tracking-tight mb-1.5"
                style={{ color: "var(--foreground)" }}
              >
                {point.title}
              </h3>
              <p
                className="text-[14px] leading-[1.6]"
                style={{ color: "var(--muted)" }}
              >
                {point.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Data storage */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Data storage
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-8"
          style={{ color: "var(--muted)" }}
        >
          In local mode, all data is stored in a single directory on your
          machine. You control every byte.
        </p>

        <div
          className="rounded-[var(--radius-lg)] overflow-hidden"
          style={{
            background: "var(--code-bg)",
            boxShadow: "var(--shadow-md)",
          }}
        >
          <div
            className="px-4 py-3 text-[12px] font-medium"
            style={{
              color: "rgba(231, 229, 228, 0.5)",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            ~/.cmk/
          </div>
          <pre
            className="p-5 overflow-x-auto text-[13px] leading-[1.7] font-mono"
            style={{ color: "var(--code-fg)" }}
          >
            <code>{`~/.cmk/
  memories.db          # SQLite database (all metadata)
  embeddings/          # Local vector store (fastembed)
  config.toml          # Configuration file
  .env                 # CMK API key (cloud mode only)`}</code>
          </pre>
        </div>

        <div
          className="mt-6 rounded-[var(--radius)] p-5"
          style={{
            background: "var(--warm-paper)",
            border: "1px solid var(--border-light)",
          }}
        >
          <div className="space-y-3">
            <StorageRow
              label="Default location"
              value="~/.cmk/"
            />
            <StorageRow
              label="Database"
              value="Standard SQLite file. Can be opened with any SQLite client."
            />
            <StorageRow
              label="Cloud sync"
              value="Disabled by default. Requires explicit CMK_STORAGE=cloud configuration."
            />
            <StorageRow
              label="Telemetry"
              value="None. Zero network calls in local mode."
            />
          </div>
        </div>
      </section>

      {/* Auth flow */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Authentication
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-8"
          style={{ color: "var(--muted)" }}
        >
          CMK supports two authentication models, both optional. You can run
          without any auth for personal local use.
        </p>

        <div className="grid md:grid-cols-2 gap-5">
          {/* API Keys */}
          <div
            className="rounded-[var(--radius)] p-6"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderTop: "3px solid var(--gate-behavioral)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div className="flex items-center gap-2.5 mb-4">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: "var(--gate-behavioral)" }}
              />
              <h3
                className="text-[17px] font-semibold tracking-tight"
                style={{ color: "var(--foreground)" }}
              >
                API keys
              </h3>
            </div>
            <p
              className="text-[14px] leading-[1.6] mb-4"
              style={{ color: "var(--muted)" }}
            >
              Generate API keys for programmatic access. Keys are hashed
              before storage and only shown once at creation time.
            </p>
            <div className="space-y-2">
              <FeatureRow text="Managed via /api/keys endpoints" />
              <FeatureRow text="Scoped per service or environment" />
              <FeatureRow text="Revocable at any time" />
              <FeatureRow text="No external service required" />
            </div>
          </div>

          {/* BetterAuth */}
          <div
            className="rounded-[var(--radius)] p-6"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderTop: "3px solid var(--gate-relational)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div className="flex items-center gap-2.5 mb-4">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: "var(--gate-relational)" }}
              />
              <h3
                className="text-[17px] font-semibold tracking-tight"
                style={{ color: "var(--foreground)" }}
              >
                BetterAuth (optional)
              </h3>
            </div>
            <p
              className="text-[14px] leading-[1.6] mb-4"
              style={{ color: "var(--muted)" }}
            >
              For the web dashboard, BetterAuth provides self-hosted user
              authentication with social login and session management.
            </p>
            <div className="space-y-2">
              <FeatureRow text="SSO and social login support" />
              <FeatureRow text="Session management" />
              <FeatureRow text="Completely optional for CLI usage" />
              <FeatureRow text="Dashboard-only feature" />
            </div>
          </div>
        </div>
      </section>

      {/* Data export and deletion */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Data export and deletion
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-8"
          style={{ color: "var(--muted)" }}
        >
          You have full control over your data at all times. Export
          everything, delete selectively, or wipe the entire store.
        </p>

        <div
          className="rounded-[var(--radius-lg)] overflow-hidden overflow-x-auto"
          style={{
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  background: "var(--warm-paper)",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <th
                  className="text-left px-5 py-3.5 text-[13px] font-semibold"
                  style={{ color: "var(--foreground)" }}
                >
                  Action
                </th>
                <th
                  className="text-left px-5 py-3.5 text-[13px] font-semibold"
                  style={{ color: "var(--foreground)" }}
                >
                  Method
                </th>
                <th
                  className="text-left px-5 py-3.5 text-[13px] font-semibold"
                  style={{ color: "var(--foreground)" }}
                >
                  Notes
                </th>
              </tr>
            </thead>
            <tbody>
              {DATA_ACTIONS.map((action, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom:
                      i < DATA_ACTIONS.length - 1
                        ? "1px solid var(--border-light)"
                        : "none",
                    background:
                      i % 2 === 0 ? "var(--surface)" : "var(--background)",
                  }}
                >
                  <td
                    className="px-5 py-3 text-[13px] font-medium"
                    style={{ color: "var(--foreground)" }}
                  >
                    {action.action}
                  </td>
                  <td className="px-5 py-3">
                    <code
                      className="text-[12px] font-mono"
                      style={{
                        background: "var(--warm-paper)",
                        padding: "1px 5px",
                        borderRadius: 4,
                        color: "var(--foreground)",
                      }}
                    >
                      {action.method}
                    </code>
                  </td>
                  <td
                    className="px-5 py-3 text-[13px]"
                    style={{ color: "var(--muted)" }}
                  >
                    {action.notes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Open source */}
      <section className="max-w-4xl mx-auto px-6 py-16 pb-24">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Open source transparency
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-8"
          style={{ color: "var(--muted)" }}
        >
          CMK is fully open source. Every line of code, every storage
          mechanism, and every classification algorithm is available for
          inspection on GitHub.
        </p>

        <div
          className="rounded-[var(--radius)] p-6"
          style={{
            background: "var(--warm-paper)",
            border: "1px solid var(--border-light)",
          }}
        >
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="currentColor"
                className="mt-0.5 shrink-0"
                style={{ color: "var(--foreground)" }}
              >
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              <div>
                <p
                  className="text-[15px] font-medium mb-1"
                  style={{ color: "var(--foreground)" }}
                >
                  Fully auditable
                </p>
                <p
                  className="text-[14px] leading-[1.6]"
                  style={{ color: "var(--muted)" }}
                >
                  The entire codebase is open on GitHub. You can audit the
                  memory classification pipeline, storage mechanisms, and
                  recall algorithms.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mt-0.5 shrink-0"
                style={{ color: "var(--foreground)" }}
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <div>
                <p
                  className="text-[15px] font-medium mb-1"
                  style={{ color: "var(--foreground)" }}
                >
                  No vendor lock-in
                </p>
                <p
                  className="text-[14px] leading-[1.6]"
                  style={{ color: "var(--muted)" }}
                >
                  Your memories are stored in standard SQLite and can be
                  exported at any time. No proprietary formats, no lock-in.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mt-0.5 shrink-0"
                style={{ color: "var(--foreground)" }}
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <div>
                <p
                  className="text-[15px] font-medium mb-1"
                  style={{ color: "var(--foreground)" }}
                >
                  Security-first approach
                </p>
                <p
                  className="text-[14px] leading-[1.6]"
                  style={{ color: "var(--muted)" }}
                >
                  API keys are hashed before storage. The server binds to
                  localhost by default. Your CMK API key is stored in your
                  local .env file, never in code.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function FeatureRow({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2">
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--sage)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-[3px] shrink-0"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
      <span
        className="text-[13px] leading-[1.5]"
        style={{ color: "var(--muted)" }}
      >
        {text}
      </span>
    </div>
  );
}

function StorageRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="text-[13px] font-medium shrink-0"
        style={{ color: "var(--foreground)", minWidth: 120 }}
      >
        {label}
      </span>
      <span className="text-[13px]" style={{ color: "var(--muted)" }}>
        {value}
      </span>
    </div>
  );
}

const LOCAL_FIRST_POINTS = [
  {
    title: "No cloud dependency",
    description:
      "In local mode, CMK uses SQLite for metadata and fastembed for embeddings. Both run entirely on your machine. No API keys, no network requests, no external services.",
    color: "var(--gate-promissory)",
  },
  {
    title: "No telemetry or analytics",
    description:
      "CMK does not collect usage data, crash reports, or any form of telemetry. The binary makes zero outbound network connections in local mode.",
    color: "var(--gate-behavioral)",
  },
  {
    title: "Opt-in cloud only",
    description:
      "Cloud storage is strictly opt-in. Set CMK_STORAGE=cloud and add your CMK API key. We handle the vector database and embeddings infrastructure on our end. Your API key is stored in your .env file and never logged.",
    color: "var(--gate-relational)",
  },
  {
    title: "Standard, portable formats",
    description:
      "Memories are stored in a standard SQLite database that you can open with any SQLite client. No proprietary binary formats, no encryption that prevents inspection.",
    color: "var(--gate-epistemic)",
  },
];

const DATA_ACTIONS = [
  {
    action: "Export all memories",
    method: "GET /api/memories",
    notes: "Returns full JSON of all stored memories. Paginate with limit/offset.",
  },
  {
    action: "Delete one memory",
    method: "cmk forget <id>",
    notes: "Removes from both SQLite and vector store.",
  },
  {
    action: "Delete by gate",
    method: "cmk forget --gate <type>",
    notes: "Bulk delete all memories of a specific gate type.",
  },
  {
    action: "Delete everything",
    method: "cmk forget --all",
    notes: "Requires confirmation. Wipes all memories and identity.",
  },
  {
    action: "Copy raw database",
    method: "cp ~/.cmk/memories.db backup.db",
    notes: "Standard SQLite file. Works with any backup tool.",
  },
  {
    action: "Revoke API key",
    method: "DELETE /api/keys/{id}",
    notes: "Immediately invalidates the key. Irreversible.",
  },
];
