"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { TierGate } from "@/components/ui/tier-gate";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Zap,
  Play,
  Square,
  Clock,
  CheckCircle2,
  XCircle,
  ListChecks,
  AlertTriangle,
} from "lucide-react";

/* ── Types ── */

interface AutoTradeStatus {
  running: boolean;
  mode: string;
  last_run?: string;
  trades_today?: number;
  pending_count?: number;
}

interface PendingTrade {
  id: string;
  ticker: string;
  action: string;
  shares: number;
  price: number;
  reason: string;
  created_at: string;
}

interface PendingResponse {
  trades: PendingTrade[];
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Pending Trade Card ── */

function PendingTradeCard({
  trade,
  onApprove,
  onReject,
}: {
  trade: PendingTrade;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="sp-card p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900">
              {trade.ticker}
            </span>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                trade.action?.toLowerCase() === "buy"
                  ? "signal-positive"
                  : "signal-negative",
              )}
            >
              {trade.action?.toLowerCase() === "buy" ? "매수" : "매도"}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {trade?.shares ?? 0} shares @ ${trade?.price?.toFixed(2) ?? "\u2014"}
          </p>
        </div>
        <span className="text-[11px] text-slate-400 shrink-0">
          {new Date(trade.created_at).toLocaleTimeString()}
        </span>
      </div>

      <p className="text-xs text-slate-600 mb-3">{trade.reason}</p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onApprove}
          className="flex-1 flex items-center justify-center gap-1.5 rounded-full bg-emerald-500 px-3 py-2.5 text-xs font-semibold text-white transition-all hover:bg-emerald-600 active:scale-[0.97]"
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          승인
        </button>
        <button
          type="button"
          onClick={onReject}
          className="flex-1 flex items-center justify-center gap-1.5 rounded-full border border-slate-200 px-3 py-2.5 text-xs font-semibold text-slate-600 transition-all hover:bg-slate-50 active:scale-[0.97]"
        >
          <XCircle className="h-3.5 w-3.5" />
          거부
        </button>
      </div>
    </div>
  );
}

/* ── Inner Content (behind TierGate) ── */

