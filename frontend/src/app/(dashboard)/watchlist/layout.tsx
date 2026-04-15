import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Watchlist",
  description:
    "Your custom stock watchlist with live prices, signals, and quick navigation to detail pages.",
  alternates: { canonical: "/watchlist" },
  robots: { index: false, follow: false },
};

export default function WatchlistLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
