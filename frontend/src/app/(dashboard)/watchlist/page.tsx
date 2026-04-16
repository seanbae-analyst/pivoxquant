"use client";

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn, isKoreanTicker } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import { useWatchlist } from "@/lib/hooks";
import type { WatchlistItem, LookupResult } from "@/lib/types";
import { ScoreBar } from "@/components/dashboard/score-bar";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { Search, Plus, X, Star } from "lucide-react";

/* ── Signal Badge (local) ── */

function SignalBadge({ signal }: { signal: string }) {
  const cls =
    signal === "POSITIVE"
      ? "signal-positive"
      : signal === "NEGATIVE"
        ? "signal-negative"
        : "signal-neutral";
  const label =
    signal === "POSITIVE"
      ? "Positive"
      : signal === "NEGATIVE"
        ? "Negative"
        : "Neutral";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        cls,
      )}
    >
      {label}
    </span>
  );
}

/* ── Search Dropdown ── */

function SearchDropdown({
  results,
  isLoading,
  onSelect,
}: {
  results: LookupResult[];
  isLoading: boolean;
  onSelect: (r: LookupResult) => void;
}) {
  if (!isLoading && results.length === 0) return null;

  return (
    <div className="absolute left-0 right-0 top-full mt-1 z-30 rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden">
      {isLoading ? (
        <div className="px-4 py-3 space-y-2">
          <div className="skeleton h-4 w-32" />
          <div className="skeleton h-4 w-24" />
        </div>
      ) : (
        <ul className="max-h-64 overflow-y-auto scrollbar-thin">
          {results.map((r) => {
            const isPositive = (r?.change_pct ?? 0) >= 0;
            return (
              <li key={r?.ticker ?? "unknown"}>
                <button
                  type="button"
                  onClick={() => onSelect(r)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50 active:bg-slate-100"
                >
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold text-slate-900">
                      {isKoreanTicker(r?.ticker ?? "") ? (r?.name || r?.ticker || "\u2014") : (r?.ticker ?? "\u2014")}
                    </span>
                    <span className="ml-2 text-xs text-slate-500 truncate">
                      {isKoreanTicker(r?.ticker ?? "") ? (r?.ticker ?? "") : (r?.name ?? "")}
                    </span>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-sm font-semibold tabular-nums text-slate-900">
                      {r?.price != null
                        ? `$${r.price.toLocaleString("en-US", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}`
                        : "\u2014"}
                    </span>
                    <span
                      className={cn(
                        "ml-2 text-xs font-semibold tabular-nums",
                        isPositive ? "text-emerald-600" : "text-red-500",
                      )}
                    >
                      {fmtPct(r?.change_pct ?? 0)}
                    </span>
                  </div>
                  <Plus className="h-4 w-4 shrink-0 text-slate-400" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/* ── Watchlist Row ── */

function WatchlistRow({
  item,
  onRemove,
  onClick,
}: {
  item: WatchlistItem;
  onRemove: (id: number) => void;
  onClick: () => void;
}) {
  const [removing, setRemoving] = useState(false);
  const isPositive = (item?.change_pct ?? 0) >= 0;
  const priceDisplay =
    item?.price == null
      ? "\u2014"
      : item.currency === "KRW"
        ? `₩${Math.round(item.price).toLocaleString("ko-KR")}`
        : `$${item.price.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`;

  const handleRemove = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setRemoving(true);
    try {
      await apiFetch(API.watchlist.remove(item.id), { method: "DELETE" });
      onRemove(item.id);
    } catch {
      toast.error("관심종목에서 제거하지 못했습니다");
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className="sp-card p-4 w-full text-left transition-all hover:shadow-md active:scale-[0.99] cursor-pointer"
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: ticker + name */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900">
              {isKoreanTicker(item.ticker, item.is_korean) ? (item.name || item.ticker) : item.ticker}
            </span>
            <SignalBadge signal={item.signal} />
          </div>
          <p className="text-xs text-slate-500 truncate mt-0.5">
            {isKoreanTicker(item.ticker, item.is_korean) ? `${item.ticker} · KRX` : item.name}
          </p>
        </div>

        {/* Right: price + change + remove */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <p className="text-sm font-bold tabular-nums text-slate-900">
              {priceDisplay}
            </p>
            <p
              className={cn(
                "text-xs font-semibold tabular-nums",
                isPositive ? "text-emerald-600" : "text-red-500",
              )}
            >
              {fmtPct(item?.change_pct ?? 0)}
            </p>
          </div>
          <button
            type="button"
            onClick={handleRemove}
            disabled={removing}
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-full transition-colors",
              "text-slate-400 hover:text-red-500 hover:bg-red-50",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
            title="관심종목에서 제거"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Score bar mini */}
      <div className="mt-3">
        <ScoreBar score={item.score} mini />
      </div>
    </div>
  );
}

/* ── Page ── */

export default function WatchlistPage() {
  const router = useRouter();
  const { data, isLoading, mutate } = useWatchlist();

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<LookupResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const watchlist = useMemo(() => data?.watchlist ?? [], [data?.watchlist]);

  /* ── Close dropdown on click outside ── */
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        searchRef.current &&
        !searchRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /* ── Debounced search ── */
  const handleSearch = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (value.trim().length < 1) {
        setSearchResults([]);
        setShowDropdown(false);
        return;
      }

      debounceRef.current = setTimeout(async () => {
        setSearching(true);
        setShowDropdown(true);
        try {
          const res = await fetch(API.market.lookup(value.trim()), {
            credentials: "include",
          });
          if (!res.ok) throw new Error("Search failed");
          const data = await res.json();
          if (Array.isArray(data)) {
            setSearchResults(data);
          } else if (data.results) {
            setSearchResults(data.results);
          } else if (data.ticker) {
            setSearchResults([data]);
          } else {
            setSearchResults([]);
          }
        } catch {
          setSearchResults([]);
        } finally {
          setSearching(false);
        }
      }, 300);
    },
    [],
  );

  /* ── Add to watchlist ── */
  const handleAdd = useCallback(
    async (result: LookupResult) => {
      setShowDropdown(false);
      setQuery("");
      setSearchResults([]);

      // Check if already in watchlist
      if (watchlist.some((w) => w.ticker === result.ticker)) {
        toast.info(`${result.ticker}은(는) 이미 관심종목에 있습니다`);
        return;
      }

      try {
        await apiFetch(API.watchlist.add, {
          method: "POST",
          body: JSON.stringify({ ticker: result.ticker }),
        });
        toast.success(`${result.ticker} 관심종목에 추가됐습니다`);
        await mutate();
      } catch {
        toast.error(`${result.ticker} 추가에 실패했습니다`);
      }
    },
    [watchlist, mutate],
  );

  /* ── Remove from watchlist ── */
  const handleRemove = useCallback(
    async (id: number) => {
      try {
        await apiFetch(API.watchlist.remove(id), { method: "DELETE" });
        toast.success("관심종목에서 제거됐습니다");
        await mutate();
      } catch {
        toast.error("관심종목에서 제거하지 못했습니다");
      }
    },
    [mutate],
  );

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-5">
        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-900">관심종목</h1>
          <span className="text-sm text-slate-400 tabular-nums">
            {watchlist.length}개 종목
          </span>
        </div>

        {/* ── Signal disclaimer ── */}
        <DisclaimerBanner type="signal" />

        {/* ── Search bar ── */}
        <div ref={searchRef} className="relative">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => handleSearch(e.target.value)}
              onFocus={() => {
                if (searchResults.length > 0) setShowDropdown(true);
              }}
              placeholder="종목 검색 (AAPL, NVDA, TSLA...)"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4",
                "text-sm text-slate-900 placeholder:text-slate-400",
                "transition-all focus:border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-100",
              )}
            />
          </div>
          {showDropdown && (
            <SearchDropdown
              results={searchResults}
              isLoading={searching}
              onSelect={handleAdd}
            />
          )}
        </div>

        {/* ── Loading ── */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : watchlist.length === 0 ? (
          /* ── Empty state ── */
          <EmptyState
            icon={<Star className="h-8 w-8" />}
            title="관심종목 없음"
            description="관심 있는 종목을 추가해 보세요. 위 검색창에서 첫 번째 종목을 찾아 추가하세요."
          />
        ) : (
          /* ── Watchlist rows ── */
          <div className="space-y-3">
            {watchlist.map((item) => (
              <WatchlistRow
                key={item.id}
                item={item}
                onRemove={handleRemove}
                onClick={() => router.push(`/detail/${item.ticker}`)}
              />
            ))}
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
