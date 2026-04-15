"use client";

import Link from "next/link";
import { useEffect } from "react";

/**
 * App-level error boundary.
 *
 * Catches runtime errors thrown in any route segment below the root layout.
 * Root layout itself is handled by `global-error.tsx`.
 *
 * Next.js 16 prefers `unstable_retry` over `reset`, but `reset` remains
 * supported for clearing the error state without re-fetching. We keep `reset`
 * here to satisfy our declared contract and because it is the safer default
 * for boundary recovery on the client.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Only log in the browser; never echo stack traces to users.
    // In production, Next.js strips the original message for SSR-thrown errors,
    // so this mostly surfaces client-component errors to the dev console.
    if (typeof window !== "undefined") {
      console.error("[PivoxQuant:error-boundary]", error);
    }
  }, [error]);

  const isProduction = process.env.NODE_ENV === "production";

  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-white p-6">
      <div className="sp-card w-full max-w-md p-8 text-center">
        {/* Brand mark — matches the landing/loading-screen logo */}
        <div className="w-14 h-14 mx-auto rounded-2xl bg-primary-gradient flex items-center justify-center mb-6">
          <svg
            className="w-7 h-7 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01M4.93 19h14.14a2 2 0 001.73-3L13.73 4a2 2 0 00-3.46 0L3.2 16a2 2 0 001.73 3z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-slate-900 mb-2">
          Something went wrong
        </h1>
        <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto">
          We hit an unexpected error while loading this page. Your portfolio
          data is safe — try again in a moment.
        </p>

        {/* Production: only show the digest so engineers can match server logs. */}
        {/* Development: show the error message for faster debugging. */}
        {isProduction ? (
          error.digest ? (
            <p className="text-[11px] font-mono text-slate-400 mb-6 tabular-nums">
              ref: {error.digest}
            </p>
          ) : null
        ) : (
          <pre className="text-left text-[11px] font-mono text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-3 mb-6 max-h-32 overflow-auto whitespace-pre-wrap break-words">
            {error.message || "Unknown error"}
          </pre>
        )}

        <div className="flex flex-col sm:flex-row gap-2.5 justify-center">
          <button
            type="button"
            onClick={() => reset()}
            className="px-5 py-2.5 rounded-full bg-primary-gradient text-white text-sm font-semibold transition-all duration-200 hover:opacity-90 active:scale-[0.97]"
          >
            Try again
          </button>
          <Link
            href="/"
            className="px-5 py-2.5 rounded-full border border-slate-200 bg-white text-slate-700 text-sm font-semibold transition-all duration-200 hover:bg-slate-50 active:scale-[0.97]"
          >
            Go home
          </Link>
        </div>

        {/* Friendly disclaimer tone — matches DisclaimerBanner voice */}
        <p className="text-[11px] text-slate-400 mt-6 leading-relaxed">
          PivoxQuant does not lose data on errors. All positions and settings
          are saved on the server.
        </p>
      </div>
    </div>
  );
}
