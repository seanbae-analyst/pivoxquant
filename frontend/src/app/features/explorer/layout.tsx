import type { Metadata } from "next";

/* /features/explorer has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  title: "Stock Explorer — PivoxQuant",
  description:
    "한국 코스피/코스닥 + 미국 NASDAQ/NYSE — 한 검색창 한 시그널 카드. 정보 제공 목적의 관찰 도구.",
  alternates: { canonical: "/features/explorer" },
  openGraph: {
    title: "Stock Explorer — PivoxQuant",
    description:
      "한국 코스피/코스닥 + 미국 NASDAQ/NYSE — 한 검색창 한 시그널 카드. 정보 제공 목적의 관찰 도구.",
    url: "/features/explorer",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Stock Explorer — PivoxQuant",
    description:
      "한국 코스피/코스닥 + 미국 NASDAQ/NYSE — 한 검색창 한 시그널 카드. 정보 제공 목적의 관찰 도구.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
