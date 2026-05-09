import type { Metadata } from "next";

/* /features/global-desk has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  title: "Global Desk — PivoxQuant",
  description:
    "한국과 미국 시장을 한 데스크에서. 글로벌 시세 통합 피드, 환율, 매크로 관찰. 정보 제공 목적.",
  alternates: { canonical: "/features/global-desk" },
  openGraph: {
    title: "Global Desk — PivoxQuant",
    description:
      "한국과 미국 시장을 한 데스크에서. 글로벌 시세 통합 피드, 환율, 매크로 관찰. 정보 제공 목적.",
    url: "/features/global-desk",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Global Desk — PivoxQuant",
    description:
      "한국과 미국 시장을 한 데스크에서. 글로벌 시세 통합 피드, 환율, 매크로 관찰. 정보 제공 목적.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
