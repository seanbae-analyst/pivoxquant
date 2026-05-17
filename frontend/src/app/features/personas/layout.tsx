import type { Metadata } from "next";

/* /features/personas has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  // Wave C-2 SEO (2026-05-17): root template adds " | PivoxQuant".
  title: "Investor Personas",
  description:
    "8가지 투자자 유형으로 본 당신의 거래 패턴 — 본인 거래 회고 데이터 기반. 정보 제공 목적의 관찰 도구.",
  alternates: { canonical: "/features/personas" },
  openGraph: {
    title: "Investor Personas — PivoxQuant",
    description:
      "8가지 투자자 유형으로 본 당신의 거래 패턴 — 본인 거래 회고 데이터 기반. 정보 제공 목적의 관찰 도구.",
    url: "/features/personas",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Investor Personas — PivoxQuant",
    description:
      "8가지 투자자 유형으로 본 당신의 거래 패턴 — 본인 거래 회고 데이터 기반. 정보 제공 목적의 관찰 도구.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
