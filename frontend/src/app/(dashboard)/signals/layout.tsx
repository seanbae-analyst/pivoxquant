import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Signals",
  description:
    "Quant signals across your universe — technical, fundamental, sentiment, and quant-model pillars combined into a single score.",
  alternates: { canonical: "/signals" },
  robots: { index: false, follow: false },
};

export default function SignalsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
