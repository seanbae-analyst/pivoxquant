"use client";

/**
 * Onboarding instant Brag Card — Activation surface (fills the empty-portfolio
 * gap so a brand-new user shares value on day zero).
 *
 * Flow:
 *   1. POST /api/artifacts/brag-card/preview → { data, png_base64 }.
 *      The backend returns a `snapshot` mode card for users with no closed
 *      trades, built from their holdings or watchlist.
 *   2. When the user has zero holdings AND zero watchlist items, the backend
 *      reports `empty_reason: "no_activity"`. We then show a light-friction
 *      single-symbol input ("보유 또는 관심 종목 1개"); adding it to the
 *      watchlist and regenerating produces a snapshot card.
 *   3. The rendered card + a "첫 Weekly Memo는 이번 일요일 도착" confirmation
 *      + a Share trigger (<ShareCardModal />).
 *
 * Events: `onboarding_done` on first successful render, `artifact_opened`
 * when the card is shown.
 *
 * §101: the card copy is the backend's `summary_safe` equivalent — the user's
 * own factual snapshot + a generic note. No recommendation language here.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Loader2, ChevronRight, Sparkles, CalendarCheck } from "lucide-react";
import { toast } from "sonner";

import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { track } from "@/lib/track";
import { PQ_EASE, PQ_DUR_SLOW } from "@/lib/motion";
import { displayName } from "@/lib/format";
import type { BragCardPreviewResponse, BragCardPreviewData } from "@/lib/types";
import { ShareCardModal } from "@/components/growth/share-card-modal";

/**
 * Build the public share URL. We prefer `/card/<share_token>` so the
 * recipient lands on the card itself (the backend public card endpoint is
 * keyed by share_token, and `referral_code` rides along server-side for
 * attribution). When no share_token exists yet we fall back to the referral
 * entry `/r/<code>`.
 */
function buildShareUrl(data: BragCardPreviewData): string {
  if (data.share_token) return `/card/${encodeURIComponent(data.share_token)}`;
  if (data.referral_code) return `/r/${encodeURIComponent(data.referral_code)}`;
  return "/";
}

/** Friendly Korean line describing the snapshot the card was built from. */
function snapshotLine(data: BragCardPreviewData): string {
  const names = (data.snapshot_tickers ?? [])
    .slice(0, 3)
    .map((t) => displayName(t));
  if (names.length === 0) return "포트폴리오 스냅샷";
  return `${names.join(" · ")} 기준 스냅샷`;
}

