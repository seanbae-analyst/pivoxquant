import type { Metadata } from "next";

import { tickerToName } from "@/lib/format";

interface DetailLayoutProps {
  children: React.ReactNode;
  params: Promise<{ ticker: string }>;
}

/**
 * Per-ticker metadata. Detail pages live behind the dashboard so we keep them
 * out of the search index (consistent with other authenticated routes).
 *
 * Tab title is name-first (audit FINDING-013): "삼성전자 005930.KS · Equity
 * Dossier" — a naked code in <title> is the most-impoverished form of a
 * company name and surfaces in history / bookmarks / OS task switcher.
 * The static seed covers the seed dataset + KOSPI/KOSDAQ majors; the long
 * tail still falls back to the bare ticker (better a code than a wrong name).
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const upper = (ticker ?? "").toUpperCase();
  const name = tickerToName(upper);
  // "삼성전자 005930.KS" when the name is known, else just the ticker.
  const label = name ? `${name} ${upper}` : upper;

  return {
    title: upper ? `${label} · Equity Dossier` : "Equity Dossier",
    description: upper
      ? `Quant signal, technical/fundamental/sentiment scores, key metrics, price chart, and recent news for ${label}.`
      : "Stock detail with quant scores, key metrics, chart, and news.",
    alternates: {
      canonical: upper ? `/detail/${upper}` : "/detail",
    },
    robots: { index: false, follow: false },
  };
}

export default function DetailLayout({ children }: DetailLayoutProps) {
  return children;
}
