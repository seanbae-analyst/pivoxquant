import type { Metadata } from "next";

/* /features/pre-trade has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  // Wave C-2 SEO (2026-05-17): root template adds " | PivoxQuant".
  title: "Pre-Trade Reflection",
  description:
    "거래 전 5문항 자기 검토 + 24시간 쿨다운 — 충동 매매를 줄이는 관찰 보조 도구. 정보 제공 목적.",
  alternates: { canonical: "/features/pre-trade" },
  openGraph: {
    title: "Pre-Trade Reflection — PivoxQuant",
    description:
      "거래 전 5문항 자기 검토 + 24시간 쿨다운 — 충동 매매를 줄이는 관찰 보조 도구. 정보 제공 목적.",
    url: "/features/pre-trade",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Pre-Trade Reflection — PivoxQuant",
    description:
      "거래 전 5문항 자기 검토 + 24시간 쿨다운 — 충동 매매를 줄이는 관찰 보조 도구. 정보 제공 목적.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
