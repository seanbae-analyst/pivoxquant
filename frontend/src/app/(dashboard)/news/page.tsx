"use client";

import { useState } from "react";
import useSWR from "swr";
import { usePortfolio } from "@/lib/hooks";
import { API } from "@/lib/endpoints";
import { Newspaper, ExternalLink } from "lucide-react";

interface NewsItem {
  title: string;
  summary: string;
  source: string;
  link: string;
  published: string;
  sentiment: string;
}

const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => r.json());

function sentimentBadge(s: string) {
  if (s === "positive" || s === "bullish")
    return "bg-emerald-500/15 text-emerald-400";
  if (s === "negative" || s === "bearish")
    return "bg-red-500/15 text-red-400";
  return "bg-amber-500/15 text-amber-400";
}

function TickerNews({ ticker }: { ticker: string }) {
  const { data, isLoading } = useSWR<{ news: NewsItem[] }>(
    API.market.news(ticker),
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 120_000 },
  );

  if (isLoading)
    return (
      <div className="flex items-center justify-center py-8">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );

  if (!data?.news?.length)
    return (
      <p className="py-4 text-[13px] text-zinc-600">No news available.</p>
    );

  return (
    <div className="space-y-4">
      {data.news.map((item, i) => (
        <div
          key={`${ticker}-${i}`}
          className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <a
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-center gap-1.5 text-sm font-semibold text-white hover:text-cyan-400 spring-transition"
              >
                {item.title}
                <ExternalLink
                  size={12}
                  className="opacity-0 group-hover:opacity-100 spring-transition"
                />
              </a>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-400 line-clamp-2">
                {item.summary}
              </p>
              <div className="mt-2 flex items-center gap-3 text-[13px] text-zinc-600">
                <span>{item.source}</span>
                <span>
                  {new Date(item.published).toLocaleDateString()}
                </span>
              </div>
            </div>
            <span
              className={`shrink-0 rounded-md px-2.5 py-1 text-[9px] font-bold capitalize ${sentimentBadge(item.sentiment)}`}
            >
              {item.sentiment}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function NewsFeedPage() {
  const { data: portfolio } = usePortfolio();
  const tickers =
    portfolio?.positions
      ?.slice(0, 5)
      .map((p) => p.ticker) ?? [];
  const [activeTab, setActiveTab] = useState("All");

  if (!portfolio)
    return (
      <div className="flex items-center justify-center py-20">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );

  const tabs = ["All", ...tickers];
  const visibleTickers =
    activeTab === "All" ? tickers : [activeTab];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          News Feed
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Latest news for your portfolio holdings
        </p>
      </div>

      {/* Tab pills */}
      {tickers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-md px-2.5 py-1 text-[9px] font-bold spring-transition transition-all duration-300 ${
                activeTab === tab
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                  : "glass-surface text-zinc-400 hover:text-white"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      )}

      {/* News sections */}
      {tickers.length === 0 ? (
        <div className="glass-surface rounded-2xl py-12 text-center">
          <Newspaper className="mx-auto h-10 w-10 text-zinc-600" />
          <p className="mt-3 text-[13px] text-zinc-600">
            Add positions to your portfolio to see news.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {visibleTickers.map((ticker) => (
            <section key={ticker}>
              <h2 className="mb-4 text-lg font-semibold text-white">
                {ticker}
              </h2>
              <TickerNews ticker={ticker} />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
