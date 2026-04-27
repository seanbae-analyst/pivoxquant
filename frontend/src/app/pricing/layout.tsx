import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing — Free, Pro, Premium",
  description:
    "Three tiers — Free, Pro at 9,900 KRW / month, Premium at 19,900 KRW / month. Flat monthly fee. No trading commissions. No performance cut.",
  keywords: [
    "PivoxQuant pricing",
    "subscription",
    "research desk",
    "artifact membership",
    "Free Pro Premium",
  ],
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "PivoxQuant Pricing — Free, Pro, Premium",
    description:
      "Flat monthly fee. No trading commissions. No performance cut. Free is free; Pro is 9,900 KRW / month; Premium is 19,900 KRW / month.",
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
