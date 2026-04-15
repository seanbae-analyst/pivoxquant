import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Discover",
  description:
    "Find high-potential stocks analyzed by our quant engine. Filter by signal, sort by score, and scan the universe on demand.",
  alternates: { canonical: "/discover" },
  robots: { index: false, follow: false },
};

export default function DiscoverLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
