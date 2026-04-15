import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Alerts",
  description:
    "Price, signal, risk, and trade notifications for your portfolio and watchlist.",
  alternates: { canonical: "/alerts" },
  robots: { index: false, follow: false },
};

export default function AlertsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
