"use client";

import { useState, useCallback, type FormEvent } from "react";
import {
  Sparkles,
  Target,
  Users,
  TrendingUp,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Loader2,
  Search,
} from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TierGate } from "@/components/ui/tier-gate";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  AiCoachingResponse,
  AiSwotResponse,
  AiCompetitorResponse,
  AiSectorTrendResponse,
  AiCommentaryResponse,
} from "@/lib/types";

/* ── Types ── */

type AnalysisSection = "swot" | "competitor" | "sectorTrend" | "commentary";

interface SectionState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  expanded: boolean;
}

type SectionsState = {
  swot: SectionState<AiSwotResponse>;
  competitor: SectionState<AiCompetitorResponse>;
  sectorTrend: SectionState<AiSectorTrendResponse>;
  commentary: SectionState<AiCommentaryResponse>;
};

const INITIAL_SECTION: SectionState<never> = {
  data: null,
  loading: false,
  error: null,
  expanded: false,
};

/* ── Section configs ── */

const SECTION_CONFIG: Record<
  AnalysisSection,
  { label: string; icon: typeof Target; description: string }
> = {
  swot: {
    label: "SWOT Analysis",
    icon: Target,
    description: "Strengths, Weaknesses, Opportunities, Threats",
  },
  competitor: {
    label: "Competitor Analysis",
    icon: Users,
    description: "Compare against top competitors",
  },
  sectorTrend: {
    label: "Sector Trend",
    icon: TrendingUp,
    description: "Industry and sector outlook",
  },
  commentary: {
    label: "Stock Commentary",
    icon: MessageSquare,
    description: "AI-generated stock opinion",
  },
};

/* ── Analysis Section Card ── */

