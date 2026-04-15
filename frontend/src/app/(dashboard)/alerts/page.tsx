"use client";

import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAlerts } from "@/lib/hooks";
import type { AlertItem } from "@/lib/types";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  BellOff,
  CheckCheck,
  Trash2,
  TrendingUp,
  TrendingDown,
  Shield,
  AlertTriangle,
  Zap,
  Info,
} from "lucide-react";

/* ── Time helpers ── */

function relativeTime(dateStr: string): string {
  if (!dateStr) return "";
  const now = Date.now();
  const d = new Date(dateStr).getTime();
  if (Number.isNaN(d)) return "";
  const diff = now - d;

  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "방금 전";
  if (mins < 60) return `${mins}분 전`;

  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;

  const days = Math.floor(hours / 24);
  if (days === 1) return "1일 전";
  if (days < 7) return `${days}일 전`;

  const weeks = Math.floor(days / 7);
  if (weeks === 1) return "1주 전";
  return `${weeks}주 전`;
}

function dateGroup(dateStr: string): string {
  if (!dateStr) return "이전";
  const now = new Date();
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "이전";

  // Reset to midnight for comparison
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const alertDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.floor(
    (today.getTime() - alertDay.getTime()) / 86_400_000,
  );

  if (diffDays === 0) return "오늘";
  if (diffDays === 1) return "어제";
  if (diffDays < 7) return "이번 주";
  return "이전";
}

/* ── Alert icon by type ── */

function AlertIcon({ type }: { type: string }) {
  switch (type) {
    case "signal_change":
    case "signal_positive":
      return <TrendingUp className="h-4 w-4 text-emerald-600" />;
    case "signal_negative":
      return <TrendingDown className="h-4 w-4 text-red-500" />;
    case "risk":
    case "risk_defense":
      return <Shield className="h-4 w-4 text-amber-500" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-amber-500" />;
    case "trade":
    case "auto_trade":
      return <Zap className="h-4 w-4 text-purple-500" />;
    default:
      return <Info className="h-4 w-4 text-blue-500" />;
  }
}

/* ── Alert Row ── */

function AlertRow({
  alert,
  onClick,
}: {
  alert: AlertItem;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors",
        "hover:bg-slate-50 active:bg-slate-100",
        !alert.is_read && "bg-violet-50/60",
      )}
    >
      {/* Icon */}
      <div className="mt-0.5 shrink-0">
        <AlertIcon type={alert.type} />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "text-sm leading-snug",
            alert.is_read
              ? "text-slate-600"
              : "font-semibold text-slate-900",
          )}
        >
          {alert.message}
        </p>
        <div className="flex items-center gap-2 mt-1">
          {alert.ticker && (
            <span className="text-xs font-semibold text-purple-600">
              {alert.ticker}
            </span>
          )}
          <span className="text-[11px] text-slate-400 tabular-nums">
            {relativeTime(alert.created_at)}
          </span>
        </div>
      </div>

      {/* Unread indicator */}
      {!alert.is_read && (
        <div className="mt-2 h-2 w-2 shrink-0 rounded-full bg-purple-500" />
      )}
    </button>
  );
}

/* ── Page ── */

export default function AlertsPage() {
  const router = useRouter();
  const { data, isLoading, mutate } = useAlerts();
  const [markingRead, setMarkingRead] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const alerts = useMemo(() => data?.alerts ?? [], [data?.alerts]);
  const unreadCount = alerts.filter((a) => !a.is_read).length;

  /* ── Group alerts by date ── */
  const grouped = useMemo(() => {
    const groups: Record<string, AlertItem[]> = {};
    const order = ["오늘", "어제", "이번 주", "이전"];

    for (const alert of alerts) {
      const group = dateGroup(alert.created_at);
      if (!groups[group]) groups[group] = [];
      groups[group].push(alert);
    }

    // Return in order
    return order
      .filter((g) => groups[g]?.length)
      .map((group) => ({
        label: group,
        items: groups[group],
      }));
  }, [alerts]);

  /* ── Mark all read ── */
  const handleMarkAllRead = useCallback(async () => {
    setMarkingRead(true);
    try {
      await apiFetch(API.alerts.read, { method: "POST" });
      await mutate();
      toast.success("모든 알림을 읽음으로 표시했습니다");
    } catch {
      toast.error("알림 읽음 처리에 실패했습니다");
    } finally {
      setMarkingRead(false);
    }
  }, [mutate]);

  /* ── Clear all ── */
  const handleClearAll = useCallback(async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }

    setClearing(true);
    try {
      await apiFetch(API.alerts.clear, { method: "POST" });
      await mutate();
      toast.success("모든 알림이 삭제됐습니다");
    } catch {
      toast.error("알림 삭제에 실패했습니다");
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }, [confirmClear, mutate]);

  /* ── Handle click ── */
  const handleAlertClick = useCallback(
    (alert: AlertItem) => {
      if (alert.ticker) {
        router.push(`/detail/${alert.ticker}`);
      }
    },
    [router],
  );

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-3xl space-y-5">
        {/* ── Disclaimer ── */}
        <DisclaimerBanner type="signal" />

        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900">
              알림
            </h1>
            {unreadCount > 0 && (
              <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-semibold text-purple-700 tabular-nums">
                {unreadCount}
              </span>
            )}
          </div>
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              disabled={markingRead}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all",
                "bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.97]",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              <CheckCheck className="h-3.5 w-3.5" />
              모두 읽음 처리
            </button>
          )}
        </div>

        {/* ── Loading ── */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : alerts.length === 0 ? (
          /* ── Empty state ── */
          <EmptyState
            icon={<BellOff className="h-8 w-8" />}
            title="알림 없음"
            description="시그널이 변경되거나 리스크 이벤트가 발생하면 알림이 표시됩니다."
          />
        ) : (
          /* ── Grouped alerts ── */
          <div className="space-y-4">
            {grouped.map((group) => (
              <div key={group.label}>
                {/* Group label */}
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
                  {group.label}
                </h3>

                {/* Alert cards */}
                <div className="sp-card overflow-hidden divide-y divide-slate-100">
                  {group.items.map((alert) => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      onClick={() => handleAlertClick(alert)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Clear all button ── */}
        {alerts.length > 0 && (
          <div className="flex justify-center pt-2 pb-4">
            <button
              type="button"
              onClick={handleClearAll}
              disabled={clearing}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-5 py-2.5 text-xs font-semibold transition-all",
                confirmClear
                  ? "bg-red-500 text-white hover:bg-red-600"
                  : "border border-slate-200 text-slate-500 hover:text-red-500 hover:border-red-200 hover:bg-red-50",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "active:scale-[0.97]",
              )}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {confirmClear
                ? "정말 전체 삭제"
                : "전체 삭제"}
            </button>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
