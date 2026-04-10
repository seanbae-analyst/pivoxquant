"use client";

import { useEffect } from "react";
import { useAiCoaching, useAiStatus } from "@/lib/hooks";

/**
 * AI Coaching Widget — displays a one-line AI-generated portfolio insight.
 * Designed for the Terminal right panel / dashboard sidebar.
 * Calls POST /api/ai/coaching on first load and on manual refresh.
 */
export function AiCoachingWidget() {
  const { data: aiStatus } = useAiStatus();
  const { data, error, isLoading, refresh } = useAiCoaching();

  // Auto-fetch coaching on mount if AI is available
  useEffect(() => {
    if (aiStatus?.available && !data && !isLoading) {
      refresh();
    }
  }, [aiStatus?.available, data, isLoading, refresh]);

  // AI not configured
  if (aiStatus && !aiStatus.available) {
    return (
      <div className="px-3 py-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-5 h-5 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 20 20" fill="none" className="text-amber-500">
              <path d="M10 2L2 18h16L10 2z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              <path d="M10 8v4M10 14v1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-amber-600">
            AI Offline
          </span>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed">
          AI coaching requires an API key. Configure it in settings to get personalized portfolio insights.
        </p>
      </div>
    );
  }

  return (
    <div className="px-3 py-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-lg bg-violet-50 border border-violet-200 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 20 20" fill="none" className="text-violet-500">
              <path d="M10 2l2.5 5 5.5.8-4 3.9.9 5.3L10 14.5l-4.9 2.5.9-5.3-4-3.9 5.5-.8z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-violet-600">
            AI Coaching
          </span>
        </div>
        <button
          onClick={refresh}
          disabled={isLoading}
          className="text-[9px] font-semibold text-slate-400 hover:text-violet-600 spring-transition transition-colors duration-300 disabled:opacity-40"
          title="Refresh insight"
        >
          {isLoading ? (
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 animate-spin rounded-full border border-violet-400 border-t-transparent inline-block" />
            </span>
          ) : (
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="spring-transition transition-transform duration-300 hover:rotate-180">
              <path d="M17.5 10a7.5 7.5 0 11-2.2-5.3M17.5 2.5v5h-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>
      </div>

      {/* Content */}
      {isLoading && !data ? (
        <div className="space-y-2">
          <div className="h-3 w-full bg-slate-100 rounded animate-pulse" />
          <div className="h-3 w-4/5 bg-slate-100 rounded animate-pulse" />
          <div className="h-3 w-3/5 bg-slate-100 rounded animate-pulse" />
        </div>
      ) : error ? (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3">
          <p className="text-[11px] text-red-600 leading-relaxed">
            Failed to load coaching insight. Please try again.
          </p>
          <button
            onClick={refresh}
            className="mt-2 text-[10px] font-semibold text-red-500 hover:text-red-700 underline"
          >
            Retry
          </button>
        </div>
      ) : data ? (
        <div className="space-y-3">
          <p className="text-[12px] text-slate-700 leading-relaxed">
            {data.insight}
          </p>
          {data.insight_kr && data.insight_kr !== data.insight && (
            <p className="text-[11px] text-slate-400 leading-relaxed border-t border-slate-100 pt-2">
              {data.insight_kr}
            </p>
          )}
          <p className="text-[9px] text-slate-300 italic">
            AI analysis, not financial advice
          </p>
        </div>
      ) : null}
    </div>
  );
}
