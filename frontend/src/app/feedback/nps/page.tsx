"use client";

/**
 * /feedback/nps — NPS 1-click landing page (Wave G C-AC2).
 *
 * Two entry modes:
 *
 * 1. Email-link auto-submit. The Weekly Memo email embeds 10 links
 *    `/feedback/nps?memo={id}&score={N}`. Hitting one auto-POSTs the
 *    score and renders a thank-you state. This is the "1-click" path.
 *
 * 2. Standalone prompt. With no query params (e.g. linked from a
 *    settings page or product banner), the page just renders
 *    `<NpsWidget />` and lets the user pick a score.
 *
 * §50 classification: TRANSACTIONAL (서비스 개선) — the page itself
 * holds no marketing copy. The email link that brings users here is
 * embedded in a transactional Weekly Memo, not a marketing blast.
 *
 * Why a dedicated page (not a modal):
 *   Email links must open a navigable URL that survives copy-paste,
 *   forwarding, and screen-readers. A modal route would lose all three.
 */

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { FEEDBACK_NPS } from "@/lib/endpoints";
import { NpsWidget } from "@/components/feedback/NpsWidget";

interface NpsResponse {
  ok: boolean;
  feedback: {
    id: number;
    score: number;
    weekly_memo_id: string | null;
    created_at: string;
  };
}

type SubmitState =
  | { kind: "idle" }
  | { kind: "auto"; score: number }
  | { kind: "submitting"; score: number }
  | { kind: "success"; score: number }
  | { kind: "error"; message: string };

function parseScore(raw: string | null): number | null {
  if (raw === null) return null;
  // Accept only integer strings — never coerce 9.7 → 9. Whitespace
  // tolerated for forgiving copy-pasted URLs.
  const trimmed = raw.trim();
  if (!/^-?\d+$/.test(trimmed)) return null;
  const n = Number.parseInt(trimmed, 10);
  if (!Number.isInteger(n) || n < 1 || n > 10) return null;
  return n;
}

function NpsPageInner(): React.ReactElement {
  const searchParams = useSearchParams();
  const memoParam = searchParams.get("memo");
  const memoId = memoParam && memoParam.length > 0 ? memoParam : undefined;
  const preScore = parseScore(searchParams.get("score"));

  const [state, setState] = useState<SubmitState>(
    preScore !== null ? { kind: "auto", score: preScore } : { kind: "idle" },
  );

  useEffect(() => {
    if (state.kind !== "auto") return;
    const score = state.score;
    setState({ kind: "submitting", score });

    const body: { score: number; weekly_memo_id?: string } = { score };
    if (memoId) body.weekly_memo_id = memoId;

    apiFetch<NpsResponse>(FEEDBACK_NPS, {
      method: "POST",
      body: JSON.stringify(body),
    })
      .then(() => {
        // Mirror NpsWidget's localStorage key so the inline widget on
        // the dashboard does not double-prompt the same user.
        if (typeof window !== "undefined") {
          try {
            window.localStorage.setItem(
              `pivox_nps_submitted_${memoId ?? "global"}`,
              JSON.stringify({ score, ts: Date.now() }),
            );
          } catch {
            /* private mode / quota — degrade silently */
          }
        }
        setState({ kind: "success", score });
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error
            ? err.message
            : "저장에 실패했습니다. 잠시 후 다시 시도해 주세요.";
        setState({ kind: "error", message });
      });
    // Run-once on first render — `memoId` and `state.score` are derived
    // from the initial URL and do not change. We intentionally omit them
    // from the dep array so a render storm (e.g. parent re-mounts) does
    // not re-POST.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="min-h-screen bg-background px-6 py-12 text-foreground">
      <div className="mx-auto max-w-xl">
        <header className="mb-8">
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Feedback
          </p>
          <h1 className="mt-2 font-serif text-3xl md:text-4xl">
            한 줄 평가, 30초.
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            이번 주간 메모가 도움이 됐는지 알려 주세요. 서비스 개선에만 사용하며
            마케팅 목적으로 활용하지 않습니다.
          </p>
        </header>

        {state.kind === "auto" || state.kind === "submitting" ? (
          <div
            role="status"
            className="rounded-lg border border-border bg-card px-4 py-6 text-sm text-muted-foreground"
            data-testid="nps-page-submitting"
          >
            {state.score}점 평가를 저장하는 중…
          </div>
        ) : null}

        {state.kind === "success" ? (
          <div
            role="status"
            className="rounded-lg border border-border bg-card px-4 py-6"
            data-testid="nps-page-thanks"
          >
            <p className="text-base font-medium text-foreground">
              감사합니다.
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {state.score}점을 저장했어요. 본 평가는 익명 통계와 서비스 개선에만
              쓰입니다.
            </p>
            <div className="mt-4">
              <Link
                href="/home"
                className="inline-flex items-center text-sm font-medium text-accent hover:underline"
              >
                홈으로 돌아가기 →
              </Link>
            </div>
          </div>
        ) : null}

        {state.kind === "error" ? (
          <div
            role="alert"
            className="rounded-lg border border-border bg-card px-4 py-6"
            data-testid="nps-page-error"
          >
            <p className="text-base font-medium text-foreground">
              저장에 실패했습니다.
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{state.message}</p>
            <div className="mt-4">
              <NpsWidget weeklyMemoId={memoId} />
            </div>
          </div>
        ) : null}

        {state.kind === "idle" ? (
          <NpsWidget weeklyMemoId={memoId} />
        ) : null}
      </div>
    </main>
  );
}

export default function NpsPage(): React.ReactElement {
  // useSearchParams requires a Suspense boundary at the page level so
  // the route remains static-shell renderable.
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-background px-6 py-12" aria-hidden />
      }
    >
      <NpsPageInner />
    </Suspense>
  );
}
