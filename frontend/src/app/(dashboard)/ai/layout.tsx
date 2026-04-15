import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Insights",
  description:
    "AI-generated portfolio insights — earnings tone, sector rotation, and risk summaries powered by Claude.",
  alternates: { canonical: "/ai" },
  robots: { index: false, follow: false },
};

export default function AiLayout({ children }: { children: React.ReactNode }) {
  return children;
}
