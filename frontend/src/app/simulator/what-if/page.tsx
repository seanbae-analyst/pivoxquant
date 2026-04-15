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
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <div className="h-6 w-32 animate-pulse rounded-md bg-slate-200" />
      <div className="mt-4 h-12 w-64 animate-pulse rounded-md bg-slate-200" />
      <div className="mt-2 h-5 w-80 animate-pulse rounded-md bg-slate-100" />
      <div className="mt-8 h-72 animate-pulse rounded-2xl bg-slate-100" />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <WhatIfClient />
    </Suspense>
  );
}
