import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Risk Dashboard",
  description:
    "Monitor portfolio risk with VaR, drawdown, stress tests, component expected shortfall, and the 7-Layer Risk Defense status.",
  alternates: { canonical: "/risk" },
  robots: { index: false, follow: false },
};

export default function RiskLayout({ children }: { children: React.ReactNode }) {
  return children;
}
