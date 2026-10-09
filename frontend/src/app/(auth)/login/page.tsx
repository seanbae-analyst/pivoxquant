"use client";

/**
 * Unified auth entry — Editorial entry, Vantablack split layout.
 *
 * 2026-09-17 (CEO decision): /login and /signup are ONE screen. The backend
 * OAuth callback provisions an account when none exists, so both routes were
 * always two decorations on a single path. This module is the canonical
 * surface; `/signup/page.tsx` renders this exact component so both URLs stay
 * alive for `_safe_next()`, OAuth redirects and existing bookmarks.
 *
 * Consequences of the merge:
 * - The "계정이 없으신가요? 회원가입 ›" switch link is gone — there is nowhere
 *   else to go.
 * - Copy is neutral for first-time and returning visitors alike
 *   (auth.login.* keys in messages/{ko,en}.json).
 * - Required consents are NOT collected here. New accounts are asked after
 *   OAuth, on the post-callback interstitial.
 *
 * Visual rules (v3 lock-in):
 * - Full-bleed Vantablack (#050505) background.
 * - Left 50% — Editorial Hero (Playfair H1 + Bronze accent + deck).
 * - Right 50% — OAuth card (Continue with Google / Kakao, mono uppercase).
 * - Hairline center divider, fleuron (❦) ornament.
 * - Phone (< 768px, 2026-10-09): an app screen, not the split page —
 *   AppCover's PIVOXQUANT wordmark on top, 56px OAuth buttons at the
 *   bottom, safe-area insets, no editorial hero. See the <style> block.
 *
 * Function preservation:
 * - OAuth handler unchanged — anchors point at API.auth.google / .kakao
 *   (plus `?next=` when /login was reached with a safe `next`, 2026-09-29).
 * - useAuth + router.replace("/mirror") + loading + null user gating
 *   unchanged.
 */

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { useAuth } from "@/lib/auth";
import { useT, useLocale } from "@/lib/locale";
import { loginNextPath } from "@/lib/login-redirect";

import { AuthHeroV2 } from "@/components/auth/v2/auth-hero-v2";
import { AuthPhoneBrand } from "@/components/auth/v2/auth-phone-brand";
import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { Fleuron } from "@/components/ui/editorial";

// Error copy is locale-aware via errorsFor() computed inside the component.

