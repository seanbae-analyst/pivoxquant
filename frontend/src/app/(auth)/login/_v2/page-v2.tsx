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

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { useAuth } from "@/lib/auth";

import { AuthHeroV2 } from "@/components/auth/v2/auth-hero-v2";
import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { AuthLinkV2 } from "@/components/auth/v2/auth-link-v2";
import { Fleuron } from "@/components/ui/editorial";

// M1 fix (2026-05-09 release-prep audit): backend OAuth callback failure
// redirects to /login?error=<reason>; SESSION_EXPIRED redirects to
// /login?expired=1. Previously v2 silently rendered an empty form so the
// user had no idea why they were bounced back. Same copy as v1.
const ERROR_COPY: Record<string, string> = {
  google_failed: "Google 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.",
  kakao_failed: "Kakao 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.",
  provisioning_failed:
    "계정 프로비저닝 중 오류가 발생했습니다. 새로고침 후 다시 시도해 주세요.",
  server_error:
    "예상치 못한 서버 오류가 발생했습니다. 문제가 계속되면 support@pivoxquant.com 으로 문의 주세요.",
  oauth_state_mismatch:
    "보안 검증 실패: 로그인 세션이 만료되었거나 변경되었습니다. 다시 시도해 주세요.",
};

export default function LoginPageV2() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const errorParam = searchParams?.get("error") ?? null;
  const expiredParam = searchParams?.get("expired") ?? null;
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/home");
    }
  }, [user, loading, router]);

  const bannerMessage =
    !bannerDismissed && expiredParam === "1"
      ? "세션이 만료되어 자동 로그아웃 되었습니다. 다시 로그인해 주세요."
      : !bannerDismissed && errorParam && errorParam in ERROR_COPY
        ? ERROR_COPY[errorParam]
        : !bannerDismissed && errorParam
          ? "로그인 중 오류가 발생했습니다. 다시 시도해 주세요."
          : null;

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

          {bannerMessage && (
            <div
              role="alert"
              className="font-serif"
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
                padding: "12px 14px",
                border: "1px solid rgba(220,38,38,0.45)",
                background: "rgba(220,38,38,0.06)",
                borderRadius: "var(--pq-radius-cta, 2px)",
                fontSize: 13,
                lineHeight: 1.5,
                color: "var(--pq-ivory, #F5F0E8)",
              }}
            >
              <span
                aria-hidden
                style={{
                  marginTop: 6,
                  height: 6,
                  width: 6,
                  borderRadius: 999,
                  background: "var(--pq-negative, #dc2626)",
                  flexShrink: 0,
                }}
              />
              <span style={{ flex: 1 }}>{bannerMessage}</span>
              <button
                type="button"
                onClick={() => setBannerDismissed(true)}
                aria-label="알림 닫기"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "rgba(245,240,232,0.55)",
                  cursor: "pointer",
                  fontSize: 16,
                  lineHeight: 1,
                  padding: "0 4px",
                }}
              >
                ×
              </button>
            </div>
          )}

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
              color: "rgba(245,240,232,0.55)",
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
