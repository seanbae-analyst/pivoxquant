import type { Metadata } from "next";

/* /features/dashboard has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  // Wave C-2 SEO (2026-05-17): root template adds " | PivoxQuant".
  title: "Dashboard",
  description:
    "당신의 포트폴리오 한 화면 — 시그널, 가격, 리스크, 리포트가 한 자리에. 정보 제공 목적의 관찰 도구.",
  alternates: { canonical: "/features/dashboard" },
  openGraph: {
    title: "Dashboard — PivoxQuant",
    description:
      "당신의 포트폴리오 한 화면 — 시그널, 가격, 리스크, 리포트가 한 자리에. 정보 제공 목적의 관찰 도구.",
    url: "/features/dashboard",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Dashboard — PivoxQuant",
    description:
      "당신의 포트폴리오 한 화면 — 시그널, 가격, 리스크, 리포트가 한 자리에. 정보 제공 목적의 관찰 도구.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
