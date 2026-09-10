/**
 * <RetiredLinkNotice />
 *
 * Shared landing for links that were handed out before the surface behind them
 * was retired — `/card/<token>` brag cards and `/r/<code>` referral links.
 *
 * These URLs live in other people's KakaoTalk threads and timelines, so they
 * keep arriving long after the feature is gone. Three things follow from that:
 *
 *   · The page must not 404. A dead link that still renders something is worth
 *     more than one that renders a browser error, and it may be re-shared.
 *   · It must not depend on the backend. The brag-card routes went with the
 *     artefact tree, and the database they read went with the Railway account
 *     on 2026-08-30 — there is no data left to serve, so nothing is fetched.
 *   · It must not repeat the old not-found copy, which blamed expiry or a
 *     privacy toggle. Neither happened. The service withdrew the feature, and
 *     saying otherwise makes the visitor look for a setting that isn't there.
 *
 * No CTA to create a card: that flow was deleted too.
 */
import Link from "next/link";

export function RetiredLinkNotice() {
  return (
    <main
      className="flex min-h-[100dvh] flex-col items-center justify-center px-6 text-center"
      style={{ backgroundColor: "var(--pq-ink)" }}
    >
      <div className="flex w-full max-w-md flex-col items-center gap-4">
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          PivoxQuant
        </span>

        <h1
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: "clamp(22px, 4vw, 30px)",
            lineHeight: 1.2,
            color: "var(--pq-ivory, #F5F0E8)",
            margin: 0,
          }}
        >
          이 공유 링크는 더 이상 열람할 수 없습니다
        </h1>

        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.7,
            color: "var(--pq-ivory-muted)",
            margin: 0,
          }}
        >
          공유 카드 기능이 종료되면서 카드 데이터가 남아 있지 않습니다. 링크가
          만료되었거나 비공개로 바뀐 것은 아닙니다.
        </p>

        <Link
          href="/"
          className="mt-2 font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
          }}
        >
          PivoxQuant 알아보기 →
        </Link>
      </div>
    </main>
  );
}
