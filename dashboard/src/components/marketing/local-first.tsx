export function LocalFirst() {
  return (
    <section className="max-w-4xl mx-auto px-6 py-20">
      <h2
        className="text-[32px] font-normal tracking-tight mb-2"
        style={{ fontFamily: "var(--font-serif)" }}
      >
        Your memories, your machine.
      </h2>
      <p
        className="text-[15px] leading-[1.6] mb-10"
        style={{ color: "var(--muted)" }}
      >
        Choose the storage mode that fits your workflow. Switch anytime.
      </p>

      {/* Two mode cards */}
      <div className="grid md:grid-cols-2 gap-5">
        {/* Cloud */}
        <div
          className="rounded-[var(--radius)] p-6 relative"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderTop: "3px solid var(--gate-relational)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <span
            className="absolute top-3 right-4 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(99, 102, 241, 0.1)",
              color: "var(--gate-relational)",
            }}
          >
            Recommended
          </span>
          <div className="flex items-center gap-2.5 mb-4">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: "var(--gate-relational)" }}
            />
            <h3
              className="text-[17px] font-semibold tracking-tight"
              style={{ color: "var(--foreground)" }}
            >
              Cloud
            </h3>
          </div>

          <p
            className="text-[14px] leading-[1.6] mb-5"
            style={{ color: "var(--muted)" }}
          >
            Sign up, add your API key, done. We handle everything else.
          </p>

          <div className="space-y-2">
            <FeatureRow text="Sync memories across all devices" />
            <FeatureRow text="Managed vector search and embeddings" />
            <FeatureRow text="No infrastructure to set up" />
            <FeatureRow text="Just one API key to configure" />
          </div>
        </div>

        {/* Local */}
        <div
          className="rounded-[var(--radius)] p-6"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderTop: "3px solid var(--gate-promissory)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div className="flex items-center gap-2.5 mb-4">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: "var(--gate-promissory)" }}
            />
            <h3
              className="text-[17px] font-semibold tracking-tight"
              style={{ color: "var(--foreground)" }}
            >
              Local
            </h3>
          </div>

          <p
            className="text-[14px] leading-[1.6] mb-5"
            style={{ color: "var(--muted)" }}
          >
            SQLite + local embeddings. Zero network calls. Full privacy.
          </p>

          <div className="space-y-2">
            <FeatureRow text="Runs entirely on your machine" />
            <FeatureRow text="Bring your own Anthropic key" />
            <FeatureRow text="fastembed for local vectors" />
            <FeatureRow text="Single-device, full control" />
          </div>
        </div>
      </div>

      {/* Reversible note */}
      <div
        className="mt-6 flex items-center justify-center gap-2 py-3"
        style={{ color: "var(--muted)" }}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M7 16l-4-4 4-4" />
          <path d="M17 8l4 4-4 4" />
          <path d="M3 12h18" />
        </svg>
        <span className="text-[13px]">
          Migration is reversible. Export and import between modes at any time.
        </span>
      </div>
    </section>
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
      <span className="text-[13px] leading-[1.5]" style={{ color: "var(--muted)" }}>
        {text}
      </span>
    </div>
  );
}
