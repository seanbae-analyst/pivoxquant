import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio",
  description:
    "Track your stock positions, P&L, signals, and per-asset risk. Record additions, reductions, and edits across US and Korean markets — journaling only.",
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
