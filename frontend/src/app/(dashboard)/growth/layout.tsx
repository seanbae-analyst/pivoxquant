import type { Metadata } from "next";

/* /growth has `"use client"` in page.tsx, blocking metadata export.
 * Without a sibling server layout the tab title falls back to the root
 * default. Server-only layout supplies metadata + delegates rendering.
 *
 * Display label in nav is "Journal" — see terminal-sidebar.tsx — the
 * route name avoids capital-market "growth" connotations under KR
 * advisory law. The metadata title mirrors the user-facing label. */
export const metadata: Metadata = {
  title: "Journal",
  description:
    "A quiet record of how you observed the market — daily score, weekly summary, and your own notes.",
  alternates: { canonical: "/growth" },
  robots: { index: false, follow: false },
};

export default function GrowthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
