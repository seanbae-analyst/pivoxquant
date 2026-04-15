import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio",
  description:
    "Track your stock positions, P&L, signals, and per-asset risk. Add, buy more, sell, and edit positions across US and Korean markets.",
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