export function OnboardingBragCard({ onDone }: { onDone: () => void }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<BragCardPreviewData | null>(null);
  const [pngDataUrl, setPngDataUrl] = useState<string | null>(null);
  const [needsSymbol, setNeedsSymbol] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [adding, setAdding] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const trackedOpen = useRef(false);

  const generate = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<BragCardPreviewResponse>(
        API.artifacts.bragCardPreview,
        { method: "POST", body: JSON.stringify({}) },
      );
      const d = res.data;
      setData(d);
      setPngDataUrl(
        res.png_base64 ? `data:image/png;base64,${res.png_base64}` : null,
      );
      // No holdings + no watchlist → ask for one symbol (light friction).
      if (d.empty_reason === "no_activity") {
        setNeedsSymbol(true);
      } else {
        setNeedsSymbol(false);
        if (!trackedOpen.current) {
          trackedOpen.current = true;
          void track("onboarding_done", { meta: { card_mode: d.mode } });
          void track("artifact_opened", { meta: { artifact: "brag_card" } });
        }
      }
    } catch {
      toast.error("카드 생성에 실패했어요. 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void generate();
  }, [generate]);

  const handleAddSymbol = useCallback(async () => {
    const clean = symbol.trim().toUpperCase();
    if (!clean || adding) return;
    setAdding(true);
    try {
      await apiFetch(API.watchlist.add, {
        method: "POST",
        body: JSON.stringify({ ticker: clean }),
      });
      await generate();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Already on the watchlist — just regenerate.
        await generate();
      } else {
        toast.error("종목을 추가하지 못했어요.");
      }
    } finally {
      setAdding(false);
    }
  }, [symbol, adding, generate]);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading && !data) {
    return (
      <div className="flex flex-col items-center gap-4 py-12">
        <Loader2
          className="h-6 w-6 animate-spin"
          style={{ color: "var(--pq-bronze)" }}
        />
        <p
          className="text-sm"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
        >
          첫 카드를 만들고 있어요…
        </p>
      </div>
    );
  }

  // ── Light-friction symbol input (zero holdings + zero watchlist) ───────────
  if (needsSymbol) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        className="flex flex-col gap-5 py-6"
      >
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Sparkles className="h-4 w-4" style={{ color: "var(--pq-bronze)" }} />
            <span
              className="text-xs font-semibold uppercase font-mono"
              style={{ color: "var(--pq-bronze)", letterSpacing: "0.2em" }}
            >
              First Card
            </span>
          </div>
          <h2
            className="text-xl font-bold leading-tight font-display sm:text-2xl"
            style={{ color: "var(--pq-ivory)" }}
          >
            보유 또는 관심 종목 1개를 알려주세요
          </h2>
          <p
            className="mt-2 text-sm leading-relaxed"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
          >
            한 종목만 있으면 첫 Brag Card를 바로 만들어 드려요. 나중에 더
            추가할 수 있어요.
          </p>
        </div>

        <input
          type="text"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void handleAddSymbol();
            }
          }}
          placeholder="AAPL, NVDA, 005930.KS"
          autoFocus
          aria-label="보유 또는 관심 종목"
          className="w-full bg-transparent px-4 py-3.5 font-mono text-sm uppercase outline-none placeholder:normal-case"
          style={{
            border: "1px solid rgba(245,240,232,0.18)",
            borderRadius: "var(--pq-radius-cta)",
            color: "var(--pq-ivory)",
          }}
        />

        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onDone}
            className="text-sm font-medium transition-colors"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.5)" }}
          >
            나중에 할게요
          </button>
          <button
            type="button"
            onClick={() => void handleAddSymbol()}
            disabled={!symbol.trim() || adding}
            className="flex items-center gap-1.5 px-6 py-3 text-sm font-bold transition-all disabled:cursor-not-allowed"
            style={{
              borderRadius: "var(--pq-radius-cta)",
              backgroundColor: symbol.trim()
                ? "var(--pq-bronze)"
                : "rgba(var(--pq-ivory-rgb), 0.06)",
              color: symbol.trim()
                ? "var(--pq-ink)"
                : "rgba(var(--pq-ivory-rgb), 0.35)",
            }}
          >
            {adding ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                카드 만들기
                <ChevronRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </motion.div>
    );
  }

  // ── Card display ───────────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
      className="flex flex-col items-center gap-5 py-6"
    >
      <div className="flex flex-col items-center text-center">
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="h-4 w-4" style={{ color: "var(--pq-bronze)" }} />
          <span
            className="text-xs font-semibold uppercase font-mono"
            style={{ color: "var(--pq-bronze)", letterSpacing: "0.2em" }}
          >
            Your First Brag Card
          </span>
        </div>
        <h2
          className="text-2xl font-bold leading-tight font-display"
          style={{ color: "var(--pq-ivory)" }}
        >
          첫 카드가 준비됐어요
        </h2>
        {data && (
          <p
            className="mt-1.5 text-sm"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
          >
            {data.month_label} · {snapshotLine(data)}
          </p>
        )}
      </div>

      {/* Card image */}
      {pngDataUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- data URL, not remote
        <img
          src={pngDataUrl}
          alt="내 Brag Card 미리보기"
          className="w-full max-w-xs"
          style={{
            borderRadius: "var(--pq-radius-card)",
            border: "1px solid var(--pq-border)",
          }}
        />
      ) : (
        <div
          className="flex aspect-[9/16] w-full max-w-xs flex-col items-center justify-center gap-2 px-6 text-center"
          style={{
            borderRadius: "var(--pq-radius-card)",
            border: "1px solid var(--pq-border)",
            background: "var(--pq-ivory-line-ghost)",
          }}
        >
          <span
            className="text-lg font-display"
            style={{ color: "var(--pq-ivory)" }}
          >
            {data?.month_label ?? ""}
          </span>
          <span
            className="text-sm"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
          >
            {data ? snapshotLine(data) : ""}
          </span>
          <span
            className="mt-2 text-xs"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.4)" }}
          >
            정보 제공 목적이며 투자 권유가 아닙니다.
          </span>
        </div>
      )}

      {/* Weekly Memo scheduling confirmation */}
      <div
        className="flex w-full max-w-xs items-start gap-3 px-4 py-3"
        style={{
          borderRadius: "var(--pq-radius-card)",
          background: "rgba(184,149,106,0.08)",
          border: "1px solid rgba(184,149,106,0.25)",
        }}
      >
        <CalendarCheck
          className="mt-0.5 h-4 w-4 shrink-0"
          style={{ color: "var(--pq-bronze)" }}
        />
        <p
          className="text-sm leading-relaxed"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.8)" }}
        >
          첫 <strong>Weekly Memo</strong>는 이번 일요일에 도착해요. 예약이
          확정됐어요.
        </p>
      </div>

      {/* Actions */}
      <div className="flex w-full max-w-xs flex-col gap-3">
        <button
          type="button"
          onClick={() => setShareOpen(true)}
          className="flex w-full items-center justify-center gap-2 px-6 py-3.5 text-sm font-bold transition-all active:scale-[0.98]"
          style={{
            borderRadius: "var(--pq-radius-cta)",
            backgroundColor: "var(--pq-bronze)",
            color: "var(--pq-ink)",
            boxShadow: "0 6px 16px rgba(var(--pq-bronze-rgb),0.25)",
          }}
        >
          공유하기
        </button>
        <button
          type="button"
          onClick={onDone}
          className="flex w-full items-center justify-center gap-1.5 px-6 py-3 text-sm font-semibold transition-colors"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.7)" }}
        >
          대시보드로 이동
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {shareOpen && data && (
        <ShareCardModal
          onClose={() => setShareOpen(false)}
          shareUrl={buildShareUrl(data)}
          imageSrc={pngDataUrl}
          title="이번 달 투자 기록"
        />
      )}
    </motion.div>
  );
}
