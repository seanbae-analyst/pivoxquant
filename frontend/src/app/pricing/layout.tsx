import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing — Observer, Operator, Partner",
  description:
    "Three tiers — Observer (free), Operator at 9,900 KRW / month, Partner at 19,900 KRW / month. Flat monthly fee. No trading commissions. No performance cut.",
  keywords: [
    "PivoxQuant pricing",
    "subscription",
    "research desk",
    "artifact membership",
    "Observer Operator Partner",
  ],
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "PivoxQuant Pricing — Observer, Operator, Partner",
    description:
      "Flat monthly fee. No trading commissions. No performance cut. Observer is free; Operator is 9,900 KRW / month; Partner is 19,900 KRW / month.",
    url: "/pricing",
    type: "website",
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
