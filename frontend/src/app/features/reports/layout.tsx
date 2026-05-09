import type { Metadata } from "next";

/* /features/reports has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  title: "Editorial Reports — PivoxQuant",
  description:
    "Weekly Memo · Brag Card · Earnings Pre-Brief · Risk Board — AI가 작성한 18종 PDF 리포트. 정보 제공 목적.",
  alternates: { canonical: "/features/reports" },
  openGraph: {
    title: "Editorial Reports — PivoxQuant",
    description:
      "Weekly Memo · Brag Card · Earnings Pre-Brief · Risk Board — AI가 작성한 18종 PDF 리포트. 정보 제공 목적.",
    url: "/features/reports",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Editorial Reports — PivoxQuant",
    description:
      "Weekly Memo · Brag Card · Earnings Pre-Brief · Risk Board — AI가 작성한 18종 PDF 리포트. 정보 제공 목적.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
