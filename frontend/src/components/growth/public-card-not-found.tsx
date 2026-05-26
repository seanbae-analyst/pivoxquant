/**
 * Clean fallback for a missing / private / expired public card.
 *
 * The backend returns the SAME 404 for "not found" and "not public" so a
 * token-holder can never enumerate or distinguish another user's private
 * card (PIPA §29 enumeration guard). This surface mirrors that: it never
 * hints at whether the card exists — it just invites the visitor to sign up.
 */

import { API } from "@/lib/endpoints";

export function PublicCardNotFound() {
  return (
    <div
      className="flex min-h-[100dvh] flex-col items-center justify-center gap-6 px-6 text-center"
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
        <h1 className="text-2xl font-bold font-display">
          카드를 찾을 수 없어요
        </h1>
        <p
          className="text-sm leading-relaxed"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
        >
          링크가 만료되었거나 비공개로 전환되었을 수 있어요. 직접 내 투자
          기록 카드를 만들어 보세요.
        </p>
      </div>
      <a
        href={API.auth.google}
        className="flex items-center justify-center gap-2 px-6 py-3.5 text-sm font-bold transition-all active:scale-[0.98]"
        style={{
          borderRadius: "var(--pq-radius-cta)",
          backgroundColor: "var(--pq-bronze)",
          color: "var(--pq-ink)",
          boxShadow: "0 6px 16px rgba(184,149,106,0.25)",
        }}
      >
        내 카드 만들기
      </a>
    </div>
  );
}
