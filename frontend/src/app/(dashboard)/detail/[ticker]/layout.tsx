import type { Metadata } from "next";

import { normalizeTicker, tickerToName } from "@/lib/format";

interface DetailLayoutProps {
  children: React.ReactNode;
  params: Promise<{ ticker: string }>;
}

/**
 * Per-ticker metadata. Detail pages live behind the dashboard so we keep them
 * out of the search index (consistent with other authenticated routes).
 *
 * Tab title is name-first (audit FINDING-013): "삼성전자 005930 · Equity
 * Dossier" — a naked code in <title> is the most-impoverished form of a
 * company name and surfaces in history / bookmarks / OS task switcher.
 * The exchange suffix (.KS/.KQ) is stripped for display per the ticker-display
 * rule (it never surfaces to users); the canonical URL keeps the full ticker so
 * routing/resolution is unaffected. The static seed covers the seed dataset +
 * KOSPI/KOSDAQ majors; the long tail falls back to the bare (stripped) code.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const upper = (ticker ?? "").toUpperCase();
  const name = tickerToName(upper);
  // Display code with the exchange suffix stripped: "005930.KS" → "005930".
  const code = normalizeTicker(upper);
  // "삼성전자 005930" when the name is known, else just the (stripped) code.
  const label = name ? `${name} ${code}` : code;

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
