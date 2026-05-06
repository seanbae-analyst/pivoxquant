"use client";

/**
 * /login v2 — Editorial entry, Vantablack split layout.
 *
 * Toggle: NEXT_PUBLIC_LOGIN_V2=true (default off; v1 remains live).
 *
 * Visual rules (v3 lock-in):
 * - Full-bleed Vantablack (#050505) background.
 * - Left 50% — Editorial Hero (Playfair H1 + Bronze italic accent + deck).
 * - Right 50% — OAuth card (Continue with Google / Kakao, mono uppercase).
 * - Hairline center divider, fleuron (❦) ornament.
 * - Bottom switch link "계정이 없으신가요? 회원가입 ›" — Bronze, mono UC.
 * - Mobile (< 900px) collapses to single column, hero on top.
 *
 * Function preservation:
 * - OAuth handler unchanged — anchors point at API.auth.google / .kakao.
 * - useAuth + router.replace("/home") + loading + null user gating
 *   identical to v1, copied 1:1 (only visual layer changed).
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { useAuth } from "@/lib/auth";

import { AuthHeroV2 } from "@/components/auth/v2/auth-hero-v2";
import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { AuthLinkV2 } from "@/components/auth/v2/auth-link-v2";
import { Fleuron } from "@/components/ui/editorial";

export default function LoginPageV2() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/home");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div
        className="flex min-h-[100dvh] items-center justify-center"
        style={{ background: "var(--pq-ink, #050505)" }}
      >
        <div
          className="h-8 w-8 animate-spin rounded-full"
          style={{
            border: "2px solid rgba(245,240,232,0.10)",
            borderTopColor: "var(--pq-bronze, #B8956A)",
          }}
        />
      </div>
    );
  }

  if (user) return null;

  return (
    <div
      className="pq-auth-shell-v2"
      style={{
        // Escape the (auth)/layout.tsx max-w-sm white wrapper without
        // editing the shared layout (v1 still depends on it). Fixed-fill
        // covers the viewport with Vantablack ink underneath the layout.
        position: "fixed",
        inset: 0,
        zIndex: 50,
        minHeight: "100dvh",
        background: "var(--pq-ink, #050505)",
        color: "var(--pq-ivory, #F5F0E8)",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        overflowY: "auto",
      }}
    >
      {/* ── Left: Editorial Hero ──────────────────────────────────────── */}
      <div
        className="pq-auth-hero-pane"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          borderRight: "0.5px solid rgba(184,149,106,0.18)",
          minHeight: "100dvh",
        }}
      >
        <AuthHeroV2
          eyebrow={"PivoxQuant · Entry"}
          headlineHtml={
            'Welcome <span class="br">back</span>.<br/>The desk is <span class="br">already lit.</span>'
          }
          deck="Sign in to continue your weekly memo, your earnings pre-briefs, and the artifacts your CFO has been holding for you."
          signature="Drafted by AI · Reviewed by you"
        />
      </div>

      {/* ── Right: OAuth Card ─────────────────────────────────────────── */}
      <div
        className="pq-auth-card-pane"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-start",
          minHeight: "100dvh",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: 420,
            padding: "64px 56px",
            display: "flex",
            flexDirection: "column",
            gap: 28,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.24em",
                color: "var(--pq-bronze, #B8956A)",
                textTransform: "uppercase",
              }}
            >
              Sign in
            </span>
            <h2
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: 24,
                lineHeight: 1.2,
                letterSpacing: "-0.01em",
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
              }}
            >
              Continue with your provider
            </h2>
          </div>

          <OAuthButtonsV2 />

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "8px 0",
            }}
            aria-hidden="true"
          >
            <span
              style={{
                flex: 1,
                height: 0,
                borderTop: "0.5px solid rgba(245,240,232,0.08)",
              }}
            />
            <Fleuron size={12} />
            <span
              style={{
                flex: 1,
                height: 0,
                borderTop: "0.5px solid rgba(245,240,232,0.08)",
              }}
            />
          </div>

          <AuthLinkV2
            prompt="계정이 없으신가요?"
            action="회원가입"
            href="/signup"
          />

          <p
            className="font-serif"
            style={{
              marginTop: 12,
              fontSize: 12,
              lineHeight: 1.55,
              color: "rgba(245,240,232,0.40)",
              textAlign: "center",
            }}
          >
            계속하면{" "}
            <Link
              href="/terms"
              style={{
                color: "rgba(245,240,232,0.65)",
                textDecoration: "underline",
                textUnderlineOffset: 2,
              }}
            >
              이용약관
            </Link>{" "}
            및{" "}
            <Link
              href="/privacy"
              style={{
                color: "rgba(245,240,232,0.65)",
                textDecoration: "underline",
                textUnderlineOffset: 2,
              }}
            >
              개인정보처리방침
            </Link>
            에 동의하게 됩니다.
          </p>
        </div>
      </div>

      {/* Mobile collapse: single column. Inline media query via <style>. */}
      <style jsx>{`
        @media (max-width: 900px) {
          :global(.pq-auth-shell-v2) {
            grid-template-columns: 1fr !important;
          }
          :global(.pq-auth-hero-pane) {
            min-height: auto !important;
            border-right: 0 !important;
            border-bottom: 0.5px solid rgba(184, 149, 106, 0.18) !important;
            justify-content: flex-start !important;
          }
          :global(.pq-auth-card-pane) {
            min-height: auto !important;
            justify-content: center !important;
          }
        }
      `}</style>
    </div>
  );
}
