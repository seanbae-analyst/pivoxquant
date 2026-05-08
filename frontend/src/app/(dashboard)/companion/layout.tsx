import type { Metadata } from "next";

/* /companion has `"use client"` in page.tsx, blocking metadata export.
 * Without a sibling server layout the tab title falls back to the root
 * default. Server-only layout supplies metadata + delegates rendering. */
export const metadata: Metadata = {
  title: "Companion",
  description:
    "Quiet check-ins on how you are observing the market — investor companion notes, informational only.",
  alternates: { canonical: "/companion" },
  robots: { index: false, follow: false },
};

export default function CompanionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
