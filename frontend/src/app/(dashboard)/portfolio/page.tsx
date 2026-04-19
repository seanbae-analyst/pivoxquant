"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn, isKoreanTicker } from "@/lib/utils";
import { fmtUsd, fmtKrw, fmtPct, pnlColor } from "@/lib/format";
import { usePortfolio } from "@/lib/hooks";
import type { Position, LookupResult, SearchResult, PortfolioResponse } from "@/lib/types";
import { ScoreBar } from "@/components/dashboard/score-bar";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ModalShell } from "@/components/ui/modal-shell";
import {
  Briefcase,
  Plus,
  Search,
  X,
  MoreVertical,
  Pencil,
  Trash2,
  TrendingUp,
  TrendingDown,
  ArrowUpCircle,
  ArrowDownCircle,
} from "lucide-react";

/* ================================================================
   Local UI helpers
   ================================================================ */

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

function formatPrice(price: number, currency: "USD" | "KRW"): string {
  if (currency === "KRW") return fmtKrw(price);
  return fmtUsd(price);
}

/* ================================================================
   Modal overlay wrapper — uses ModalShell for ESC + focus trap.
   ================================================================ */

function ModalOverlay({
  children,
  onClose,
  ariaLabel,
}: {
  children: React.ReactNode;
  onClose: () => void;
  ariaLabel?: string;
}) {
  return (
    <ModalShell onClose={onClose} ariaLabel={ariaLabel}>
      {children}
    </ModalShell>
  );
}

/* ================================================================
   Search dropdown (reused from watchlist pattern)
   ================================================================ */

