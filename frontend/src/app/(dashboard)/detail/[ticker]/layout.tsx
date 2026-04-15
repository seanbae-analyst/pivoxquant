import type { Metadata } from "next";

interface DetailLayoutProps {
  children: React.ReactNode;
  params: Promise<{ ticker: string }>;
}

/**
 * Per-ticker metadata. Detail pages live behind the dashboard so we keep them
 * out of the search index (consistent with other authenticated routes).
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const upper = (ticker ?? "").toUpperCase();

  return {
    title: upper ? `${upper} — Stock Detail` : "Stock Detail",
    description: upper
      ? `Quant signal, technical/fundamental/sentiment scores, key metrics, price chart, and recent news for ${upper}.`
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
