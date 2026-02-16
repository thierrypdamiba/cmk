"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth-client";
import Link from "next/link";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await authClient.signIn.email({ email, password });
      if (result.error) {
        setError(result.error.message || "Sign in failed");
      } else {
        router.push("/dashboard");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSocial = async (provider: "github" | "google") => {
    await authClient.signIn.social({
      provider,
      callbackURL: "/dashboard",
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "#FAF9F7" }}>
      <div className="w-full flex items-center justify-center gap-16 px-8" style={{ maxWidth: 960 }}>
        {/* Left: Context Panel */}
        <div className="hidden lg:flex flex-col justify-center flex-1 max-w-[400px]">
          <p className="text-[18px] font-medium mb-3" style={{ color: "var(--muted)" }}>
            Claude Memory Kit
          </p>
          <h1 className="text-[28px] font-semibold tracking-tight leading-tight mb-4" style={{ letterSpacing: "-0.01em" }}>
            Claude remembers what matters.
          </h1>
          <p className="text-[15px] leading-relaxed mb-8" style={{ color: "var(--muted)" }}>
            CMK gives Claude persistent memory across sessions.
            Runs locally by default. Sync only if you choose.
          </p>

          {/* Pipeline animation */}
          <div className="flex items-center gap-3 mb-10">
            {["conversation", "memory", "identity"].map((step, i) => (
              <div key={step} className="flex items-center gap-3">
                <span
                  className="px-3 py-1.5 rounded-full text-[13px]"
                  style={{
                    border: "1px solid var(--border)",
                    color: "var(--muted)",
                    animation: `drift-in ${200 + i * 200}ms ease ${i * 200}ms both`,
                  }}
                >
                  {step}
                </span>
                {i < 2 && (
                  <span
                    className="w-6 h-px"
                    style={{
                      background: "var(--border)",
                      animation: `drift-in 200ms ease ${(i + 1) * 200}ms both`,
                    }}
                  />
                )}
              </div>
            ))}
          </div>

          {/* Trust indicators */}
          <div className="flex flex-col gap-2">
            {[
              "Local-first",
              "Fully editable memory",
              "Export anytime",
            ].map((item) => (
              <div key={item} className="flex items-center gap-2">
                <span className="text-[13px]" style={{ color: "var(--sage)" }}>&#10003;</span>
                <span className="text-[13px]" style={{ color: "var(--muted)" }}>{item}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Auth Card */}
        <div className="w-full max-w-[400px] shrink-0">
          <div
            className="rounded-[12px] p-8"
            style={{
              background: "#FFFFFF",
              boxShadow: "0 8px 24px rgba(0,0,0,0.06)",
            }}
          >
            {/* Header */}
            <h2 className="text-[22px] font-semibold tracking-tight text-center mb-1" style={{ letterSpacing: "-0.01em" }}>
              Welcome back
            </h2>
            <p className="text-[14px] text-center mb-6" style={{ color: "var(--muted)" }}>
              Your memories will sync after sign-in.
            </p>

            {/* Email/password form */}
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-[12px] font-medium uppercase tracking-[0.06em] mb-1.5" style={{ color: "var(--muted)" }}>
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded-[10px] text-[14px] h-[40px] px-3"
                  style={{
                    border: "1px solid var(--border)",
                    background: "#fff",
                  }}
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium uppercase tracking-[0.06em] mb-1.5" style={{ color: "var(--muted)" }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded-[10px] text-[14px] h-[40px] px-3"
                  style={{
                    border: "1px solid var(--border)",
                    background: "#fff",
                  }}
                />
              </div>

              {error && (
                <p className="text-[13px] rounded-[10px] p-2.5" style={{
                  color: "#B23A2A",
                  background: "rgba(178, 58, 42, 0.08)",
                  border: "1px solid rgba(178, 58, 42, 0.15)",
                }}>
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-[10px] text-[14px] font-medium h-[40px]"
                style={{
                  background: "#2F2B27",
                  color: "#fff",
                  opacity: loading ? 0.6 : 1,
                }}
              >
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
              <span className="text-[12px] uppercase tracking-wider" style={{ color: "var(--muted-light)" }}>or</span>
              <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
            </div>

            {/* Social buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => handleSocial("github")}
                className="flex-1 flex items-center justify-center gap-2 rounded-[10px] text-[14px] font-medium h-[40px]"
                style={{
                  border: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--foreground)",
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                GitHub
              </button>
              <button
                onClick={() => handleSocial("google")}
                className="flex-1 flex items-center justify-center gap-2 rounded-[10px] text-[14px] font-medium h-[40px]"
                style={{
                  border: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--foreground)",
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                </svg>
                Google
              </button>
            </div>

            {/* Local install link */}
            <div className="text-center mt-4 space-y-1.5">
              <Link
                href="/dashboard/setup"
                className="block text-[13px]"
                style={{ color: "var(--muted)" }}
              >
                Install CMK locally instead &rarr;
              </Link>
            </div>
          </div>

          {/* Sign up link */}
          <p className="text-center text-[14px] mt-6" style={{ color: "var(--muted)" }}>
            Don&apos;t have an account?{" "}
            <Link
              href="/sign-up"
              className="font-medium"
              style={{ color: "var(--foreground)" }}
            >
              Sign up &rarr;
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
