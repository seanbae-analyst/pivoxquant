import type { Metadata } from "next";

/* /journal has `"use client"` in page.tsx, blocking metadata export.
 * Without a sibling server layout the tab title falls back to the root
 * default. Server-only layout supplies metadata + delegates rendering.
 *
 * "Journal" = the user's own pre-trade decision-reflection feed (read-only).
 * Informational record only — not a recommendation, not a trade log. */
export const metadata: Metadata = {
  title: "Journal",
  description:
    "A quiet record of your own pre-trade reflections — the rationale you wrote before each decision, in your words.",
  alternates: { canonical: "/journal" },
  robots: { index: false, follow: false },
};

export default function JournalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
