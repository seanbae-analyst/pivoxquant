/**
 * /simulator/what-if — Public "What-If" (Time-Machine) Simulator
 *
 * Server Component shell: handles metadata + SEO, wraps the interactive
 * client in a Suspense boundary so useSearchParams() streams correctly.
 *
 * Auth: NOT required. Viral acquisition surface.
 * Beta gate: bypassed via middleware.ts BETA_BYPASS_PREFIXES.
 */

import { Suspense } from "react";
import type { Metadata } from "next";
import { WhatIfClient } from "./what-if-client";

export const metadata: Metadata = {
  title: "타임머신 — 만약에 샀다면? | What-If Simulator",
  description:
    "과거에 이 종목을 샀다면 지금 얼마? 코로나 바닥 NVDA, 금융위기 AAPL — 1분 시뮬레이션. PivoxQuant Time Machine.",
  alternates: { canonical: "/simulator/what-if" },
  openGraph: {
    title: "PivoxQuant — 타임머신 시뮬레이터",
    description:
      "과거에 투자했다면 지금 얼마? 1분 시뮬레이션으로 확인하세요.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "PivoxQuant — If You Had Invested...",
    description:
      "Simulate any past investment in 60 seconds. Free, no signup.",
  },
};

function LoadingFallback() {
  // v3 Vantablack: full-bleed ink background + pq-skeleton-dark shimmer so
  // the Suspense fallback matches the live client surface (not a white flash).
  return (
    <main
      className="min-h-[100dvh]"
      style={{ backgroundColor: "var(--pq-ink)" }}
    >
      <div className="mx-auto w-full max-w-3xl px-4 py-10">
        <div className="pq-skeleton-dark h-6 w-32" />
        <div className="pq-skeleton-dark mt-4 h-12 w-64" />
        <div className="pq-skeleton-dark mt-2 h-5 w-80" />
        <div className="pq-skeleton-dark mt-8 h-72 rounded-sm" />
      </div>
    </main>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <WhatIfClient />
    </Suspense>
  );
}
