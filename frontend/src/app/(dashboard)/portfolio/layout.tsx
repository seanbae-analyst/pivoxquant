import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio",
  // 2026-09-19: dropped "P&L, signals, and per-asset risk". The signal and
  // risk surfaces were pruned long ago, and P&L at market price is behind the
  // vendor-display flag — the description now names only what the page shows
  // with the flag off, which is the shipped default.
  description:
    "Your own record of what you hold, at the average cost you entered. Record additions, reductions, and edits across US and Korean markets — journaling only.",
  alternates: { canonical: "/portfolio" },
  robots: { index: false, follow: false },
};

export default function PortfolioLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
