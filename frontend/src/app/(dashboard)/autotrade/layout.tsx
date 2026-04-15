import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Autotrade",
  description:
    "Automated paper trading with kill switch, circuit breakers, and quant-driven signals (paper mode only).",
  alternates: { canonical: "/autotrade" },
  robots: { index: false, follow: false },
};

export default function AutotradeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