export default function AuthEntryPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const t = useT();
  const { locale } = useLocale();
  const searchParams = useSearchParams();
  const errorParam = searchParams?.get("error") ?? null;
  const expiredParam = searchParams?.get("expired") ?? null;
  // 2026-09-29: where to land after sign-in. Validated here (same-origin
  // relative path, not /login itself) and again by the backend's _safe_next.
  const nextPath = loginNextPath(searchParams?.get("next") ?? null);
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
      router.replace(nextPath ?? "/mirror");
    }
  }, [user, loading, router, nextPath]);

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
    // Page-load skeleton — Vantablack surface.
    // Desktop (md+): unchanged centred card stack.
    // Phone: the same frame as the live phone screen — wordmark in the upper
    // area, skeleton buttons at the bottom — so the app cover → sign-in hand-
    // off never flashes a different picture while /api/auth/me answers.
    return (
      <div
        // Phone: fixed full-bleed like the live screen (which escapes the
        // login layout's max-w-sm wrapper the same way), so nothing moves
        // when auth resolves. md+: back in normal flow, as before.
        className="fixed inset-0 z-50 overflow-y-auto md:static md:z-auto md:overflow-visible"
        style={{ background: "var(--pq-ink, #050505)" }}
        role="status"
        aria-live="polite"
        aria-label="Loading login"
      >
        <div className="hidden min-h-[100dvh] items-center justify-center px-6 md:flex">
          <div className="w-full max-w-sm flex flex-col gap-3">
            <div className="pq-skeleton-dark h-10 w-10 rounded-sm" />
            <div className="pq-skeleton-dark h-8 w-48 rounded" />
            <div className="pq-skeleton-dark h-4 w-32 rounded" />
            <div className="pq-skeleton-dark mt-6 h-12 w-full rounded-sm" />
            <div className="pq-skeleton-dark h-12 w-full rounded-sm" />
          </div>
        </div>
        <div
          className="mx-auto flex min-h-[100dvh] w-full max-w-[480px] flex-col gap-5 md:hidden"
          style={{
            paddingTop: "calc(var(--pq-safe-top) + 24px)",
            paddingRight: "calc(var(--pq-safe-right) + 24px)",
            paddingBottom: "calc(var(--pq-safe-bottom) + 28px)",
            paddingLeft: "calc(var(--pq-safe-left) + 24px)",
            color: "var(--pq-ivory)",
          }}
        >
          {/* Same slot geometry as `.pq-auth-phone-brand-slot`. */}
          <div className="flex min-h-[168px] flex-1 items-center justify-center pb-4">
            <AuthPhoneBrand tagline={t("auth.login.phoneTagline")} />
          </div>
          {/* Heights mirror the live stack: eyebrow / heading / 2-line deck,
              two 56px buttons, terms line — 20px apart. */}
          <div className="flex flex-col gap-2.5">
            <div className="pq-skeleton-dark h-5 w-28 rounded-sm" />
            <div className="pq-skeleton-dark h-9 w-56 rounded-sm" />
            <div className="pq-skeleton-dark h-12 w-full rounded-sm" />
          </div>
          <div className="flex flex-col gap-3">
            <div className="pq-skeleton-dark h-14 w-full rounded-sm" />
            <div className="pq-skeleton-dark h-14 w-full rounded-sm" />
          </div>
          <div className="pq-skeleton-dark mx-auto h-5 w-3/4 rounded-sm" />
        </div>
        <span className="sr-only">Loading…</span>
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
        {/* 2026-09-01: the deck used to sell weekly memos, earnings
            pre-briefs and AI artifacts — all three deleted in the prune.
            2026-09-17: it also greeted every visitor with "welcome back",
            which is wrong for the half of them who have no account yet. */}
        <AuthHeroV2
          eyebrow={"PivoxQuant · Entry"}
          headlineHtml={t("auth.login.heroHeadline")}
          deck={t("auth.login.heroDeck")}
          signature={t("auth.login.heroSignature")}
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
        {/* Phone only — AppCover's soft ivory glow, so the sign-in screen
            sits on the same surface the installed app opened on. */}
        <div aria-hidden className="pq-auth-phone-only pq-auth-phone-glow" />
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
          {/* Phone only — the PIVOXQUANT wordmark from the app cover. Takes
              the free space above the actions, so the OAuth buttons sit in
              thumb reach at the bottom of the screen. */}
          <div className="pq-auth-phone-only pq-auth-phone-brand-slot">
            <AuthPhoneBrand tagline={t("auth.login.phoneTagline")} />
          </div>

          <div
            className="pq-auth-card-header"
            style={{ display: "flex", flexDirection: "column", gap: 8 }}
          >
            <span
              className="pq-auth-card-eyebrow font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze, #B8956A)",
                textTransform: "uppercase",
              }}
            >
              {t("auth.login.eyebrow")}
            </span>
            <h2
              className="pq-auth-card-heading font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-quote)",
                lineHeight: 1.2,
                letterSpacing: "-0.01em",
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
              }}
            >
              {t("auth.login.heading")}
            </h2>
            {/* Phone only — on desktop the hero pane carries this line; the
                hero is not shown on a phone, and a first-time user needs to
                know that this one screen also creates the account. */}
            <p className="pq-auth-phone-only pq-auth-card-deck">
              {t("auth.login.phoneDeck")}
            </p>
          </div>

          {bannerMessage && (
            <div
              role="alert"
              className="pq-auth-banner font-serif"
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
                className="pq-auth-banner-dismiss"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--pq-ivory-dim)",
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

          <OAuthButtonsV2 next={nextPath} />

          <div
            className="pq-auth-fleuron-rule"
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

          <p
            className="pq-auth-terms font-serif"
            style={{
              // Was marginTop: 12 on top of the 28px stack gap, which spaced
              // this off the switch link that used to sit above. With that
              // link removed the fleuron divider is the neighbour, so the
              // plain 28px gap keeps the card's vertical rhythm.
              marginTop: 0,
              fontSize: "var(--pq-text-eyebrow)",
              lineHeight: 1.55,
              color: "var(--pq-ivory-dim)",
              textAlign: "center",
            }}
          >
            {locale === "ko" ? (
              <>
                계속하면{" "}
                <Link href="/terms" style={{ color: "var(--pq-ivory-mid)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  이용약관
                </Link>{" "}
                및{" "}
                <Link href="/privacy" style={{ color: "var(--pq-ivory-mid)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  개인정보처리방침
                </Link>
                에 동의하게 됩니다.
              </>
            ) : (
              <>
                By continuing, you agree to our{" "}
                <Link href="/terms" style={{ color: "var(--pq-ivory-mid)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  Terms of Service
                </Link>{" "}
                and{" "}
                <Link href="/privacy" style={{ color: "var(--pq-ivory-mid)", textDecoration: "underline", textUnderlineOffset: 2 }}>
                  Privacy Policy
                </Link>.
              </>
            )}
          </p>
        </div>
      </div>

      {/* Phone layout (< 768px) — 2026-10-09 redesign.
          CEO: "폰 그리고 시작하기 들어가서 나오는 로그인 부분 너무 이상함".
          The installed app opens on AppCover (pwa/app-welcome.tsx) and its
          시작하기 / 로그인 buttons land here. The phone used to get the
          desktop split stacked into one column: card on top, then the
          editorial marketing hero below it — a web page, not the app the
          user had just been swiping through. Now:
            - the editorial hero pane is not rendered on phones;
            - the app cover's PIVOXQUANT wordmark (+ glow) fills the upper
              space, the actions sit at the bottom in thumb reach;
            - OAuth buttons are 56px tall with plain sans labels (the mono
              0.22em tracking split Korean labels apart);
            - safe-area insets on all four sides (PWA standalone, notch,
              home indicator);
            - while the cookie banner is up, the bottom of the screen is
              reserved so it never covers the buttons or the terms line
              (the 2026-09-27 "no way to log in" report).
          Desktop (md+) is untouched: every rule below is phone-scoped, and
          the phone-only nodes are display:none above the breakpoint.
          FINDING-MOB-001 (design-audit-20260514) still holds: one column,
          no horizontal scroll at 375px. */}
      <style jsx>{`
        :global(.pq-auth-phone-only) {
          display: none;
        }
        @media (max-width: 767px) {
          :global(.pq-auth-shell-v2) {
            grid-template-columns: 1fr !important;
          }
          :global(.pq-auth-hero-pane) {
            display: none !important;
          }
          :global(.pq-auth-card-pane) {
            position: relative;
            min-height: 100dvh !important;
            align-items: stretch !important;
            justify-content: center !important;
          }
          :global(.pq-auth-phone-glow) {
            display: block;
            position: absolute;
            inset: 0;
            pointer-events: none;
            background: radial-gradient(
              ellipse 90% 60% at 50% 32%,
              rgba(var(--pq-ivory-rgb), 0.03) 0%,
              rgba(var(--pq-ivory-rgb), 0.012) 40%,
              transparent 75%
            );
          }
          :global(.pq-auth-card-inner) {
            position: relative;
            max-width: 480px !important;
            margin: 0 auto;
            min-height: 100dvh;
            padding: calc(var(--pq-safe-top) + 24px)
              calc(var(--pq-safe-right) + 24px)
              calc(var(--pq-safe-bottom) + 28px)
              calc(var(--pq-safe-left) + 24px) !important;
            gap: 20px !important;
          }
          :global(.pq-auth-phone-brand-slot) {
            display: flex;
            flex: 1 0 auto;
            align-items: center;
            justify-content: center;
            min-height: 168px;
            padding-bottom: 16px;
          }
          :global(.pq-auth-card-header) {
            gap: 10px !important;
          }
          :global(.pq-auth-card-eyebrow) {
            font-family: var(--pq-font-sans) !important;
            font-size: var(--pq-text-button) !important;
            letter-spacing: 0.2em !important;
          }
          :global(.pq-auth-card-heading) {
            font-family: var(--pq-font-serif) !important;
            font-size: var(--pq-text-avatar) !important;
            line-height: 1.3 !important;
            word-break: keep-all;
          }
          :global(.pq-auth-card-deck) {
            display: block;
            margin: 0;
            font-size: var(--pq-text-lead);
            line-height: 1.6;
            color: var(--pq-ivory-mid);
            word-break: keep-all;
          }
          :global(.pq-auth-shell-v2 .pq-auth-oauth-btn) {
            min-height: 56px;
            padding: 0 20px !important;
            gap: 12px !important;
            font-family: var(--pq-font-sans) !important;
            font-size: var(--pq-text-h6) !important;
            font-weight: 500;
            letter-spacing: 0 !important;
            text-transform: none !important;
            border-color: rgba(var(--pq-bronze-rgb), 0.38) !important;
            background: var(--pq-ivory-line-faint) !important;
            -webkit-tap-highlight-color: transparent;
          }
          :global(.pq-auth-shell-v2 .pq-auth-oauth-btn:active) {
            background: var(--pq-ivory-line) !important;
            border-color: rgba(var(--pq-bronze-rgb), 0.7) !important;
          }
          :global(.pq-auth-shell-v2 .pq-auth-wake-note) {
            font-family: var(--pq-font-sans) !important;
            font-size: var(--pq-text-caption) !important;
            letter-spacing: 0.02em !important;
            word-break: keep-all;
          }
          :global(.pq-auth-shell-v2 .pq-auth-wake-retry) {
            min-height: 48px;
            padding: 0 24px !important;
            font-family: var(--pq-font-sans) !important;
            font-size: var(--pq-text-body) !important;
            letter-spacing: 0.04em !important;
          }
          :global(.pq-auth-banner-dismiss) {
            min-width: 44px;
            min-height: 44px;
            margin: -12px -10px -12px 0 !important;
          }
          :global(.pq-auth-fleuron-rule) {
            display: none !important;
          }
          :global(.pq-auth-terms) {
            font-size: var(--pq-text-caption) !important;
            line-height: 1.7 !important;
            word-break: keep-all;
          }
          :global(body:has([data-cookie-banner="true"]) .pq-auth-card-inner) {
            padding-bottom: calc(var(--pq-safe-bottom) + 184px) !important;
          }
        }
      `}</style>
    </div>
  );
}