function AutoTradeContent() {
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);

  const {
    data: status,
    isLoading: statusLoading,
    mutate: mutateStatus,
  } = useSWR<AutoTradeStatus>(API.autotrade.status, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 10_000,
  });

  const {
    data: pendingData,
    isLoading: pendingLoading,
    mutate: mutatePending,
  } = useSWR<PendingResponse>(API.autotrade.pending, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 10_000,
  });

  const pendingTrades = pendingData?.trades ?? [];

  const handleStart = useCallback(async () => {
    setStarting(true);
    try {
      await apiFetch(API.autotrade.start, {
        method: "POST",
        body: JSON.stringify({ mode: "paper" }),
      });
      await mutateStatus();
    } catch {
      // silent
    } finally {
      setStarting(false);
    }
  }, [mutateStatus]);

  const handleStop = useCallback(async () => {
    setStopping(true);
    try {
      await apiFetch(API.autotrade.stop, { method: "POST" });
      await mutateStatus();
    } catch {
      // silent
    } finally {
      setStopping(false);
    }
  }, [mutateStatus]);

  const handleApprove = useCallback(
    async (tradeId: string) => {
      try {
        await apiFetch(API.autotrade.approve(tradeId), { method: "POST" });
        await mutatePending();
      } catch {
        // silent
      }
    },
    [mutatePending],
  );

  const handleReject = useCallback(
    async (tradeId: string) => {
      try {
        await apiFetch(API.autotrade.reject(tradeId), { method: "POST" });
        await mutatePending();
      } catch {
        // silent
      }
    },
    [mutatePending],
  );

  const isRunning = status?.running ?? false;

  return (
    <div className="space-y-5">
      {/* ── Status Card ── */}
      {statusLoading ? (
        <CardSkeleton />
      ) : (
        <div className="sp-card p-5">
          <div className="flex items-center gap-3 mb-4">
            <div
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-xl",
                isRunning ? "bg-emerald-100" : "bg-slate-100",
              )}
            >
              <Zap
                className={cn(
                  "h-5 w-5",
                  isRunning ? "text-emerald-600" : "text-slate-400",
                )}
              />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-slate-900">AutoTrade</p>
                <div
                  className={cn(
                    "status-dot",
                    isRunning ? "active" : "inactive",
                  )}
                />
                <span
                  className={cn(
                    "text-xs font-semibold",
                    isRunning ? "text-emerald-600" : "text-slate-400",
                  )}
                >
                  {isRunning ? "실행 중" : "미실행"}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {status?.mode === "paper"
                  ? "모의투자 모드 (시뮬레이션)"
                  : status?.mode === "live"
                    ? "실전투자 모드"
                    : "자동매매 엔진"}
              </p>
            </div>
          </div>

          {/* Stats row */}
          {status && (
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-[11px] text-slate-500 mb-0.5">
                  오늘 체결
                </p>
                <p className="text-lg font-bold tabular-nums text-slate-900">
                  {status.trades_today ?? 0}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-[11px] text-slate-500 mb-0.5">
                  승인 대기
                </p>
                <p className="text-lg font-bold tabular-nums text-slate-900">
                  {status.pending_count ?? pendingTrades.length}
                </p>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-3">
            {!isRunning ? (
              <button
                type="button"
                onClick={handleStart}
                disabled={starting}
                className={cn(
                  "flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition-all active:scale-[0.97]",
                  "bg-slate-900 text-white hover:bg-slate-800",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                <Play className="h-4 w-4" />
                {starting ? "시작 중..." : "모의투자 시작"}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStop}
                disabled={stopping}
                className={cn(
                  "flex flex-1 items-center justify-center gap-2 rounded-full border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600 transition-all hover:bg-red-50 active:scale-[0.97]",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                <Square className="h-4 w-4" />
                {stopping ? "중지 중..." : "자동매매 중지"}
              </button>
            )}
          </div>

          {status?.last_run && (
            <p className="text-[11px] text-slate-400 mt-3 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              마지막 실행: {new Date(status.last_run).toLocaleString("ko-KR")}
            </p>
          )}
        </div>
      )}

      {/* ── Pending Trades ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <ListChecks className="h-4 w-4 text-slate-400" />
          <h2 className="text-base font-bold text-slate-900">대기 중인 매매</h2>
        </div>

        {pendingLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : pendingTrades.length === 0 ? (
          <EmptyState
            icon={<ListChecks className="h-8 w-8" />}
            title="대기 중인 매매 없음"
            description={
              isRunning
                ? "자동매매 실행 중입니다. 신규 매매 신호가 여기에 표시됩니다."
                : "자동매매를 시작하면 매매 신호를 확인할 수 있습니다."
            }
          />
        ) : (
          <div className="space-y-3">
            {pendingTrades.map((trade) => (
              <PendingTradeCard
                key={trade.id}
                trade={trade}
                onApprove={() => handleApprove(trade.id)}
                onReject={() => handleReject(trade.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Warning ── */}
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-amber-800 mb-1">
              모의투자 먼저 권장
            </p>
            <p className="text-[11px] text-amber-700 leading-relaxed">
              실전투자 전에 반드시 모의투자로 먼저 테스트하세요.
              자동매매는 알고리즘 신호를 사용하며 수익을 보장하지 않습니다.
              결과를 꼼꼼히 모니터링하세요.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Page ── */

export default function AutoTradePage() {
  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-5">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="auto-trade" alwaysExpanded />

        {/* ── Header ── */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-gradient">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">자동매매</h1>
            <p className="text-sm text-slate-500">
              퀀트 신호 기반 자동매매 엔진
            </p>
          </div>
        </div>

        {/* ── TierGate wraps content ── */}
        <TierGate tier="premium">
          <AutoTradeContent />
        </TierGate>
      </div>
    </ErrorBoundary>
  );
}
