"use client";

import Link from "next/link";
import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

/**
 * App-level error boundary.
 *
 * Catches runtime errors thrown in any route segment below the root layout.
 * Root layout itself is handled by `global-error.tsx`.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // P3 (wave1-critical): only emit the boundary log in non-production.
    // In production the `error.digest` is already shown to the user
    // (and forwarded to Sentry by Next.js when configured), so dumping
    // the raw Error to console.error pollutes prod browser consoles
    // for end users without adding observability.
    if (
      typeof window !== "undefined" &&
      process.env.NODE_ENV !== "production"
    ) {
      console.error("[PivoxQuant:error-boundary]", error);
    }
  }, [error]);

  const isProduction = process.env.NODE_ENV === "production";

  // 2026-10-22: Korean, same voice and buttons as the 404 (not-found-view).
  // The English "The desk hit a snag" with a tracked-capitals kicker was the
  // one screen still written like the old website.
  return (
    <div
      className="min-h-[100dvh] flex items-center justify-center px-6"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <div className="w-full max-w-md text-center">
        <AlertTriangle
          className="mx-auto mb-5 h-7 w-7"
          style={{ color: "var(--pq-bronze)" }}
          aria-hidden
        />

        <div
          className="mb-3"
          style={{ color: "var(--pq-bronze)", fontSize: "var(--pq-text-body-sm)", fontWeight: 500 }}
        >
          화면을 그리다 멈췄어요
        </div>

        <h1
          className="mb-4 leading-[1.2] [word-break:keep-all]"
          style={{ fontSize: "clamp(1.6rem,4vw,2.1rem)", fontWeight: 600 }}
        >
          잠깐 문제가 생겼어요.
        </h1>

        <p
          className="text-pq-body leading-relaxed mb-6 [word-break:keep-all]"
          style={{ color: "var(--pq-ivory-mid)" }}
        >
          남긴 기록은 그대로예요. 다시 시도하거나 거울로 돌아가 주세요.
        </p>

        {isProduction ? (
          error.digest ? (
            <p
              className="text-pq-mono-sm mb-6 tabular-nums"
              style={{ color: "rgba(var(--pq-ivory-rgb),0.35)" }}
            >
              참조 번호 {error.digest}
            </p>
          ) : null
        ) : (
          <pre
            className="text-left text-pq-mono-sm font-mono rounded-[var(--pq-radius-cta)] p-3 mb-6 max-h-32 overflow-auto whitespace-pre-wrap break-words"
            style={{
              color: "rgba(var(--pq-ivory-rgb),0.55)",
              background: "rgba(var(--pq-ivory-rgb),0.04)",
              border: "1px solid var(--pq-ivory-line)",
            }}
          >
            {error.message || "Unknown error"}
          </pre>
        )}

        <div className="flex items-center justify-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => reset()}
            className="pq-ink-btn-bronze inline-flex min-h-[44px] items-center gap-2"
          >
            <RotateCw className="h-3.5 w-3.5" aria-hidden />
            다시 시도
          </button>
          <Link
            href="/mirror"
            className="pq-ink-btn-ghost inline-flex min-h-[44px] items-center"
          >
            거울로 돌아가기
          </Link>
        </div>
      </div>
    </div>
  );
}
