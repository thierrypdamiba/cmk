"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/product", label: "Product" },
  { href: "/memory-model", label: "Memory Model" },
  { href: "/docs", label: "Docs" },
  { href: "/dashboard", label: "Dashboard" },
];

export function MarketingNav() {
  const pathname = usePathname();

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-6"
      style={{
        background: "rgba(250, 249, 247, 0.85)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--border-light)",
      }}
    >
      <div className="w-full max-w-6xl mx-auto flex items-center justify-between">
        {/* Logo + Sign up */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2">
            <svg
              width="20"
              height="20"
              viewBox="0 0 16 16"
              fill="none"
              aria-label="CMK logo"
            >
              <g
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ color: "var(--foreground)" }}
              >
                <path d="M6 3.75h4.25c1.25 0 2 .9 2 2v4.5c0 1.1-.75 2-2 2H6" />
                <path d="M3.75 8h5.75" />
                <path d="M8.5 6.6 10.1 8 8.5 9.4" />
              </g>
            </svg>
            <span
              className="text-[15px] font-semibold tracking-tight"
              style={{ color: "var(--foreground)" }}
            >
              Claude Memory Kit (CMK)
            </span>
          </Link>
          <Link
            href="/sign-in"
            className="px-3.5 py-1.5 rounded-[var(--radius)] text-[14px] font-medium"
            style={{
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              background: "transparent",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--surface-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            Sign in
          </Link>
        </div>

        {/* Center nav */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const active =
              pathname === link.href ||
              (link.href !== "/" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className="px-3 py-1.5 rounded-[var(--radius-sm)] text-[14px]"
                style={{
                  color: active ? "var(--foreground)" : "var(--muted)",
                  fontWeight: active ? 500 : 400,
                  background: active ? "var(--surface-active)" : "transparent",
                  transition: "color 140ms ease, background 140ms ease",
                }}
                onMouseEnter={(e) => {
                  if (!active)
                    e.currentTarget.style.background = "var(--surface-hover)";
                }}
                onMouseLeave={(e) => {
                  if (!active)
                    e.currentTarget.style.background = "transparent";
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right: GitHub + Install CTA */}
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/thierrydamiba/claude-memory"
            target="_blank"
            rel="noopener noreferrer"
            className="w-8 h-8 flex items-center justify-center rounded-[var(--radius-sm)]"
            style={{ color: "var(--muted)" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--surface-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
            </svg>
          </a>
          <Link
            href="/docs/install"
            className="px-3.5 py-1.5 rounded-[var(--radius)] text-[14px] font-medium"
            style={{
              background: "var(--foreground)",
              color: "var(--background)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = "0.85";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = "1";
            }}
          >
            Install
          </Link>
        </div>
      </div>
    </header>
  );
}
