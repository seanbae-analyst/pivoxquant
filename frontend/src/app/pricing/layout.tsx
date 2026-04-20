import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing — Free, Pro, Premium",
  description:
    "Three tiers — Free, Pro at ₩9,900/month, Premium at ₩19,900/month. Quant scoring, risk defense, AI Assistant, and paper trading.",
  keywords: [
    "PivoxQuant 가격",
    "주식 분석 구독",
    "AI 투자 가격",
    "pivoxquant pricing",
    "subscription",
  ],
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "PivoxQuant Pricing — Free, Pro, Premium",
    description:
      "AI Quant Research Tool pricing. Start free; upgrade for full quant scoring, AI Assistant, and risk dashboard.",
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
