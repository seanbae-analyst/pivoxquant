import type { Metadata } from "next";

/* /features/engine has `"use client"` in its page.tsx, which forbids
 * exporting `metadata`. SEO audit (2026-05-09 release-prep) found 7
 * /features/* directories with the same gap — adding a sibling
 * server-component layout.tsx supplies per-route SEO + OG context
 * while children continue to render the existing client page tree
 * unchanged. Mirrors the pattern PR #155 established for
 * /reports + /companion + /growth + /pre-trade.
 */
export const metadata: Metadata = {
  // Wave C-2 SEO (2026-05-17): top-level title runs through the
  // root layout template (`%s | PivoxQuant`), so the brand suffix
  // here previously produced "Quant Engine — PivoxQuant | PivoxQuant"
  // in the <title>. OG/Twitter titles below stay branded — they
  // bypass the template and need standalone context.
  title: "Quant Engine",
  description:
    "58개 퀀트 모델 + 7-Layer Risk Defense. 머신이 읽고, 사람이 결정합니다. 정보 제공 목적의 관찰 도구.",
  alternates: { canonical: "/features/engine" },
  openGraph: {
    title: "Quant Engine — PivoxQuant",
    description:
      "58개 퀀트 모델 + 7-Layer Risk Defense. 머신이 읽고, 사람이 결정합니다. 정보 제공 목적의 관찰 도구.",
    url: "/features/engine",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Quant Engine — PivoxQuant",
    description:
      "58개 퀀트 모델 + 7-Layer Risk Defense. 머신이 읽고, 사람이 결정합니다. 정보 제공 목적의 관찰 도구.",
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
