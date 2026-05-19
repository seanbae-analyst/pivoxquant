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

  return (
    <div
      className="min-h-[100dvh] flex items-center justify-center px-6"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <div className="w-full max-w-md text-center">
        <AlertTriangle
          className="mx-auto mb-6 h-8 w-8"
          style={{ color: "var(--pq-bronze)" }}
        />

        <div
          className="text-pq-mono-sm tracking-[0.22em] uppercase mb-4"
          style={{ color: "var(--pq-bronze)" }}
        >
          Something interrupted the observation
        </div>

        <h1
          className="font-serif italic mb-6 leading-[1.05]"
          style={{ fontSize: "clamp(1.75rem,4vw,2.5rem)" }}
        >
          The desk hit a snag.
        </h1>

        <p
          className="text-sm leading-relaxed mb-6"
          style={{ color: "rgba(var(--pq-ivory-rgb),0.65)" }}
        >
          An unexpected issue stopped the page from loading. Your data is safe.
          Retry, or head back to the desk.
        </p>

        {isProduction ? (
          error.digest ? (
            <p
              className="text-pq-mono-sm font-mono mb-6"
              style={{ color: "rgba(var(--pq-ivory-rgb),0.3)" }}
            >
              ref: {error.digest}
            </p>
          ) : null
        ) : (
          <pre
            className="text-left text-pq-mono-sm font-mono rounded p-3 mb-6 max-h-32 overflow-auto whitespace-pre-wrap break-words"
            style={{
              color: "rgba(var(--pq-ivory-rgb),0.55)",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(var(--pq-ivory-rgb),0.08)",
            }}
          >
            {error.message || "Unknown error"}
          </pre>
        )}

        <div className="flex items-center justify-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => reset()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-sm border text-sm font-medium tracking-wide transition-colors"
            style={{ borderColor: "var(--pq-bronze)", color: "var(--pq-bronze)" }}
          >
            <RotateCw className="h-3.5 w-3.5" />
            Try again
          </button>
          <Link
            href="/home"
            className="inline-flex items-center px-5 py-2.5 rounded-sm border text-sm font-medium tracking-wide"
            style={{
              borderColor: "rgba(var(--pq-ivory-rgb),0.15)",
              color: "rgba(var(--pq-ivory-rgb),0.6)",
            }}
          >
            Back to desk
          </Link>
        </div>

        <p
          className="text-pq-mono-sm mt-8 leading-relaxed"
          style={{ color: "rgba(var(--pq-ivory-rgb),0.3)" }}
        >
          PivoxQuant does not lose data on errors. All positions and settings
          are saved on the server.
        </p>
      </div>
    </div>
  );
}
