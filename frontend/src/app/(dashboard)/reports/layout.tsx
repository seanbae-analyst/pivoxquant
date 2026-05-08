import type { Metadata } from "next";

/* /reports has `"use client"` in its page.tsx, which forbids exporting
 * `metadata`. Without a sibling server-component layout.tsx the tab
 * title falls back to the root layout default ("PivoxQuant — …"),
 * losing per-route SEO + breadcrumb context. This server-only layout
 * supplies the metadata while children continue to render the existing
 * client page tree unchanged. */
export const metadata: Metadata = {
  title: "Reports",
  description:
    "Your CFO archive — weekly memos, brag cards, earnings pre-briefs, and risk notes generated for your book.",
  alternates: { canonical: "/reports" },
  robots: { index: false, follow: false },
};

export default function ReportsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
