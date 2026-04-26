"use client";

/**
 * /ai — AI Analysis Tools in the Vantablack ink theme.
 *
 * Two stations:
 *   1. Portfolio Insights — single Claude-generated coaching note.
 *   2. Stock Analysis — ticker-scoped accordion (SWOT / Competitor /
 *      Sector trend / Commentary), each fetched on first expand.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner top + bottom.
 * Editorial palette: Vantablack #050505, bronze hairlines, Source Serif 4
 * headings, JetBrains Mono numbers. No buy/sell/recommend language.
 */

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
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
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
                <div className="text-[10.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
                  Station I &middot; Portfolio
                </div>
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
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
                Station II &middot; Symbol
              </div>
              <h2 className="mt-1 font-serif text-xl text-[var(--pq-ivory)]">
                Stock Analysis
              </h2>
              <Caption className="mt-1 mb-4">
                Enter a ticker to draw SWOT, competitor, sector and commentary notes.
              </Caption>

              <form
                onSubmit={handleTickerSubmit}
                className="flex gap-2"
              >
                <div className="relative flex-1 max-w-xs">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[rgba(245,240,232,0.4)]" />
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    className={cn(
                      "w-full rounded-[2px] border border-[rgba(245,240,232,0.12)] bg-[rgba(255,255,255,0.02)] pl-9 pr-4 py-2.5 text-[13px] font-mono tracking-wide text-[var(--pq-ivory)]",
                      "placeholder:text-[rgba(245,240,232,0.3)] outline-none transition-all duration-200",
                      "focus:border-[var(--pq-bronze)] focus:bg-[rgba(255,255,255,0.04)]",
                    )}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!ticker.trim()}
                  className={cn(
                    ticker.trim() ? "pq-ink-btn-bronze" : "pq-ink-btn-ghost",
                    !ticker.trim() && "opacity-40 cursor-not-allowed",
                  )}
                >
                  Analyze
                </button>
              </form>

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

            {!activeTicker && (
              <div className="border-t border-[rgba(245,240,232,0.08)] pq-ink-empty text-center py-12">
                <Fleuron size={14} />
                <div className="font-serif text-[15px] text-[var(--pq-ivory)] mt-3">
                  No symbol selected.
                </div>
                <Caption className="mt-2">
                  Enter a ticker above to begin observing.
                </Caption>
              </div>
            )}
          </section>

          {/* ── Disclaimer + Editorial signature ── */}
          <DisclaimerBanner type="ai-analysis" />
          <FootSignature note="PivoxQuant &middot; AI Assistant &middot; Observational research only &middot; Not investment advice" />
        </div>
      </TierGate>
    </ErrorBoundary>
  );
}
