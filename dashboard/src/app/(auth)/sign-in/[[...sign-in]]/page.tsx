"use client";

import { SignIn } from "@clerk/nextjs";
import Link from "next/link";

export default function SignInPage() {
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

            {/* Clerk sign-in */}
            <div className="clerk-auth">
              <SignIn
                forceRedirectUrl="/dashboard"
                appearance={{
                  elements: {
                    rootBox: "w-full",
                    card: "shadow-none border-none bg-transparent w-full p-0 m-0",
                    cardBox: "shadow-none border-none bg-transparent w-full",
                    main: "gap-3",
                    header: "hidden",
                    headerTitle: "hidden",
                    headerSubtitle: "hidden",
                    socialButtonsBlockButton:
                      "rounded-[10px] text-[14px] font-medium h-[40px] w-full",
                    socialButtonsBlockButtonText: "text-[14px] font-medium",
                    socialButtonsProviderIcon: "w-[18px] h-[18px]",
                    dividerLine: "bg-[var(--border)]",
                    dividerText: "text-[12px] uppercase tracking-wider",
                    formFieldLabel: "text-[12px] font-medium uppercase tracking-[0.06em]",
                    formFieldInput: "rounded-[10px] text-[14px] h-[40px]",
                    formButtonPrimary:
                      "rounded-[10px] text-[14px] font-medium h-[40px] normal-case",
                    footer: "hidden",
                    footerAction: "hidden",
                    identityPreview: "rounded-[10px]",
                    identityPreviewEditButton: "text-[13px]",
                    formFieldAction: "text-[13px] font-medium",
                    otpCodeFieldInput: "rounded-[6px]",
                    alert: "rounded-[10px] text-[14px]",
                    alertText: "text-[14px]",
                    formFieldInputShowPasswordButton: "opacity-50",
                    backLink: "text-[14px] font-medium",
                  },
                  variables: {
                    colorPrimary: "#2F2B27",
                    colorDanger: "#B23A2A",
                    colorBackground: "transparent",
                    colorText: "#2F2B27",
                    colorTextOnPrimaryBackground: "#fff",
                    colorTextSecondary: "#6b6560",
                    colorInputBackground: "#fff",
                    colorInputText: "#2F2B27",
                    colorNeutral: "#6b6560",
                    borderRadius: "10px",
                    fontFamily:
                      "var(--font-geist-sans), system-ui, -apple-system, sans-serif",
                    fontSize: "14px",
                    spacingUnit: "14px",
                  },
                  layout: {
                    socialButtonsPlacement: "bottom",
                    socialButtonsVariant: "blockButton",
                    showOptionalFields: false,
                  },
                }}
              />
            </div>

            {/* Forgot password + local */}
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

      <style>{`
        .clerk-auth .cl-card,
        .clerk-auth .cl-cardBox {
          padding: 0 !important;
          margin: 0 !important;
          box-shadow: none !important;
          border: none !important;
          background: transparent !important;
          width: 100% !important;
        }
        .clerk-auth .cl-footer,
        .clerk-auth .cl-footerAction,
        .clerk-auth .cl-internal-b3fm6y {
          display: none !important;
        }
        .clerk-auth .cl-socialButtons {
          display: flex !important;
          flex-direction: row !important;
          gap: 8px !important;
          justify-content: center !important;
          width: 100% !important;
        }
        .clerk-auth .cl-main {
          align-items: center !important;
          width: 100% !important;
        }
        .clerk-auth .cl-rootBox,
        .clerk-auth .cl-signIn-root,
        .clerk-auth .cl-signIn-start {
          width: 100% !important;
        }
        .clerk-auth .cl-socialButtonsBlockButtonArrow {
          display: none !important;
        }
        .clerk-auth .cl-socialButtonsProviderButton__lastUsed::after,
        .clerk-auth [data-last-used],
        .clerk-auth .cl-badge,
        .clerk-auth .cl-internal-badge,
        .clerk-auth span[class*="lastUsed"],
        .clerk-auth div[class*="lastUsed"],
        .clerk-auth span[class*="badge"],
        .clerk-auth span[class*="Badge"],
        .clerk-auth [class*="cl-internal"][class*="badge"],
        .clerk-auth .cl-socialButtonsBlockButton span:last-child:not([class*="Text"]):not([class*="Icon"]) {
          display: none !important;
        }
        .clerk-auth .cl-socialButtonsBlockButton {
          position: relative !important;
          overflow: hidden !important;
        }
        .clerk-auth .cl-socialButtonsBlockButton,
        .clerk-auth .cl-socialButtonsIconButton,
        .clerk-auth .cl-socialButtonsProviderButton,
        .clerk-auth button[class*="socialButton"] {
          border: 1px solid var(--border) !important;
          border-color: var(--border) !important;
          background: transparent !important;
          box-shadow: none !important;
          transition: all 140ms ease !important;
          outline: none !important;
          width: auto !important;
          flex: 0 0 auto !important;
          color: var(--foreground) !important;
        }
        .clerk-auth .cl-socialButtonsBlockButton:hover,
        .clerk-auth .cl-socialButtonsIconButton:hover,
        .clerk-auth .cl-socialButtonsProviderButton:hover,
        .clerk-auth button[class*="socialButton"]:hover {
          background: var(--surface-hover) !important;
          border-color: var(--border) !important;
        }
        .clerk-auth .cl-formFieldInput {
          border: 1px solid var(--border) !important;
          background: #fff !important;
          box-shadow: none !important;
          transition: border-color 140ms ease, box-shadow 140ms ease !important;
        }
        .clerk-auth .cl-formFieldInput:focus {
          border-color: var(--accent) !important;
          box-shadow: 0 0 0 2px rgba(192, 86, 33, 0.08) !important;
        }
        .clerk-auth .cl-formButtonPrimary {
          background: #2F2B27 !important;
          border: none !important;
          box-shadow: none !important;
          color: #fff !important;
          transition: background 140ms ease, transform 90ms ease !important;
        }
        .clerk-auth .cl-formButtonPrimary:hover {
          background: #3d3833 !important;
        }
        .clerk-auth .cl-formButtonPrimary:active {
          transform: scale(0.98) !important;
        }
        .clerk-auth .cl-formFieldLabel {
          color: var(--muted) !important;
          text-transform: uppercase !important;
          letter-spacing: 0.06em !important;
          font-size: 12px !important;
        }
        .clerk-auth .cl-formFieldAction {
          color: var(--muted) !important;
        }
        .clerk-auth .cl-dividerLine {
          background: var(--border) !important;
        }
        .clerk-auth .cl-dividerText {
          color: var(--muted-light) !important;
        }
        .clerk-auth .cl-formFieldErrorText {
          color: #B23A2A !important;
        }
        .clerk-auth .cl-alert {
          border: 1px solid rgba(178, 58, 42, 0.15) !important;
          background: rgba(178, 58, 42, 0.08) !important;
          color: #B23A2A !important;
        }
        .clerk-auth .cl-alertText {
          color: #B23A2A !important;
        }
        .clerk-auth .cl-identityPreview {
          border: 1px solid var(--border) !important;
          background: var(--surface-hover) !important;
        }
      `}</style>
    </div>
  );
}
