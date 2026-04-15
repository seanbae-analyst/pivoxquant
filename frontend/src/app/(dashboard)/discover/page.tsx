"use client";

import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import { useDiscover } from "@/lib/hooks";
import type { DiscoverResult } from "@/lib/types";
import { ScoreBar } from "@/components/dashboard/score-bar";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  RefreshCw,
  Compass,
  ArrowUpDown,
  ChevronDown,
} from "lucide-react";

/* ── Filters ── */

const SIGNAL_FILTERS = ["All", "POSITIVE", "NEGATIVE", "NEUTRAL"] as const;
type SignalFilter = (typeof SIGNAL_FILTERS)[number];

type SortKey = "score" | "ticker" | "change_pct";
type SortDir = "asc" | "desc";

/* ── Signal Badge ── */

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
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
        cls,
      )}
    >
      {label}
    </span>
  );
}

/* ── Discover Row ── */

function DiscoverRow({
  item,
  onClick,
}: {
  item: DiscoverResult;
  onClick: () => void;
}) {
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

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50 active:bg-slate-100"
    >
      {/* Ticker + Name */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-900">
            {item.ticker}
          </span>
          {item.already_owned && (
            <span className="rounded bg-purple-50 px-1.5 py-0.5 text-[10px] font-semibold text-purple-600">
              보유중
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 truncate mt-0.5">{item.name}</p>
      </div>

      {/* Price + Change */}
      <div className="text-right shrink-0 min-w-[70px]">
        <p className="text-sm font-semibold tabular-nums text-slate-900">
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

      {/* Score bar mini + Badge */}
      <div className="hidden sm:flex items-center gap-2 shrink-0">
        <ScoreBar score={item.score} mini />
        <SignalBadge signal={item.signal} />
      </div>
      <div className="flex sm:hidden shrink-0">
        <SignalBadge signal={item.signal} />
      </div>
    </button>
  );
}

/* ── Sort Button ── */

function SortButton({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const isActive = currentKey === sortKey;

  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={cn(
        "flex items-center gap-1 text-xs font-medium transition-colors",
        isActive ? "text-purple-600" : "text-slate-500 hover:text-slate-700",
      )}
    >
      {label}
      {isActive && (
        <ChevronDown
          className={cn(
            "h-3 w-3 transition-transform",
            currentDir === "asc" && "rotate-180",
          )}
        />
      )}
    </button>
  );
}

/* ── Page ── */

export default function DiscoverPage() {
  const router = useRouter();
  const { data, isLoading, mutate } = useDiscover();
  const [filter, setFilter] = useState<SignalFilter>("All");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [scanning, setScanning] = useState(false);

  const results = useMemo(() => data?.results ?? [], [data?.results]);

  /* ── Filter + Sort ── */
  const processed = useMemo(() => {
    let items = [...results];

    // Filter
    if (filter !== "All") {
      items = items.filter((s) => s.signal === filter);
    }

    // Sort
    items.sort((a, b) => {
      let diff = 0;
      switch (sortKey) {
        case "score":
          diff = (a?.score ?? 0) - (b?.score ?? 0);
          break;
        case "ticker":
          diff = (a?.ticker ?? "").localeCompare(b?.ticker ?? "");
          break;
        case "change_pct":
          diff = (a?.change_pct ?? 0) - (b?.change_pct ?? 0);
          break;
      }
      return sortDir === "desc" ? -diff : diff;
    });

    return items;
  }, [results, filter, sortKey, sortDir]);

  /* ── Toggle sort ── */
  const handleSort = useCallback(
    (key: SortKey) => {
      if (key === sortKey) {
        setSortDir((d) => (d === "desc" ? "asc" : "desc"));
      } else {
        setSortKey(key);
        setSortDir("desc");
      }
    },
    [sortKey],
  );

  /* ── Force scan ── */
  const handleScan = useCallback(async () => {
    setScanning(true);
    try {
      await apiFetch(`${API.discover}?force=1`);
      await mutate();
    } catch {
      // silent — SWR will show stale data
    } finally {
      setScanning(false);
    }
  }, [mutate]);

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-5">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="signal" />

        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">탐색</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              퀀트 엔진이 분석한 유망 종목을 발굴하세요
            </p>
          </div>
          <button
            type="button"
            onClick={handleScan}
            disabled={scanning}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all",
              "bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", scanning && "animate-spin")}
            />
            스캔
          </button>
        </div>

        {/* ── Filter pills ── */}
        <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
          {SIGNAL_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "filter-pill whitespace-nowrap",
                filter === f && "active",
              )}
            >
              {f === "All" ? "전체" : f.charAt(0) + f.slice(1).toLowerCase()}
              {f !== "All" && (
                <span className="ml-1 tabular-nums">
                  ({results.filter((s) => s.signal === f).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Sort bar ── */}
        <div className="flex items-center gap-4 px-1">
          <ArrowUpDown className="h-3.5 w-3.5 text-slate-400" />
          <SortButton
            label="점수"
            sortKey="score"
            currentKey={sortKey}
            currentDir={sortDir}
            onSort={handleSort}
          />
          <SortButton
            label="티커"
            sortKey="ticker"
            currentKey={sortKey}
            currentDir={sortDir}
            onSort={handleSort}
          />
          <SortButton
            label="변동"
            sortKey="change_pct"
            currentKey={sortKey}
            currentDir={sortDir}
            onSort={handleSort}
          />
          <span className="ml-auto text-xs text-slate-400 tabular-nums">
            {processed.length}개 종목
          </span>
        </div>

        {/* ── Loading ── */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : processed.length === 0 ? (
          /* ── Empty state ── */
          <EmptyState
            icon={<Compass className="h-8 w-8" />}
            title={
              results.length === 0
                ? "스캔된 종목 없음"
                : "해당하는 종목 없음"
            }
            description={
              results.length === 0
                ? "스캔 버튼을 눌러 60개 종목을 퀀트 엔진으로 분석해 보세요."
                : "다른 필터를 선택해 보세요."
            }
          />
        ) : (
          /* ── Results list ── */
          <div className="sp-card overflow-hidden divide-y divide-slate-100">
            {processed.map((item) => (
              <DiscoverRow
                key={item.ticker}
                item={item}
                onClick={() => router.push(`/detail/${item.ticker}`)}
              />
            ))}
          </div>
        )}

        {/* ── Cached indicator ── */}
        {data?.cached && data.cached_at && (
          <p className="text-center text-xs text-slate-400">
            캐시됨:{" "}
            {new Date(data.cached_at).toLocaleTimeString("ko-KR", {
              hour: "numeric",
              minute: "2-digit",
            })}
          </p>
        )}
      </div>
    </ErrorBoundary>
  );
}
