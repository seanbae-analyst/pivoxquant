"use client";

/**
 * <NpsWidget /> — 10-point NPS one-click row (Wave G C-AC2).
 *
 * Renders horizontally as 10 buttons (1–10). Tapping a button POSTs to
 * /api/feedback/nps, then writes a localStorage flag keyed by the memo
 * so the same prompt is never shown twice on this device.
 *
 * Surface contract
 * ----------------
 * - Render inline at the bottom of a fresh Weekly Memo card. Caller
 *   passes `weeklyMemoId` so we can correlate score → memo version.
 * - "1 — 매우 별로" / "10 — 매우 좋음" anchors. Pure KR copy (디자인 v3
 *   convention: KR primary, EN secondary only when load-bearing).
 * - After submit, swap the row for a small thank-you line — the user
 *   should see acknowledgement without a route change.
 *
 * §50 classification: TRANSACTIONAL (서비스 개선) — no consent gate.
 * No marketing copy, no second prompt, no follow-up email triggered.
 *
 * Design tokens
 * -------------
 * - Bronze accent: `text-accent`, `bg-accent`, `ring-accent`.
 * - Neutral surface: `bg-card`, `border-border`, `text-foreground`,
 *   `text-muted-foreground`. No hardcoded hex.
 */

import * as React from "react";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import { FEEDBACK_NPS } from "@/lib/endpoints";

export interface NpsWidgetProps {
  /**
   * Stable identifier of the Weekly Memo (or other artifact) this prompt
   * is attached to. Used for the localStorage dedup key AND submitted to
   * the backend so the score can be correlated with memo version.
   */
  weeklyMemoId?: string;
  /**
   * Called after a successful submit. Lets the caller swap in a richer
   * thank-you UI; the widget shows its own minimal acknowledgement when
   * this prop is omitted.
   */
  onSubmitted?: (score: number) => void;
  /** Optional class hooks for caller layouts. */
  className?: string;
}

interface NpsResponse {
  ok: boolean;
  feedback: {
    id: number;
    score: number;
    weekly_memo_id: string | null;
    created_at: string;
  };
}

const SCORES: ReadonlyArray<number> = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

function lsKey(memoId: string | undefined): string {
  // When no memo id is supplied (e.g. catalog page), key by "global" so
  // the widget still self-dedupes per device.
  return `pivox_nps_submitted_${memoId ?? "global"}`;
}

function hasSubmitted(memoId: string | undefined): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(lsKey(memoId)) !== null;
  } catch {
    return false;
  }
}

function markSubmitted(memoId: string | undefined, score: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      lsKey(memoId),
      JSON.stringify({ score, ts: Date.now() }),
    );
  } catch {
    /* private mode / quota — degrade silently */
  }
}

export function NpsWidget({
  weeklyMemoId,
  onSubmitted,
  className,
}: NpsWidgetProps): React.ReactElement | null {
  // Hydration-safe initial state: render the prompt on the server, then
  // hide it on the client after we read localStorage. This avoids a
  // hydration mismatch warning while still respecting per-device dedup.
  const [submittedScore, setSubmittedScore] = React.useState<number | null>(
    null,
  );
  const [busyScore, setBusyScore] = React.useState<number | null>(null);
  const [dismissed, setDismissed] = React.useState<boolean>(false);

  React.useEffect(() => {
    if (hasSubmitted(weeklyMemoId)) {
      setDismissed(true);
    }
  }, [weeklyMemoId]);

  const handleClick = React.useCallback(
    async (score: number) => {
      if (busyScore !== null || submittedScore !== null) return;
      setBusyScore(score);
      try {
        const body: { score: number; weekly_memo_id?: string } = { score };
        if (weeklyMemoId) body.weekly_memo_id = weeklyMemoId;
        await apiFetch<NpsResponse>(FEEDBACK_NPS, {
          method: "POST",
          body: JSON.stringify(body),
        });
        markSubmitted(weeklyMemoId, score);
        setSubmittedScore(score);
        toast.success("감사합니다");
        onSubmitted?.(score);
      } catch (err) {
        toast.error("저장에 실패했습니다. 잠시 후 다시 시도해 주세요.");
        // Surface for debugging only — never bubble to the user.

        console.error("NpsWidget submit failed", err);
      } finally {
        setBusyScore(null);
      }
    },
    [busyScore, submittedScore, weeklyMemoId, onSubmitted],
  );

  // Already submitted from a previous session — hide entirely.
  if (dismissed && submittedScore === null) return null;

  // Just submitted in this session — show minimal acknowledgement.
  if (submittedScore !== null) {
    return (
      <div
        role="status"
        className={[
          "rounded-lg border border-border bg-card px-4 py-3",
          "text-sm text-muted-foreground",
          className ?? "",
        ].join(" ")}
        data-testid="nps-widget-thanks"
      >
        <span className="font-medium text-foreground">감사합니다.</span>{" "}
        <span>피드백이 저장됐어요 ({submittedScore}/10).</span>
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label="NPS 점수 — PivoxQuant를 친구에게 추천할 가능성을 골라 주세요"
      className={[
        "rounded-lg border border-border bg-card px-4 py-3",
        className ?? "",
      ].join(" ")}
      data-testid="nps-widget"
    >
      <p className="text-sm font-medium text-foreground">
        PivoxQuant를 친구에게 추천할 가능성은 얼마인가요?
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {SCORES.map((score) => {
          const isBusy = busyScore === score;
          return (
            <button
              key={score}
              type="button"
              disabled={busyScore !== null}
              onClick={() => handleClick(score)}
              aria-label={`${score}점`}
              className={[
                "inline-flex h-9 w-9 items-center justify-center",
                "rounded-md border border-border bg-background",
                "text-sm font-medium text-foreground tabular-nums",
                "transition-colors duration-150",
                "hover:border-accent hover:text-accent",
                "focus-visible:outline-none focus-visible:ring-2",
                "focus-visible:ring-accent focus-visible:ring-offset-2",
                "focus-visible:ring-offset-card",
                "disabled:cursor-not-allowed disabled:opacity-50",
                isBusy ? "bg-accent text-accent-foreground" : "",
              ].join(" ")}
              data-testid={`nps-score-${score}`}
            >
              {score}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>1 — 매우 별로</span>
        <span>10 — 매우 좋음</span>
      </div>
    </div>
  );
}

export default NpsWidget;
