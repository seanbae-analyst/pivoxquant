"use client";

/**
 * /ai — AI Analysis Tools in the Vantablack ink theme.
 *
 * Two stations:
 *   1. Portfolio Insights — single Claude-generated coaching note.
 *   2. Stock Analysis — ticker-scoped accordion (SWOT / Competitor /
 *      Sector trend / Commentary), each fetched on first expand.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. A contextual coaching
 * DisclaimerBanner sits above the Stations; the page-level legal footer
 * is provided by (dashboard)/layout.tsx (type="ai-analysis").
 * Editorial palette: Vantablack #050505, bronze hairlines, Source Serif 4
 * headings, JetBrains Mono numbers. No buy/sell/recommend language.
 */

import { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  Sparkles,
  Target,
  Users,
  TrendingUp,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { Eyebrow } from "@/components/landing/eyebrow";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TierGate } from "@/components/ui/tier-gate";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { usePortfolioPositions, useWatchlist } from "@/lib/hooks";
import type {
  AiCoachingResponse,
  AiSwotResponse,
  AiCompetitorResponse,
  AiSectorTrendResponse,
  AiCommentaryResponse,
  Position,
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
    description: "Industry and sector observation",
  },
  commentary: {
    label: "Stock Commentary",
    icon: MessageSquare,
    description: "AI-generated commentary on public data",
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
    <div className="overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors duration-200 hover:bg-[rgba(255,255,255,0.02)]"
        aria-expanded={state.expanded}
      >
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[2px] border border-[rgba(245,240,232,0.1)]"
          style={{ background: "rgba(139,111,71,0.12)" }}
        >
          <Icon className="h-4 w-4 text-[var(--pq-bronze)]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-serif text-[15px] text-[var(--pq-ivory)]">
            {config.label}
          </p>
          <p className="text-[11.5px] text-[rgba(245,240,232,0.55)] truncate">
            {config.description}
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {state.loading && (
            <Loader2 className="h-4 w-4 animate-spin text-[var(--pq-bronze)]" />
          )}
          {state.expanded ? (
            <ChevronUp className="h-4 w-4 text-[rgba(245,240,232,0.5)]" />
          ) : (
            <ChevronDown className="h-4 w-4 text-[rgba(245,240,232,0.5)]" />
          )}
        </div>
      </button>

      {state.expanded && (
        <div className="border-t border-[rgba(245,240,232,0.08)] px-5 py-5">
          {state.loading && !content && (
            <div className="flex items-center justify-center gap-2 py-8">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--pq-bronze)]" />
              <span className="text-[12px] text-[rgba(245,240,232,0.55)] uppercase tracking-[0.18em]">
                Analyzing with AI…
              </span>
            </div>
          )}
          {state.error && (
            <div className="rounded-[2px] border border-red-500/30 bg-red-500/5 px-4 py-3">
              <p className="text-[12.5px] text-red-400">{state.error}</p>
            </div>
          )}
          {content && (
            <div className="space-y-3">
              <div className="whitespace-pre-wrap font-serif text-[14px] leading-relaxed text-[var(--pq-ivory)]">
                {content}
              </div>
              {contentKr && (
                <details className="group">
                  <summary className="cursor-pointer text-[10.5px] font-medium uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)] transition-colors">
                    Korean translation
                  </summary>
                  <div className="mt-3 whitespace-pre-wrap font-serif text-[13px] leading-relaxed text-[rgba(245,240,232,0.6)]">
                    {contentKr}
                  </div>
                </details>
              )}
            </div>
          )}
          {!state.loading && !state.error && !content && (
            <p className="text-center text-[12px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.4)] py-4">
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
  const [activeTicker, setActiveTicker] = useState("");

  /* Whitelist: user's holdings + watchlist (§101 회피 — 임의 ticker 금지) */
  const positionsSwr = usePortfolioPositions<{ positions?: Position[] }>();
  const watchlistSwr = useWatchlist();
  const userTickers = useMemo(() => {
    const set = new Map<string, string>();
    (positionsSwr.data?.positions ?? []).forEach((p) => {
      if (p.ticker) set.set(p.ticker.toUpperCase(), p.name || p.ticker);
    });
    (watchlistSwr.data?.watchlist ?? []).forEach((w) => {
      if (w.ticker) {
        const key = w.ticker.toUpperCase();
        if (!set.has(key)) set.set(key, w.name || w.ticker);
      }
    });
    return Array.from(set.entries()).map(([ticker, name]) => ({ ticker, name }));
  }, [positionsSwr.data, watchlistSwr.data]);
  const hasUserTickers = userTickers.length > 0;
  const tickersLoading = positionsSwr.isLoading || watchlistSwr.isLoading;

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

  /* Handle ticker selection from dropdown */
  const handleTickerSelect = useCallback(
    (value: string) => {
      const t = value.trim().toUpperCase();
      if (!t) {
        setActiveTicker("");
        return;
      }
      // Whitelist guard — only holdings or watchlist tickers allowed.
      const allowed = userTickers.some((u) => u.ticker === t);
      if (!allowed) return;
      setActiveTicker(t);
      // Reset all sections
      setSections({
        swot: { ...INITIAL_SECTION },
        competitor: { ...INITIAL_SECTION },
        sectorTrend: { ...INITIAL_SECTION },
        commentary: { ...INITIAL_SECTION },
      });
    },
    [userTickers],
  );

  return (
    <ErrorBoundary>
      <TierGate tier="pro">
        <div className="space-y-8">
          {/* ── Header ── */}
          <header>
            <RuledKicker>AI Assistant &middot; Observational analysis</RuledKicker>
            <h1 className="mt-2 font-serif text-2xl md:text-3xl text-[var(--pq-ivory)]">
              AI Analysis Tools
            </h1>
            <p className="mt-2 font-serif text-[15px] text-[var(--pq-ivory)] max-w-2xl">
              Claude-driven research notes, drawn over 58 quant signals.
            </p>
            <Caption className="mt-1 max-w-2xl">
              Generative summaries, not advice. Every line here is informational only.
            </Caption>
          </header>

          <DisclaimerBanner type="coaching" />

          {/* ── Portfolio Insights ── */}
          <section className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
            <div className="flex items-start gap-4">
              <div
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[2px] border border-[rgba(245,240,232,0.1)]"
                style={{ background: "rgba(139,111,71,0.14)" }}
              >
                <Sparkles className="h-5 w-5 text-[var(--pq-bronze)]" />
              </div>
              <div className="flex-1 min-w-0">
                <Eyebrow withDashLeft={false} className="flex">
                  Station I &middot; Portfolio
                </Eyebrow>
                <h2 className="mt-1 font-serif text-xl text-[var(--pq-ivory)]">
                  Portfolio Insights
                </h2>
                <Caption className="mt-1">
                  An AI-drafted note on the shape of your book — generated on demand.
                </Caption>

                {coaching.loading && (
                  <div className="mt-4 flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-[var(--pq-bronze)]" />
                    <span className="text-[11.5px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.55)]">
                      Generating insight…
                    </span>
                  </div>
                )}

                {coaching.error && (
                  <div className="mt-4 rounded-[2px] border border-red-500/30 bg-red-500/5 px-4 py-3">
                    <p className="text-[12.5px] text-red-400">{coaching.error}</p>
                  </div>
                )}

                {coaching.data && (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-[2px] border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.015)] p-4">
                      <p className="whitespace-pre-wrap font-serif text-[14px] leading-relaxed text-[var(--pq-ivory)]">
                        {coaching.data.insight}
                      </p>
                    </div>
                    {coaching.data.insight_kr && (
                      <details className="group">
                        <summary className="cursor-pointer text-[10.5px] font-medium uppercase tracking-[0.22em] text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)] transition-colors">
                          Korean translation
                        </summary>
                        <div className="mt-3 rounded-[2px] border border-[rgba(245,240,232,0.06)] bg-[rgba(255,255,255,0.015)] p-4">
                          <p className="whitespace-pre-wrap font-serif text-[13px] leading-relaxed text-[rgba(245,240,232,0.6)]">
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
                    className="pq-ink-btn-bronze mt-4 inline-flex items-center gap-1.5"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Get Insight
                  </button>
                )}

                {coaching.data && !coaching.loading && (
                  <button
                    type="button"
                    onClick={fetchCoaching}
                    className="mt-3 text-[10.5px] uppercase tracking-[0.22em] font-medium text-[var(--pq-bronze)] hover:text-[var(--pq-ivory)] transition-colors"
                  >
                    Refresh insight
                  </button>
                )}
              </div>
            </div>
          </section>

          {/* ── Stock Analysis ── */}
          <section className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px]">
            <div className="p-5">
              <Eyebrow withDashLeft={false} className="flex">
                Station II &middot; Symbol
              </Eyebrow>
              <h2 className="mt-1 font-serif text-xl text-[var(--pq-ivory)]">
                Stock Analysis
              </h2>
              <Caption className="mt-1 mb-4">
                Select one of your holdings or watchlist symbols to draw SWOT,
                competitor, sector and commentary notes.
              </Caption>

              {tickersLoading ? (
                <div className="flex items-center gap-2 text-[12px] text-[rgba(245,240,232,0.5)]">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--pq-bronze)]" />
                  Loading your symbols…
                </div>
              ) : hasUserTickers ? (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <label className="sr-only" htmlFor="ai-ticker-select">
                    Choose a symbol
                  </label>
                  <div className="relative flex-1 max-w-xs">
                    <select
                      id="ai-ticker-select"
                      value={activeTicker}
                      onChange={(e) => handleTickerSelect(e.target.value)}
                      className={cn(
                        "w-full appearance-none rounded-[2px] border border-[rgba(245,240,232,0.12)] bg-[rgba(255,255,255,0.02)] px-3 pr-9 py-2.5 text-[13px] font-mono tracking-wide text-[var(--pq-ivory)]",
                        "outline-none transition-all duration-200",
                        "focus:border-[var(--pq-bronze)] focus:bg-[rgba(255,255,255,0.04)]",
                      )}
                    >
                      <option value="">내 보유 종목에서 선택</option>
                      {userTickers.map((u) => (
                        <option key={u.ticker} value={u.ticker}>
                          {u.ticker} — {u.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[rgba(245,240,232,0.5)]" />
                  </div>
                  <span className="text-[10.5px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.65)]">
                    {userTickers.length} symbol{userTickers.length === 1 ? "" : "s"} eligible
                  </span>
                </div>
              ) : (
                <div className="rounded-[2px] border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.015)] px-4 py-5">
                  <p className="font-serif text-[14px] text-[var(--pq-ivory)]">
                    보유 종목이나 관심종목을 먼저 추가하세요.
                  </p>
                  <Caption className="mt-1.5">
                    AI 분석은 사용자의 보유/관심 종목에 한해 제공됩니다.
                  </Caption>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link href="/portfolio" className="pq-ink-btn-bronze inline-flex items-center gap-1.5">
                      포지션 추가
                    </Link>
                    <Link href="/watchlist" className="pq-ink-btn-ghost inline-flex items-center gap-1.5">
                      관심종목 추가
                    </Link>
                  </div>
                </div>
              )}

              {activeTicker && (
                <p className="mt-3 text-[10.5px] uppercase tracking-[0.22em] font-medium text-[var(--pq-bronze)]">
                  Showing analysis for{" "}
                  <span className="font-mono tabular-nums">{activeTicker}</span>
                </p>
              )}
            </div>

            {/* Analysis sections */}
            {activeTicker && (
              <div className="border-t border-[rgba(245,240,232,0.08)]">
                {(
                  Object.keys(SECTION_CONFIG) as AnalysisSection[]
                ).map((section) => (
                  <div
                    key={section}
                    className={cn(
                      section !== "swot" && "border-t border-[rgba(245,240,232,0.06)]",
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

            {!activeTicker && hasUserTickers && (
              <div className="border-t border-[rgba(245,240,232,0.08)] pq-ink-empty text-center py-12">
                <Fleuron size={14} />
                <div className="font-serif text-[15px] text-[var(--pq-ivory)] mt-3">
                  No symbol selected.
                </div>
                <Caption className="mt-2">
                  Choose one of your symbols above to begin observing.
                </Caption>
              </div>
            )}
          </section>

          {/* Editorial signature — legal disclaimer mounted by (dashboard)/layout.tsx
              as a path-aware footer (type="ai-analysis"). The contextual
              type="coaching" banner above the Stations is intentional and
              specific to the coaching surface. */}
          <FootSignature note="PivoxQuant &middot; AI Assistant &middot; Observational research only &middot; Not investment advice" />
        </div>
      </TierGate>
    </ErrorBoundary>
  );
}
