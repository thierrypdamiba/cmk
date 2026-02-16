export default function ProductPage() {
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
          The architecture behind memory
        </h1>
        <p
          className="text-[18px] leading-[1.65] max-w-2xl"
          style={{ color: "var(--muted)" }}
        >
          CMK is a structured memory layer for Claude. It intercepts
          conversations via MCP, classifies memories through five semantic
          gates, stores them locally, and retrieves them with vector search
          when context demands it.
        </p>
      </section>

      {/* Architecture Diagram */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          How data flows
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-10"
          style={{ color: "var(--muted)" }}
        >
          From conversation to persistent recall, every memory passes through
          a deterministic pipeline.
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
            architecture
          </div>
          <pre
            className="p-6 overflow-x-auto text-[13px] leading-[1.7] font-mono"
            style={{ color: "var(--code-fg)" }}
          >
            <code>{`  Claude Desktop / Claude Code
            |
            v
  ┌─────────────────────┐
  │     MCP Server       │   cmk serve --port 7749
  │   (tool interface)   │
  └─────────┬───────────┘
            |
            v
  ┌─────────────────────┐
  │    Five Gates        │   behavioral, relational, epistemic,
  │  (classification)    │   promissory, correction
  └─────────┬───────────┘
            |
       ┌────┴────┐
       v         v
  ┌─────────┐ ┌──────────┐
  │ SQLite  │ │ Vectors  │   metadata + embeddings
  │ (meta)  │ │ (search) │   local or cloud
  └────┬────┘ └────┬─────┘
       └────┬──────┘
            v
  ┌─────────────────────┐
  │      Recall          │   semantic search + keyword match
  │  (hybrid retrieval)  │   confidence scoring + decay
  └─────────────────────┘`}</code>
          </pre>
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          How CMK compares
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-10"
          style={{ color: "var(--muted)" }}
        >
          CMK fills a gap that existing approaches leave open.
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
                  Feature
                </th>
                {["CMK", "System prompt", "CLAUDE.md", "No memory"].map(
                  (col) => (
                    <th
                      key={col}
                      className="text-center px-5 py-3.5 text-[13px] font-semibold"
                      style={{
                        color:
                          col === "CMK"
                            ? "var(--accent)"
                            : "var(--foreground)",
                      }}
                    >
                      {col}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {COMPARISON_ROWS.map((row, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom:
                      i < COMPARISON_ROWS.length - 1
                        ? "1px solid var(--border-light)"
                        : "none",
                    background:
                      i % 2 === 0 ? "var(--surface)" : "var(--background)",
                  }}
                >
                  <td
                    className="px-5 py-3 text-[13px]"
                    style={{ color: "var(--foreground)" }}
                  >
                    {row.feature}
                  </td>
                  {row.values.map((val, j) => (
                    <td
                      key={j}
                      className="text-center px-5 py-3 text-[13px]"
                      style={{
                        color:
                          val === "Yes"
                            ? "var(--success)"
                            : val === "No"
                              ? "var(--gate-correction)"
                              : "var(--muted)",
                      }}
                    >
                      {val}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Use Cases */}
      <section className="max-w-5xl mx-auto px-6 py-16 pb-24">
        <h2
          className="text-[32px] font-normal tracking-tight mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Built for every scale
        </h2>
        <p
          className="text-[15px] leading-[1.6] mb-10"
          style={{ color: "var(--muted)" }}
        >
          Whether you work solo or with a team, CMK adapts to your workflow.
        </p>

        <div className="grid md:grid-cols-3 gap-5">
          {USE_CASES.map((uc, i) => (
            <div
              key={i}
              className="rounded-[var(--radius)] p-6"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderTop: `3px solid ${uc.color}`,
                boxShadow: "var(--shadow-sm)",
                animation: `drift-up 300ms ease ${i * 80}ms both`,
              }}
            >
              <div className="flex items-center gap-2.5 mb-4">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: uc.color }}
                />
                <h3
                  className="text-[17px] font-semibold tracking-tight"
                  style={{ color: "var(--foreground)" }}
                >
                  {uc.title}
                </h3>
              </div>
              <p
                className="text-[14px] leading-[1.6] mb-5"
                style={{ color: "var(--muted)" }}
              >
                {uc.description}
              </p>
              <div className="space-y-2">
                {uc.features.map((feat) => (
                  <div key={feat} className="flex items-start gap-2">
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
                      {feat}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

const COMPARISON_ROWS = [
  {
    feature: "Persists across sessions",
    values: ["Yes", "No", "Manual", "No"],
  },
  {
    feature: "Auto-classifies memories",
    values: ["Yes", "No", "No", "No"],
  },
  {
    feature: "Semantic search recall",
    values: ["Yes", "No", "No", "No"],
  },
  {
    feature: "Editable by user",
    values: ["Yes", "No", "Yes", "No"],
  },
  {
    feature: "Scoped (user/project/global)",
    values: ["Yes", "No", "Partial", "No"],
  },
  {
    feature: "Confidence scoring",
    values: ["Yes", "No", "No", "No"],
  },
  {
    feature: "Decay and expiry",
    values: ["Yes", "No", "No", "No"],
  },
  {
    feature: "Local-first storage",
    values: ["Yes", "N/A", "Yes", "N/A"],
  },
  {
    feature: "Identity synthesis",
    values: ["Yes", "No", "No", "No"],
  },
];

const USE_CASES = [
  {
    title: "Individual dev",
    color: "var(--gate-behavioral)",
    description:
      "Your preferences, your stack, your habits. CMK learns how you code and remembers it across every session.",
    features: [
      "Local-only storage, zero config",
      "Remembers editor, language, and style preferences",
      "Identity document builds automatically",
      "Pin important memories to prevent decay",
    ],
  },
  {
    title: "Team",
    color: "var(--gate-relational)",
    description:
      "Shared context about team members, conventions, and architecture decisions that every Claude session should know.",
    features: [
      "Project-scoped memories for shared context",
      "Relational gate tracks team structure",
      "Cloud sync across all devices",
      "API keys for shared access control",
    ],
  },
  {
    title: "Enterprise",
    color: "var(--gate-epistemic)",
    description:
      "Deploy CMK as a memory service across your organization. Audit trails, access control, and full data sovereignty.",
    features: [
      "Self-hosted with full data control",
      "BetterAuth integration for SSO",
      "API key management per service",
      "Export and deletion for compliance",
    ],
  },
];
