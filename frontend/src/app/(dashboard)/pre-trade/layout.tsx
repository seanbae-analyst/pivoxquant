import type { Metadata } from "next";

/* /pre-trade has `"use client"` in page.tsx, blocking metadata export.
 * Without a sibling server layout the tab title falls back to the root
 * default. Server-only layout supplies metadata + delegates rendering. */
export const metadata: Metadata = {
  title: "Pre-Trade",
  description:
    "Seven questions before every observation — a structured pre-trade checklist, informational only.",
  alternates: { canonical: "/pre-trade" },
  robots: { index: false, follow: false },
};

export default function PreTradeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
