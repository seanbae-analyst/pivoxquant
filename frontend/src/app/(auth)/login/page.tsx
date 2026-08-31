"use client";

/**
 * /login v2 — Editorial entry, Vantablack split layout.
 *
 * Sole /login surface — the pre-v3 variant was deleted 2026-08-30.
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
 * - useAuth + router.replace("/mirror") + loading + null user gating
 *   identical to v1, copied 1:1 (only visual layer changed).
 */

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { useAuth } from "@/lib/auth";
import { useT, useLocale } from "@/lib/locale";

import { AuthHeroV2 } from "@/components/auth/v2/auth-hero-v2";
import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { AuthLinkV2 } from "@/components/auth/v2/auth-link-v2";
import { Fleuron } from "@/components/ui/editorial";

// Error copy is locale-aware via errorsFor() computed inside the component.

export default function LoginPageV2() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const t = useT();
  const { locale } = useLocale();
  const searchParams = useSearchParams();
  const errorParam = searchParams?.get("error") ?? null;
  const expiredParam = searchParams?.get("expired") ?? null;
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // Locale-aware error copy.
  const ERROR_COPY: Record<string, string> =
    locale === "ko"
      ? {
          google_failed: "Google 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.",
          kakao_failed: "Kakao 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.",
          provisioning_failed: "계정 프로비저닝 중 오류가 발생했습니다. 새로고침 후 다시 시도해 주세요.",
          server_error: "예상치 못한 서버 오류가 발생했습니다. 문제가 계속되면 support@pivoxquant.com 으로 문의 주세요.",
          oauth_state_mismatch: "보안 검증 실패: 로그인 세션이 만료되었거나 변경되었습니다. 다시 시도해 주세요.",
        }
      : {
          google_failed: "Google sign-in failed. Please try again.",
          kakao_failed: "Kakao sign-in failed. Please try again.",
          provisioning_failed: "Account provisioning error. Please refresh and try again.",
          server_error: "Unexpected server error. If this continues, contact support@pivoxquant.com.",
          oauth_state_mismatch: "Security check failed: your session may have expired. Please try again.",
        };

  useEffect(() => {
    if (!loading && user) {
      router.replace("/mirror");
    }
  }, [user, loading, router]);

  const sessionExpiredMsg =
    locale === "ko"
      ? "세션이 만료되어 자동 로그아웃 되었습니다. 다시 로그인해 주세요."
      : "Your session has expired. Please sign in again.";
  const genericErrorMsg =
    locale === "ko"
      ? "로그인 중 오류가 발생했습니다. 다시 시도해 주세요."
      : "An error occurred during sign-in. Please try again.";

  const bannerMessage =
    !bannerDismissed && expiredParam === "1"
      ? sessionExpiredMsg
      : !bannerDismissed && errorParam && errorParam in ERROR_COPY
        ? ERROR_COPY[errorParam]
        : !bannerDismissed && errorParam
          ? genericErrorMsg
          : null;

  if (loading) {
    // Page-load skeleton — Vantablack surface matching the editorial split
    // login layout. Mirrors the marketing card stack so dimensions stay
    // stable when the live form mounts.
    return (
      <div
        className="flex min-h-[100dvh] items-center justify-center px-6"
        style={{ background: "var(--pq-ink, #050505)" }}
        role="status"
        aria-live="polite"
        aria-label="Loading login"
      >
        <div className="w-full max-w-sm flex flex-col gap-3">
          <div className="pq-skeleton-dark h-10 w-10 rounded-sm" />
          <div className="pq-skeleton-dark h-8 w-48 rounded" />
          <div className="pq-skeleton-dark h-4 w-32 rounded" />
          <div className="pq-skeleton-dark mt-6 h-12 w-full rounded-sm" />
          <div className="pq-skeleton-dark h-12 w-full rounded-sm" />
          <span className="sr-only">Loading…</span>
        </div>
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
            locale === "ko"
              ? '다시 오신 것을 <span class="br">환영합니다</span>.<br/>데스크는 이미 <span class="br">준비됐습니다.</span>'
              : 'Welcome <span class="br">back</span>.<br/>The desk is <span class="br">already lit.</span>'
          }
          deck={
            locale === "ko"
              ? "로그인하여 주간 메모, 실적 프리브리프, AI가 준비한 아티팩트를 확인하세요."
              : "Sign in to continue your weekly memo, your earnings pre-briefs, and the artifacts your CFO has been holding for you."
          }
          signature={locale === "ko" ? "AI 초안 · 당신의 검토" : "Drafted by AI · Reviewed by you"}
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
          className="pq-auth-card-inner"
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
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze, #B8956A)",
                textTransform: "uppercase",
              }}
            >
              {locale === "ko" ? "로그인" : "Sign in"}
            </span>
            <h2
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-quote)",
                lineHeight: 1.2,
                letterSpacing: "-0.01em",
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
              }}
            >
              {locale === "ko" ? "소셜 계정으로 계속하기" : "Continue with your provider"}
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
                border: "1px solid rgba(209,136,136,0.45)",
                background: "rgba(209,136,136,0.06)",
                borderRadius: "var(--pq-radius-cta, 2px)",
                fontSize: "var(--pq-text-button)",
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
                  background: "var(--pq-negative, #d18888)",
                  flexShrink: 0,
                }}
              />
              <span style={{ flex: 1 }}>{bannerMessage}</span>
              <button
                type="button"
                onClick={() => setBannerDismissed(true)}
                aria-label={locale === "ko" ? "알림 닫기" : "Dismiss"}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "rgba(245,240,232,0.55)",
                  cursor: "pointer",
                  fontSize: "var(--pq-text-h6)",
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
                borderTop: "0.5px solid var(--pq-ivory-line)",
              }}
            />
            <Fleuron size={12} />
            <span
              style={{
                flex: 1,
                height: 0,
                borderTop: "0.5px solid var(--pq-ivory-line)",
              }}
            />
          </div>

          <AuthLinkV2
            prompt={t("auth.login.noAccount")}
            action={t("auth.login.createAccount")}
            href="/signup"
          />

          <p
            className="font-serif"
            style={{
              marginTop: 12,
              fontSize: "var(--pq-text-eyebrow)",
              lineHeight: 1.55,
              color: "rgba(245,240,232,0.55)",
              textAlign: "center",
            }}
          >
            {locale === "ko" ? (
              <>
                계속하면{" "}
                <Link href="/terms" style={{ color: "rgba(245,240,232,0.65)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  이용약관
                </Link>{" "}
                및{" "}
                <Link href="/privacy" style={{ color: "rgba(245,240,232,0.65)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  개인정보처리방침
                </Link>
                에 동의하게 됩니다.
              </>
            ) : (
              <>
                By continuing, you agree to our{" "}
                <Link href="/terms" style={{ color: "rgba(245,240,232,0.65)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  Terms of Service
                </Link>{" "}
                and{" "}
                <Link href="/privacy" style={{ color: "rgba(245,240,232,0.65)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  Privacy Policy
                </Link>.
              </>
            )}
          </p>
        </div>
      </div>

      {/* Mobile collapse: single column. Inline media query via <style>.
          FINDING-MOB-001 (design-audit-20260514): the split grid
          (grid-template-columns: 1fr 1fr) must collapse to a single column
          on phones or the right-hand login card is pushed off-screen.
          Breakpoint aligned to the 768px tablet threshold per the audit
          spec; the inner card/hero horizontal padding is also reduced so
          375px viewports never trigger a horizontal scrollbar. */}
      <style jsx>{`
        @media (max-width: 767px) {
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
          :global(.pq-auth-card-inner) {
            padding: 40px 24px !important;
          }
        }
      `}</style>
    </div>
  );
}