function SearchDropdown({
  results,
  isLoading,
  onSelect,
}: {
  results: SearchResult[];
  isLoading: boolean;
  onSelect: (r: SearchResult) => void;
}) {
  if (!isLoading && results.length === 0) return null;

  return (
    <div className="absolute left-0 right-0 top-full mt-1 z-50 rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden">
      {isLoading ? (
        <div className="px-4 py-3 space-y-2">
          <div className="skeleton h-4 w-32" />
          <div className="skeleton h-4 w-24" />
        </div>
      ) : (
        <ul className="max-h-64 overflow-y-auto scrollbar-thin">
          {results.map((r) => (
            <li key={r.ticker}>
              <button
                type="button"
                onClick={() => onSelect(r)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50 active:bg-slate-100"
              >
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-bold text-slate-900">
                    {isKoreanTicker(r.ticker, r.is_korean) ? (r.name || r.ticker) : r.ticker}
                  </span>
                  <span className="ml-2 text-xs text-slate-500 truncate">
                    {isKoreanTicker(r.ticker, r.is_korean) ? r.ticker : r.name}
                  </span>
                </div>
                <div className="text-right shrink-0">
                  {r.exchange && (
                    <span className="text-[10px] text-slate-400 font-medium">
                      {r.exchange}
                    </span>
                  )}
                  {r.is_korean && (
                    <span className="ml-1 inline-flex items-center rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 border border-blue-100">
                      KR
                    </span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ================================================================
   Add Position Modal
   ================================================================ */

function AddPositionModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selected, setSelected] = useState<LookupResult | null>(null);
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [avgCostTouched, setAvgCostTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* Close dropdown on click outside */
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /* B1: Debounced fuzzy search via /api/search */
  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    setSelected(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (value.trim().length < 1) {
      setSearchResults([]);
      setShowDropdown(false);
      setSearching(false);
      return;
    }

    setSearching(true);
    setShowDropdown(true);

    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(API.market.search(value.trim()), {
          credentials: "include",
        });
        if (!res.ok) throw new Error("Search failed");
        const data = await res.json();
        const parsed: SearchResult[] = data.results ?? [];
        setSearchResults(parsed);
        setShowDropdown(parsed.length > 0);
      } catch {
        setSearchResults([]);
        setShowDropdown(false);
      } finally {
        setSearching(false);
      }
    }, 300);
  }, []);

  /* B1+B4: When user selects from dropdown, look up price via exact match */
  const handleSelect = async (r: SearchResult) => {
    setQuery(r.ticker);
    setShowDropdown(false);
    setSearchResults([]);

    try {
      const res = await fetch(API.market.lookup(r.ticker), {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.ticker) {
          const lookup = data as LookupResult;
          setSelected(lookup);
          /* B2: Only auto-fill avgCost if user has NOT manually typed one */
          if (!avgCostTouched) setAvgCost(lookup.price.toString());
          return;
        }
      }
    } catch {
      /* lookup failed, proceed with search result only */
    }
    /* Fallback: use search result without price */
    setSelected({
      ticker: r.ticker,
      name: r.name,
      price: 0,
      currency: r.currency,
      is_korean: r.is_korean,
    });
  };

  const handleSubmit = async () => {
    if (submitting) return;

    let stock = selected;

    /* If no stock selected via dropdown, try to look up the typed ticker */
    if (!stock) {
      const trimmed = query.trim().toUpperCase();
      if (!trimmed) {
        toast.error("종목을 검색하고 선택해 주세요");
        return;
      }
      setSubmitting(true);
      try {
        const res = await fetch(API.market.lookup(trimmed), {
          credentials: "include",
        });
        if (!res.ok) throw new Error("Ticker not found");
        const data = await res.json();
        if (data.ticker) {
          stock = data as LookupResult;
          setSelected(stock);
        } else {
          toast.error("티커를 찾을 수 없습니다. 검색 결과에서 선택해 주세요.");
          setSubmitting(false);
          return;
        }
      } catch {
        toast.error("티커를 확인할 수 없습니다. 검색 결과에서 선택해 주세요.");
        setSubmitting(false);
        return;
      }
    }

    const sharesNum = parseFloat(shares);
    const costNum = parseFloat(avgCost);
    if (!sharesNum || sharesNum <= 0) {
      toast.error("올바른 수량을 입력해 주세요");
      setSubmitting(false);
      return;
    }
    if (!costNum || costNum <= 0) {
      toast.error("올바른 평균 단가를 입력해 주세요");
      setSubmitting(false);
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch(API.portfolio.addPosition, {
        method: "POST",
        body: JSON.stringify({
          ticker: stock.ticker,
          shares: sharesNum,
          avg_cost: costNum,
        }),
      });
      toast.success(`${stock.ticker} 포트폴리오에 추가됐습니다`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "포지션 추가에 실패했습니다",
      );
    } finally {
      setSubmitting(false);
    }
  };

  /* B3: Determine currency symbol for selected stock */
  const selectedCurrency = selected?.is_korean ? "KRW" : (selected?.currency === "KRW" ? "KRW" : "USD");

  return (
    <ModalOverlay onClose={onClose}>
      <div
        className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]"
        role="dialog"
        aria-modal="true"
        style={{ transform: "none" }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-slate-900">포지션 추가</h3>
          <button
            type="button"
            onClick={() => onClose()}
            className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Ticker search */}
        <div ref={searchRef} className="relative mb-4">
          <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
            종목
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => handleSearch(e.target.value)}
              onFocus={() => {
                if (searchResults.length > 0) setShowDropdown(true);
              }}
              placeholder="티커, 종목명, 한글명 검색... (예: nvidia, 삼성전자)"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-4",
                "text-sm text-slate-900 placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
          {showDropdown && (
            <SearchDropdown
              results={searchResults}
              isLoading={searching}
              onSelect={handleSelect}
            />
          )}
        </div>

        {/* B3: Selected stock preview with correct currency symbol */}
        {selected && selected.price > 0 && (
          <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-900">
                  {isKoreanTicker(selected.ticker, selected.is_korean) ? (selected.name || selected.ticker) : selected.ticker}
                </span>
                <span className="text-xs text-slate-500 truncate">
                  {isKoreanTicker(selected.ticker, selected.is_korean) ? selected.ticker : selected.name}
                </span>
                {selected.is_korean && (
                  <span className="inline-flex items-center rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 border border-blue-100">
                    KR
                  </span>
                )}
              </div>
              <span className="text-sm font-semibold tabular-nums text-slate-900">
                {formatPrice(selected.price, selectedCurrency as "USD" | "KRW")}
              </span>
            </div>
          </div>
        )}

        {/* Selected but no price yet */}
        {selected && selected.price === 0 && (
          <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900">
                {isKoreanTicker(selected.ticker, selected.is_korean) ? (selected.name || selected.ticker) : selected.ticker}
              </span>
              <span className="text-xs text-slate-500 truncate">
                {isKoreanTicker(selected.ticker, selected.is_korean) ? selected.ticker : selected.name}
              </span>
              {selected.is_korean && (
                <span className="inline-flex items-center rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 border border-blue-100">
                  KR
                </span>
              )}
            </div>
          </div>
        )}

        {/* Shares + Avg Cost */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              수량
            </label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="0"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              평균 단가 ({selectedCurrency === "KRW" ? "\u20A9" : "$"})
            </label>
            <input
              type="number"
              value={avgCost}
              onChange={(e) => {
                setAvgCost(e.target.value);
                setAvgCostTouched(true);
              }}
              placeholder="0.00"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              "flex-1 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {submitting ? "추가 중..." : "포지션 추가"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            취소
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}

/* ================================================================
   Buy More Modal
   ================================================================ */

function BuyMoreModal({
  position,
  onClose,
  onSuccess,
}: {
  position: Position;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState(position.current_price.toString());
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    const sharesNum = parseFloat(shares);
    const priceNum = parseFloat(price);
    if (!sharesNum || sharesNum <= 0) {
      toast.error("올바른 수량을 입력해 주세요");
      return;
    }
    if (!priceNum || priceNum <= 0) {
      toast.error("올바른 가격을 입력해 주세요");
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch(API.portfolio.buyMore(position.id), {
        method: "POST",
        body: JSON.stringify({ shares: sharesNum, price: priceNum }),
      });
      toast.success(`${position.ticker} ${sharesNum}주 추가 매수했습니다`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "추가 매수에 실패했습니다",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const totalCost =
    (parseFloat(shares) || 0) * (parseFloat(price) || 0);

  return (
    <ModalOverlay onClose={onClose}>
      <div
        className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-sm overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-emerald-600" />
            <h3 className="text-lg font-bold text-slate-900">
              {position.ticker} 추가 매수
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Current position info */}
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 mb-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>현재: {position.shares}주</span>
            <span>평균 단가: {formatPrice(position.avg_cost, position.currency)}</span>
          </div>
        </div>

        <div className="space-y-3 mb-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              매수 수량
            </label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="0"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              주당 가격
            </label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
        </div>

        {/* Total cost */}
        {totalCost > 0 && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 mb-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-700">
                총 매수 금액
              </span>
              <span className="text-sm font-bold tabular-nums text-emerald-700">
                {formatPrice(totalCost, position.currency)}
              </span>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              "flex-1 rounded-full bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-emerald-700 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {submitting ? "매수 중..." : "추가 매수"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            취소
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}

/* ================================================================
   Sell Shares Modal
   ================================================================ */

function SellSharesModal({
  position,
  onClose,
  onSuccess,
}: {
  position: Position;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState(position.current_price.toString());
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    const sharesNum = parseFloat(shares);
    const priceNum = parseFloat(price);
    if (!sharesNum || sharesNum <= 0) {
      toast.error("올바른 수량을 입력해 주세요");
      return;
    }
    if (sharesNum > position.shares) {
      toast.error(`보유 수량은 ${position.shares}주입니다`);
      return;
    }
    if (!priceNum || priceNum <= 0) {
      toast.error("올바른 가격을 입력해 주세요");
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch(API.portfolio.sellShares(position.id), {
        method: "POST",
        body: JSON.stringify({ shares: sharesNum, price: priceNum }),
      });
      toast.success(`${position.ticker} ${sharesNum}주 매도했습니다`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "매도에 실패했습니다",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const totalProceeds =
    (parseFloat(shares) || 0) * (parseFloat(price) || 0);
  const pnlPerShare =
    (parseFloat(price) || 0) - position.avg_cost;
  const estimatedPnl =
    (parseFloat(shares) || 0) * pnlPerShare;

  return (
    <ModalOverlay onClose={onClose}>
      <div
        className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-sm overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-500" />
            <h3 className="text-lg font-bold text-slate-900">
              {position.ticker} 매도
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Current position info */}
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 mb-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>보유: {position.shares}주</span>
            <span>평균 단가: {formatPrice(position.avg_cost, position.currency)}</span>
          </div>
        </div>

        <div className="space-y-3 mb-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              매도 수량
            </label>
            <div className="relative">
              <input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                placeholder="0"
                min="0"
                max={position.shares}
                step="any"
                className={cn(
                  "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                  "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                  "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
                )}
              />
              <button
                type="button"
                onClick={() => setShares(position.shares.toString())}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-200 transition-colors"
              >
                MAX
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              주당 가격
            </label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
        </div>

        {/* Proceeds + estimated P&L */}
        {totalProceeds > 0 && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 mb-5 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">
                매도 금액
              </span>
              <span className="text-sm font-bold tabular-nums text-slate-900">
                {formatPrice(totalProceeds, position.currency)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">
                예상 손익
              </span>
              <span
                className={cn(
                  "text-sm font-bold tabular-nums",
                  pnlColor(estimatedPnl),
                )}
              >
                {estimatedPnl >= 0 ? "+" : ""}
                {formatPrice(estimatedPnl, position.currency)}
              </span>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              "flex-1 rounded-full bg-red-500 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-red-600 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {submitting ? "매도 중..." : "매도하기"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            취소
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}

/* ================================================================
   Edit Position Modal
   ================================================================ */

function EditPositionModal({
  position,
  onClose,
  onSuccess,
}: {
  position: Position;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [shares, setShares] = useState(position.shares.toString());
  const [avgCost, setAvgCost] = useState(position.avg_cost.toString());
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    const sharesNum = parseFloat(shares);
    const costNum = parseFloat(avgCost);
    if (!sharesNum || sharesNum <= 0) {
      toast.error("올바른 수량을 입력해 주세요");
      return;
    }
    if (!costNum || costNum <= 0) {
      toast.error("올바른 평균 단가를 입력해 주세요");
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch(API.portfolio.editPosition(position.id), {
        method: "PUT",
        body: JSON.stringify({ shares: sharesNum, avg_cost: costNum }),
      });
      toast.success(`${position.ticker} 포지션이 수정됐습니다`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "포지션 수정에 실패했습니다",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalOverlay onClose={onClose}>
      <div
        className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-sm overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Pencil className="h-5 w-5 text-slate-500" />
            <h3 className="text-lg font-bold text-slate-900">
              {position.ticker} 수정
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 mb-6">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              수량
            </label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="0"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
              평균 단가
            </label>
            <input
              type="number"
              value={avgCost}
              onChange={(e) => setAvgCost(e.target.value)}
              placeholder="0.00"
              min="0"
              step="any"
              className={cn(
                "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5",
                "text-sm text-slate-900 tabular-nums placeholder:text-slate-400",
                "transition-all focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/20",
              )}
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              "flex-1 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {submitting ? "저장 중..." : "변경 저장"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            취소
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}

/* ================================================================
   Delete Position Modal
   ================================================================ */

function DeletePositionModal({
  position,
  onClose,
  onSuccess,
}: {
  position: Position;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  const handleDelete = async () => {
    setSubmitting(true);
    try {
      await apiFetch(API.portfolio.deletePosition(position.id), {
        method: "DELETE",
      });
      toast.success(`${position.ticker} 포트폴리오에서 제거됐습니다`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "포지션 삭제에 실패했습니다",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalOverlay onClose={onClose}>
      <div
        className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-sm overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Trash2 className="h-5 w-5 text-red-500" />
            <h3 className="text-lg font-bold text-slate-900">
              {position.ticker} 제거
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-sm text-slate-600 mb-2">
          <span className="font-bold text-slate-900">{position.ticker}</span>{" "}
          ({position.shares}주)를 포트폴리오에서 제거하시겠습니까?
        </p>
        <p className="text-xs text-slate-400 mb-6">
          이 작업은 되돌릴 수 없습니다. 거래 이력은 보존됩니다.
        </p>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleDelete}
            disabled={submitting}
            className={cn(
              "flex-1 rounded-full bg-red-500 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-red-600 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {submitting ? "제거 중..." : "포지션 제거"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            취소
          </button>
        </div>
      </div>
    </ModalOverlay>
  );
}

/* ================================================================
   Position Action Menu
   ================================================================ */

function PositionActions({
  position,
  onBuy,
  onSell,
  onEdit,
  onDelete,
}: {
  position: Position;
  onBuy: () => void;
  onSell: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((prev) => !prev);
        }}
        className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
        aria-label={`Actions for ${position.ticker}`}
      >
        <MoreVertical className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-xl border border-slate-200 bg-white py-1.5 shadow-lg">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onBuy();
            }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <ArrowUpCircle className="h-4 w-4 text-emerald-500" />
            추가 매수
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onSell();
            }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <ArrowDownCircle className="h-4 w-4 text-red-500" />
            매도
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onEdit();
            }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Pencil className="h-4 w-4 text-slate-400" />
            포지션 수정
          </button>
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onDelete();
            }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            제거
          </button>
        </div>
      )}
    </div>
  );
}

/* ================================================================
   Position Card
   ================================================================ */

function PositionCard({
  position,
  onBuy,
  onSell,
  onEdit,
  onDelete,
  onClick,
}: {
  position: Position;
  onBuy: () => void;
  onSell: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onClick: () => void;
}) {
  const priceDisplay = formatPrice(position.current_price, position.currency);
  const costDisplay = formatPrice(position.avg_cost, position.currency);
  const valueDisplay = formatPrice(position.market_value, position.currency);
  const pnlValue = position.market_value - position.shares * position.avg_cost;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick();
      }}
      className="sp-card p-4 w-full text-left transition-all hover:shadow-md active:scale-[0.99] cursor-pointer"
    >
      {/* Top row: ticker, signal, actions */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-base font-semibold text-slate-900">
              {isKoreanTicker(position.ticker, position.is_korean) ? (position.name || position.ticker) : position.ticker}
            </span>
            {position.signal && position.signal !== "\u2014" && (
              <SignalBadge signal={position.signal} />
            )}
            {position.is_korean && (
              <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-600 border border-blue-100">
                KR
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 truncate mt-0.5">
            {isKoreanTicker(position.ticker, position.is_korean) ? `${position.ticker} · KRX` : position.name}
          </p>
        </div>
        <PositionActions
          position={position}
          onBuy={onBuy}
          onSell={onSell}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      </div>

      {/* Price + P&L row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-3">
        <div>
          <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
            현재가
          </p>
          <p className="text-sm font-bold tabular-nums text-slate-900">
            {priceDisplay}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
            평균 단가
          </p>
          <p className="text-sm font-semibold tabular-nums text-slate-700">
            {costDisplay}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
            수량
          </p>
          <p className="text-sm font-semibold tabular-nums text-slate-700">
            {position.shares}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
            평가금액
          </p>
          <p className="text-sm font-bold tabular-nums text-slate-900">
            {valueDisplay}
          </p>
        </div>
      </div>

      {/* P&L bar */}
      <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">P&L</span>
          <span
            className={cn(
              "text-sm font-bold tabular-nums",
              pnlColor(position.pnl_pct),
            )}
          >
            {fmtPct(position.pnl_pct)}
          </span>
        </div>
        <span
          className={cn(
            "text-xs font-semibold tabular-nums",
            pnlColor(pnlValue),
          )}
        >
          {pnlValue >= 0 ? "+" : ""}
          {formatPrice(Math.abs(pnlValue), position.currency)}
          {pnlValue < 0 ? " 손실" : ""}
        </span>
      </div>

      {/* Score bar mini */}
      <div className="mt-3">
        <ScoreBar score={position.score} mini />
      </div>

      {/* TP / SL */}
      {(position.take_profit || position.stop_loss) && (
        <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-400">
          {position.take_profit != null && (
            <span>
              TP: {formatPrice(position.take_profit, position.currency)}{" "}
              <span className="text-emerald-500">
                ({fmtPct(position.tp_pct)})
              </span>
            </span>
          )}
          {position.stop_loss != null && (
            <span>
              SL: {formatPrice(position.stop_loss, position.currency)}{" "}
              <span className="text-red-400">
                ({fmtPct(-Math.abs(position.sl_pct))})
              </span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/* ================================================================
   Portfolio Summary Cards
   ================================================================ */

function PortfolioSummary({ data }: { data: PortfolioResponse }) {
  const fxRate = data.fx_rate ?? 0;
  const hasKrw =
    data.total_value_krw > 0 ||
    data.positions.some((p) => p.currency === "KRW" || p.is_korean);
  const hasUsd =
    data.total_value_usd > 0 ||
    data.positions.some((p) => p.currency !== "KRW" && !p.is_korean);
  const unit: "KRW" | "USD" = hasKrw ? "KRW" : "USD";

  const totalPnl = data.positions.reduce((sum, p) => {
    const cost = p.shares * p.avg_cost;
    const pnlNative = p.market_value - cost;
    const isKrw = p.currency === "KRW" || p.is_korean;
    if (unit === "KRW") {
      return sum + (isKrw ? pnlNative : pnlNative * (fxRate || 0));
    }
    return sum + (isKrw ? 0 : pnlNative);
  }, 0);

  const totalCost = data.positions.reduce((sum, p) => {
    const costNative = p.shares * p.avg_cost;
    const isKrw = p.currency === "KRW" || p.is_korean;
    if (unit === "KRW") {
      return sum + (isKrw ? costNative : costNative * (fxRate || 0));
    }
    return sum + (isKrw ? 0 : costNative);
  }, 0);
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  const mainTotalValue =
    unit === "KRW" ? data.total_value_all_krw : data.total_value_usd;
  const fmtMain = unit === "KRW" ? fmtKrw : fmtUsd;
  const mainCash =
    unit === "KRW" ? data.available_capital_krw : data.available_capital;

  const positiveCount = data.positions.filter(
    (p) => p.signal === "POSITIVE",
  ).length;
  const negativeCount = data.positions.filter(
    (p) => p.signal === "NEGATIVE",
  ).length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {/* Total Value */}
      <div className="sp-card p-4">
        <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1">
          총 평가금액
        </p>
        <p className="text-lg font-bold tabular-nums text-slate-900">
          {fmtMain(mainTotalValue)}
        </p>
        {unit === "KRW" && hasUsd && data.total_value_usd > 0 && (
          <p className="text-xs text-slate-400 tabular-nums">
            {fmtUsd(data.total_value_usd)}
          </p>
        )}
        {unit === "USD" && data.total_value_krw > 0 && (
          <p className="text-xs text-slate-400 tabular-nums">
            {fmtKrw(data.total_value_all_krw)}
          </p>
        )}
      </div>

      {/* Total P&L */}
      <div className="sp-card p-4">
        <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1">
          총 손익
        </p>
        <p
          className={cn(
            "text-lg font-bold tabular-nums",
            pnlColor(totalPnl),
          )}
        >
          {totalPnl >= 0 ? "+" : ""}
          {fmtMain(totalPnl)}
        </p>
        <p
          className={cn(
            "text-xs font-semibold tabular-nums",
            pnlColor(totalPnlPct),
          )}
        >
          {fmtPct(totalPnlPct)}
        </p>
      </div>

      {/* Cash */}
      <div className="sp-card p-4">
        <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1">
          가용 현금
        </p>
        <p className="text-lg font-bold tabular-nums text-slate-900">
          {fmtMain(mainCash)}
        </p>
        {unit === "KRW" && data.available_capital > 0 && (
          <p className="text-xs text-slate-400 tabular-nums">
            {fmtUsd(data.available_capital)}
          </p>
        )}
        {unit === "USD" && data.available_capital_krw > 0 && (
          <p className="text-xs text-slate-400 tabular-nums">
            {fmtKrw(data.available_capital_krw)}
          </p>
        )}
      </div>

      {/* Signals */}
      <div className="sp-card p-4">
        <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1">
          시그널
        </p>
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold text-emerald-600 tabular-nums">
            {positiveCount} 매수
          </span>
          <span className="text-sm font-bold text-red-500 tabular-nums">
            {negativeCount} 매도
          </span>
        </div>
        <p className="text-xs text-slate-400">
          {data.positions.length}개 포지션
        </p>
      </div>
    </div>
  );
}

/* ================================================================
   Sort / Filter types
   ================================================================ */

type SortKey = "ticker" | "pnl" | "value" | "score";
type FilterSignal = "ALL" | "POSITIVE" | "NEGATIVE" | "NEUTRAL";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "ticker", label: "티커" },
  { key: "pnl", label: "손익" },
  { key: "value", label: "평가금액" },
  { key: "score", label: "점수" },
];

const SIGNAL_FILTERS: { key: FilterSignal; label: string }[] = [
  { key: "ALL", label: "전체" },
  { key: "POSITIVE", label: "Positive" },
  { key: "NEGATIVE", label: "Negative" },
  { key: "NEUTRAL", label: "Neutral" },
];

function sortPositions(
  positions: Position[],
  key: SortKey,
  desc: boolean,
): Position[] {
  const sorted = [...positions].sort((a, b) => {
    switch (key) {
      case "ticker":
        return a.ticker.localeCompare(b.ticker);
      case "pnl":
        return a.pnl_pct - b.pnl_pct;
      case "value":
        return a.market_value - b.market_value;
      case "score":
        return a.score - b.score;
      default:
        return 0;
    }
  });
  return desc ? sorted.reverse() : sorted;
}

/* ================================================================
   Portfolio Page
   ================================================================ */

export default function PortfolioPage() {
  const router = useRouter();
  const { data, isLoading, error, mutate } = usePortfolio();

  /* Modal state */
  const [showAddModal, setShowAddModal] = useState(false);
  const [buyTarget, setBuyTarget] = useState<Position | null>(null);
  const [sellTarget, setSellTarget] = useState<Position | null>(null);
  const [editTarget, setEditTarget] = useState<Position | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Position | null>(null);

  /* Sort / Filter */
  const [sortKey, setSortKey] = useState<SortKey>("value");
  const [sortDesc, setSortDesc] = useState(true);
  const [signalFilter, setSignalFilter] = useState<FilterSignal>("ALL");

  const handleMutate = useCallback(async () => {
    await mutate();
  }, [mutate]);

  const handleSortToggle = (key: SortKey) => {
    if (sortKey === key) {
      setSortDesc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  /* Compute displayed positions */
  const positions = data?.positions ?? [];
  const filtered =
    signalFilter === "ALL"
      ? positions
      : positions.filter((p) => p.signal === signalFilter);
  const sorted = sortPositions(filtered, sortKey, sortDesc);

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-5">
        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
              <Briefcase className="h-5 w-5 text-slate-500" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">포트폴리오</h1>
              <p className="text-sm text-slate-500">
                포지션 관리
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowAddModal(true);
            }}
            className="flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
          >
            <Plus className="h-4 w-4" />
            추가
          </button>
        </div>

        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="signal" />

        {/* ── Loading ── */}
        {isLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {error && !isLoading && (
          <div className="sp-card p-6 text-center">
            <p className="text-sm text-red-500 mb-3">
              포트폴리오를 불러오지 못했습니다
            </p>
            <button
              type="button"
              onClick={() => mutate()}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 transition-all active:scale-[0.97]"
            >
              다시 시도
            </button>
          </div>
        )}

        {/* ── Empty state ── */}
        {!isLoading && !error && positions.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-6 text-slate-400">
              <Briefcase className="h-8 w-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">
              포지션 없음
            </h3>
            <p className="text-slate-500 max-w-sm mb-6">
              첫 번째 포지션을 추가하여 포트폴리오 성과를 추적해 보세요.
            </p>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowAddModal(true);
              }}
              className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-slate-800 active:scale-[0.97]"
            >
              <Plus className="h-4 w-4" />
              포지션 추가
            </button>
          </div>
        )}

        {/* ── Data loaded with positions ── */}
        {!isLoading && !error && data && positions.length > 0 && (
          <>
            {/* Summary cards */}
            <PortfolioSummary data={data} />

            {/* Sort + filter bar */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {/* Signal filter pills */}
              <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
                {SIGNAL_FILTERS.map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setSignalFilter(f.key)}
                    className={cn(
                      "filter-pill whitespace-nowrap",
                      signalFilter === f.key && "active",
                    )}
                  >
                    {f.label}
                    {f.key !== "ALL" && (
                      <span className="ml-1 text-[10px] opacity-60">
                        {positions.filter((p) =>
                          f.key === "NEUTRAL"
                            ? p.signal === "NEUTRAL" || p.signal === "\u2014"
                            : p.signal === f.key,
                        ).length}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Sort options */}
              <div className="flex gap-1.5">
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => handleSortToggle(opt.key)}
                    className={cn(
                      "rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition-colors",
                      sortKey === opt.key
                        ? "bg-slate-900 text-white"
                        : "text-slate-500 hover:bg-slate-100",
                    )}
                  >
                    {opt.label}
                    {sortKey === opt.key && (
                      <span className="ml-0.5">
                        {sortDesc ? "\u2193" : "\u2191"}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Position cards */}
            <div className="space-y-3">
              {sorted.length === 0 ? (
                <div className="py-10 text-center">
                  <p className="text-sm text-slate-400">
                    해당하는 포지션이 없습니다
                  </p>
                </div>
              ) : (
                sorted.map((pos) => (
                  <PositionCard
                    key={pos.id}
                    position={pos}
                    onBuy={() => setBuyTarget(pos)}
                    onSell={() => setSellTarget(pos)}
                    onEdit={() => setEditTarget(pos)}
                    onDelete={() => setDeleteTarget(pos)}
                    onClick={() => router.push(`/detail/${pos.ticker}`)}
                  />
                ))
              )}
            </div>

            {/* Position count footer */}
            <p className="text-center text-xs text-slate-400 pt-2">
              {sorted.length} of {positions.length} positions
              {data.fx_rate > 0 && (
                <span className="ml-2">
                  FX: $1 = {fmtKrw(data.fx_rate)}
                </span>
              )}
            </p>
          </>
        )}
      </div>

      {/* ── Modals ── */}
      {showAddModal && (
        <AddPositionModal
          onClose={() => setShowAddModal(false)}
          onSuccess={handleMutate}
        />
      )}
      {buyTarget && (
        <BuyMoreModal
          position={buyTarget}
          onClose={() => setBuyTarget(null)}
          onSuccess={handleMutate}
        />
      )}
      {sellTarget && (
        <SellSharesModal
          position={sellTarget}
          onClose={() => setSellTarget(null)}
          onSuccess={handleMutate}
        />
      )}
      {editTarget && (
        <EditPositionModal
          position={editTarget}
          onClose={() => setEditTarget(null)}
          onSuccess={handleMutate}
        />
      )}
      {deleteTarget && (
        <DeletePositionModal
          position={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onSuccess={handleMutate}
        />
      )}
    </ErrorBoundary>
  );
}
