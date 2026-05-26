/**
 * /r/[code] — referral entry point (K-factor attribution).
 *
 * Unlike /card/[token] (which renders a specific shared card), /r/<code>
 * carries only the inviter's referral code. The public card endpoint is keyed
 * by share_token, not referral_code, so this route can't fetch a specific
 * card — it's a lightweight invite landing that:
 *   - fires `landing_view` with the ref_code (attribution),
 *   - offers a "내 카드 만들기" CTA that starts OAuth signup with ?ref=<code>
 *     (backend captures it into the signed state → records referral_signup).
 *
 * §101: generic product invite only. No tickers, no recommendation language.
 */

import type { Metadata } from "next";

import { API } from "@/lib/endpoints";
import { LandingViewTracker } from "@/components/growth/landing-view-tracker";

export const metadata: Metadata = {
  title: "PivoxQuant — 내 투자 기록 카드 만들기",
  description:
    "PivoxQuant로 나의 투자 기록을 한 장의 카드로 정리해 보세요. 정보 제공 목적이며 투자 권유가 아닙니다.",
  openGraph: {
    title: "PivoxQuant — 내 투자 기록 카드 만들기",
    description:
      "PivoxQuant로 나의 투자 기록을 한 장의 카드로 정리해 보세요.",
    type: "website",
  },
};

/** Sanitize the path code to the backend's ≤16-char ref_code bound. */
function cleanRef(raw: string): string | null {
  const c = (raw || "").trim().slice(0, 16);
  return c.length > 0 ? c : null;
}

function oauthWithRef(base: string, refCode: string | null): string {
  if (!refCode) return base;
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}ref=${encodeURIComponent(refCode)}`;
}

export default async function ReferralEntryPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const ref = cleanRef(code);

  return (
    <>
      <LandingViewTracker refCode={ref} channel="referral_link" />
      <div
        className="flex min-h-[100dvh] flex-col items-center justify-center gap-7 px-6 text-center"
        style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
      >
        <span
          className="text-base font-bold font-display"
          style={{
            color: "var(--pq-ivory)",
            letterSpacing: "var(--pq-track-wordmark)",
          }}
        >
          PivoxQuant
        </span>

        <div className="flex max-w-sm flex-col items-center gap-3">
          <span
            className="text-xs font-semibold uppercase font-mono"
            style={{ color: "var(--pq-bronze)", letterSpacing: "0.2em" }}
          >
            초대장
          </span>
          <h1 className="text-2xl font-bold leading-tight font-display">
            친구가 PivoxQuant에 초대했어요
          </h1>
          <p
            className="text-sm leading-relaxed"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.65)" }}
          >
            나의 투자 기록을 한 장의 카드로 정리하고, AI가 만든 주간 메모를
            받아보세요.
          </p>
        </div>

        <div className="flex w-full max-w-xs flex-col gap-3">
          <a
            href={oauthWithRef(API.auth.google, ref)}
            className="flex w-full items-center justify-center gap-2 px-6 py-3.5 text-sm font-bold transition-all active:scale-[0.98]"
            style={{
              borderRadius: "var(--pq-radius-cta)",
              backgroundColor: "var(--pq-bronze)",
              color: "var(--pq-ink)",
              boxShadow: "0 6px 16px rgba(184,149,106,0.25)",
            }}
          >
            Google로 시작하기
          </a>
          <a
            href={oauthWithRef(API.auth.kakao, ref)}
            className="flex w-full items-center justify-center gap-2 px-6 py-3 text-sm font-semibold transition-colors"
            style={{
              borderRadius: "var(--pq-radius-cta)",
              border: "1px solid rgba(245,240,232,0.16)",
              color: "var(--pq-ivory)",
            }}
          >
            카카오로 시작하기
          </a>
        </div>

        <p
          className="max-w-xs text-xs leading-relaxed"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.4)" }}
        >
          본 페이지는 정보 제공 목적이며 투자 권유가 아닙니다.
        </p>
      </div>
    </>
  );
}
