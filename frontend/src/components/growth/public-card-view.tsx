"use client";

/**
 * Public OG card landing view — K-factor `c` lever (where a recipient lands).
 *
 * Renders the shared brag card image + owner display name + the §101-safe
 * summary, then a "나도 내 카드 만들기" CTA that starts OAuth signup with the
 * inviter's `?ref=<code>` attached (the backend captures it into the signed
 * state and records `referral_signup`).
 *
 * Compliance: NO recommendation language. `summarySafe` is the backend's
 * server-generated factual one-liner. The card image is the owner's own
 * snapshot. A disclaimer + AI-content badge sit below.
 */

import { useState } from "react";
import { motion } from "motion/react";

import { API } from "@/lib/endpoints";
import { PQ_EASE, PQ_DUR_SLOW } from "@/lib/motion";
import { AiContentBadge } from "@/components/ui/ai-content-badge";

export interface PublicCardViewProps {
  ownerDisplayName: string;
  cardImageUrl: string | null;
  summarySafe: string;
  monthLabel: string | null;
  /** Inviter's referral code, attached to the OAuth start URL as ?ref=. */
  referralCode: string | null;
}

function oauthWithRef(base: string, refCode: string | null): string {
  if (!refCode) return base;
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}ref=${encodeURIComponent(refCode)}`;
}

export function PublicCardView({
  ownerDisplayName,
  cardImageUrl,
  summarySafe,
  monthLabel,
  referralCode,
}: PublicCardViewProps) {
  const [imgError, setImgError] = useState(false);

  return (
    <div
      className="flex min-h-[100dvh] flex-col items-center px-4 py-10 sm:py-16"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <div className="flex w-full max-w-md flex-col items-center gap-6">
        {/* Wordmark */}
        <span
          className="text-base font-bold font-display"
          style={{
            color: "var(--pq-ivory)",
            letterSpacing: "var(--pq-track-wordmark)",
          }}
        >
          PivoxQuant
        </span>

        {/* Eyebrow */}
        <div className="flex flex-col items-center text-center">
          <span
            className="text-xs font-semibold uppercase font-mono"
            style={{ color: "var(--pq-bronze)", letterSpacing: "0.2em" }}
          >
            {monthLabel ? `${monthLabel} · Brag Card` : "Brag Card"}
          </span>
          <h1
            className="mt-2 text-2xl font-bold leading-tight font-display"
            style={{ color: "var(--pq-ivory)" }}
          >
            {ownerDisplayName}님의 투자 기록
          </h1>
        </div>

        {/* Card image */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
          className="w-full max-w-xs"
        >
          {cardImageUrl && !imgError ? (
            // eslint-disable-next-line @next/next/no-img-element -- public PNG, crawler-cacheable
            <img
              src={cardImageUrl}
              alt={`${ownerDisplayName}님의 Brag Card`}
              onError={() => setImgError(true)}
              className="w-full"
              style={{
                borderRadius: "var(--pq-radius-card)",
                border: "1px solid var(--pq-border)",
              }}
            />
          ) : (
            <div
              className="flex aspect-[9/16] w-full flex-col items-center justify-center gap-2 px-6 text-center"
              style={{
                borderRadius: "var(--pq-radius-card)",
                border: "1px solid var(--pq-border)",
                background: "var(--pq-ivory-line-ghost)",
              }}
            >
              <span className="text-lg font-display">
                {monthLabel ?? "Brag Card"}
              </span>
            </div>
          )}
        </motion.div>

        {/* §101-safe summary */}
        <p
          className="text-center text-sm leading-relaxed"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.75)" }}
        >
          {summarySafe}
        </p>

        {/* CTA — start signup with referral attribution */}
        <div className="flex w-full flex-col gap-3">
          <a
            href={oauthWithRef(API.auth.google, referralCode)}
            className="flex w-full items-center justify-center gap-2 px-6 py-3.5 text-sm font-bold transition-all active:scale-[0.98]"
            style={{
              borderRadius: "var(--pq-radius-cta)",
              backgroundColor: "var(--pq-bronze)",
              color: "var(--pq-ink)",
              boxShadow: "0 6px 16px rgba(184,149,106,0.25)",
            }}
          >
            나도 내 카드 만들기
          </a>
          <a
            href={oauthWithRef(API.auth.kakao, referralCode)}
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

        {/* Compliance footer */}
        <div className="mt-2 flex flex-col items-center gap-3">
          <AiContentBadge variant="inline" />
          <p
            className="max-w-xs text-center text-xs leading-relaxed"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.4)" }}
          >
            본 페이지는 정보 제공 목적이며 투자 권유가 아닙니다. 표시된 내용은
            작성자 본인의 기록이며, 특정 종목의 매매를 권유하지 않습니다.
          </p>
        </div>
      </div>
    </div>
  );
}