function AnalysisSectionCard({
  section,
  state,
  onToggle,
}: {
  section: AnalysisSection;
  state: SectionState<
    AiSwotResponse | AiCompetitorResponse | AiSectorTrendResponse | AiCommentaryResponse
  >;
  onToggle: () => void;
}) {
  const config = SECTION_CONFIG[section];
  const Icon = config.icon;

  function getContent(): string | null {
    if (!state.data) return null;
    if ("swot" in state.data) return state.data.swot;
    if ("analysis" in state.data) return state.data.analysis;
    if ("trend" in state.data) return state.data.trend;
    if ("commentary" in state.data) return state.data.commentary;
    return null;
  }

  function getContentKr(): string | null {
    if (!state.data) return null;
    if ("swot_kr" in state.data) return state.data.swot_kr;
    if ("analysis_kr" in state.data) return state.data.analysis_kr;
    if ("trend_kr" in state.data) return state.data.trend_kr;
    if ("commentary_kr" in state.data) return state.data.commentary_kr;
    return null;
  }

  const content = getContent();
  const contentKr = getContentKr();

  return (
    <div className="sp-card overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-200 hover:bg-slate-50"
        aria-expanded={state.expanded}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--sp-accent-light)]">
          <Icon className="h-4 w-4 text-[var(--sp-accent)]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900">{config.label}</p>
          <p className="text-xs text-slate-500 truncate">{config.description}</p>
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {state.loading && (
            <Loader2 className="h-4 w-4 animate-spin text-[var(--sp-accent)]" />
          )}
          {state.expanded ? (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          )}
        </div>
      </button>

      {state.expanded && (
        <div className="border-t border-slate-100 px-4 py-4">
          {state.loading && !content && (
            <div className="flex items-center justify-center gap-2 py-8">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--sp-accent)]" />
              <span className="text-sm text-slate-500">
                Analyzing with AI...
              </span>
            </div>
          )}
          {state.error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3">
              <p className="text-sm text-red-600">{state.error}</p>
            </div>
          )}
          {content && (
            <div className="space-y-3">
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {content}
              </div>
              {contentKr && (
                <details className="group">
                  <summary className="cursor-pointer text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors">
                    Korean translation
                  </summary>
                  <div className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-slate-500">
                    {contentKr}
                  </div>
                </details>
              )}
            </div>
          )}
          {!state.loading && !state.error && !content && (
            <p className="text-center text-sm text-slate-400 py-4">
              Click to load analysis
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main Page ── */

export default function AiPage() {
  const [ticker, setTicker] = useState("");
  const [activeTicker, setActiveTicker] = useState("");

  /* Coaching state */
  const [coaching, setCoaching] = useState<{
    data: AiCoachingResponse | null;
    loading: boolean;
    error: string | null;
  }>({ data: null, loading: false, error: null });

  /* Analysis sections */
  const [sections, setSections] = useState<SectionsState>({
    swot: { ...INITIAL_SECTION },
    competitor: { ...INITIAL_SECTION },
    sectorTrend: { ...INITIAL_SECTION },
    commentary: { ...INITIAL_SECTION },
  });

  /* Fetch coaching insight */
  const fetchCoaching = useCallback(async () => {
    setCoaching({ data: null, loading: true, error: null });
    try {
      const result = await apiFetch<AiCoachingResponse>(API.ai.coaching, {
        method: "POST",
      });
      setCoaching({ data: result, loading: false, error: null });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load";
      setCoaching({ data: null, loading: false, error: message });
    }
  }, []);

  /* Fetch a specific analysis section */
  const fetchSection = useCallback(
    async (section: AnalysisSection, tickerValue: string) => {
      setSections((prev) => ({
        ...prev,
        [section]: { ...prev[section], loading: true, error: null },
      }));

      try {
        let result: AiSwotResponse | AiCompetitorResponse | AiSectorTrendResponse | AiCommentaryResponse;
        const body = JSON.stringify({ ticker: tickerValue });

        switch (section) {
          case "swot":
            result = await apiFetch<AiSwotResponse>(API.ai.swot, {
              method: "POST",
              body,
            });
            break;
          case "competitor":
            result = await apiFetch<AiCompetitorResponse>(API.ai.competitor, {
              method: "POST",
              body,
            });
            break;
          case "sectorTrend":
            result = await apiFetch<AiSectorTrendResponse>(API.ai.sectorTrend, {
              method: "POST",
              body,
            });
            break;
          case "commentary":
            result = await apiFetch<AiCommentaryResponse>(API.ai.commentary, {
              method: "POST",
              body,
            });
            break;
        }

        setSections((prev) => ({
          ...prev,
          [section]: { data: result, loading: false, error: null, expanded: true },
        }));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to load";
        setSections((prev) => ({
          ...prev,
          [section]: { ...prev[section], loading: false, error: message },
        }));
      }
    },
    [],
  );

  /* Toggle section — fetch on first expand */
  const toggleSection = useCallback(
    (section: AnalysisSection) => {
      setSections((prev) => {
        const current = prev[section];
        const willExpand = !current.expanded;

        // If expanding and no data yet, trigger fetch
        if (willExpand && !current.data && !current.loading && activeTicker) {
          fetchSection(section, activeTicker);
        }

        return {
          ...prev,
          [section]: { ...current, expanded: willExpand },
        };
      });
    },
    [activeTicker, fetchSection],
  );

  /* Handle ticker submit */
  const handleTickerSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const t = ticker.trim().toUpperCase();
      if (!t) return;
      setActiveTicker(t);
      // Reset all sections
      setSections({
        swot: { ...INITIAL_SECTION },
        competitor: { ...INITIAL_SECTION },
        sectorTrend: { ...INITIAL_SECTION },
        commentary: { ...INITIAL_SECTION },
      });
    },
    [ticker],
  );

  return (
    <ErrorBoundary>
      <TierGate tier="pro">
        <DisclaimerBanner type="coaching" />
        <div className="space-y-6 pb-8">
          {/* Page header */}
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              AI Analysis Tools
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Powered by Claude AI with 58 quant models
            </p>
          </div>

          {/* Quick Insight — Coaching */}
          <div className="sp-card overflow-hidden">
            <div className="flex items-start gap-4 p-5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[var(--sp-accent-light)]">
                <Sparkles className="h-5 w-5 text-[var(--sp-accent)]" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-bold text-slate-900">
                  Portfolio Insights
                </h2>
                <p className="mt-0.5 text-sm text-slate-500">
                  Get an AI-generated insight about your portfolio right now.
                </p>

                {coaching.loading && (
                  <div className="mt-4 flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-[var(--sp-accent)]" />
                    <span className="text-sm text-slate-500">
                      Generating insight...
                    </span>
                  </div>
                )}

                {coaching.error && (
                  <div className="mt-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3">
                    <p className="text-sm text-red-600">{coaching.error}</p>
                  </div>
                )}

                {coaching.data && (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                        {coaching.data.insight}
                      </p>
                    </div>
                    {coaching.data.insight_kr && (
                      <details className="group">
                        <summary className="cursor-pointer text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors">
                          Korean translation
                        </summary>
                        <div className="mt-2 rounded-xl border border-slate-100 bg-slate-50 p-4">
                          <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-500">
                            {coaching.data.insight_kr}
                          </p>
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {!coaching.loading && !coaching.data && (
                  <button
                    type="button"
                    onClick={fetchCoaching}
                    className={cn(
                      "mt-4 inline-flex items-center gap-2 rounded-full px-5 py-2.5",
                      "bg-[var(--sp-accent)] text-white text-sm font-semibold",
                      "transition-all duration-200 hover:bg-[var(--sp-accent-hover)] hover:scale-[1.02] active:scale-[0.97]",
                    )}
                    style={{
                      transitionTimingFunction:
                        "cubic-bezier(0.16, 1, 0.3, 1)",
                    }}
                  >
                    <Sparkles className="h-4 w-4" />
                    Get Insight
                  </button>
                )}

                {coaching.data && !coaching.loading && (
                  <button
                    type="button"
                    onClick={fetchCoaching}
                    className="mt-3 text-xs font-medium text-[var(--sp-accent)] hover:underline"
                  >
                    Refresh insight
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Stock Analysis section */}
          <div className="sp-card overflow-hidden">
            <div className="p-5">
              <h2 className="text-base font-bold text-slate-900 mb-1">
                Stock Analysis
              </h2>
              <p className="text-sm text-slate-500 mb-4">
                Enter a ticker symbol to run AI-powered analysis tools.
              </p>

              <form
                onSubmit={handleTickerSubmit}
                className="flex gap-2"
              >
                <div className="relative flex-1 max-w-xs">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    className={cn(
                      "w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-4 py-2.5 text-sm text-slate-900",
                      "placeholder:text-slate-400 outline-none transition-all duration-200",
                      "focus:border-[var(--sp-accent)] focus:ring-2 focus:ring-[var(--sp-accent)]/20 focus:bg-white",
                    )}
                    style={{
                      transitionTimingFunction:
                        "cubic-bezier(0.16, 1, 0.3, 1)",
                    }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!ticker.trim()}
                  className={cn(
                    "rounded-xl px-5 py-2.5 text-sm font-semibold transition-all duration-200 active:scale-[0.97]",
                    ticker.trim()
                      ? "bg-slate-900 text-white hover:bg-slate-800"
                      : "bg-slate-100 text-slate-400 cursor-not-allowed",
                  )}
                  style={{
                    transitionTimingFunction:
                      "cubic-bezier(0.16, 1, 0.3, 1)",
                  }}
                >
                  Analyze
                </button>
              </form>

              {activeTicker && (
                <p className="mt-3 text-xs font-medium text-[var(--sp-accent)]">
                  Showing analysis for {activeTicker}
                </p>
              )}
            </div>

            {/* Analysis sections */}
            {activeTicker && (
              <div className="border-t border-slate-100">
                {(
                  Object.keys(SECTION_CONFIG) as AnalysisSection[]
                ).map((section) => (
                  <div
                    key={section}
                    className={cn(
                      section !== "swot" && "border-t border-slate-100",
                    )}
                  >
                    <AnalysisSectionCard
                      section={section}
                      state={sections[section]}
                      onToggle={() => toggleSection(section)}
                    />
                  </div>
                ))}
              </div>
            )}

            {!activeTicker && (
              <div className="border-t border-slate-100 px-5 py-8 text-center">
                <Search className="mx-auto h-8 w-8 text-slate-300 mb-3" />
                <p className="text-sm text-slate-400">
                  Enter a ticker symbol above to get started
                </p>
              </div>
            )}
          </div>

          {/* Disclaimer */}
          <DisclaimerBanner type="ai-analysis" />
        </div>
      </TierGate>
    </ErrorBoundary>
  );
}
