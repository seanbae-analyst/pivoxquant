import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market Overview",
  description:
    "Macro indicators and sector performance — S&P 500, NASDAQ, KOSPI, KOSDAQ, VIX, USD/KRW, gold, oil, and bitcoin.",
  alternates: { canonical: "/market" },
  robots: { index: false, follow: false },
};

export default function MarketLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
