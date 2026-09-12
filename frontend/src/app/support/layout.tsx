import type { Metadata } from "next";

/* /support has `"use client"` in page.tsx, which blocks a metadata export.
 * Without this server layout the page inherited the ROOT layout's
 * `alternates.canonical` — the homepage — so crawlers were told /support is a
 * duplicate of `/` (measured on production 2026-09-10:
 * <link rel="canonical" href="https://www.pivoxquant.com"> on /support).
 * Same pattern as (dashboard)/journal/layout.tsx. */
export const metadata: Metadata = {
  title: "Support",
  description:
    "Frequently asked questions, business information and how to reach PivoxQuant support.",
  alternates: { canonical: "/support" },
};

export default function SupportLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
