"use client";

/**
 * /growth — Solo Founder Growth OS dashboard.
 *
 * Sections:
 * 1. Streak counter + today's score summary
 * 2. Morning briefing (today's priorities)
 * 3. Reflection form (evening questions)
 * 4. Growth Graph (365-day heatmap)
 * 5. Weekly trend chart
 * 6. Weekly reports archive
 */

import { useState, useCallback } from "react";
import { useGrowthData, useGrowthToday, useGrowthWeekly } from "@/lib/hooks";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { GrowthGraph } from "@/components/growth/growth-graph";
import { WeeklyTrendChart } from "@/components/growth/weekly-trend-chart";
import { ReflectionForm } from "@/components/growth/reflection-form";
import { StreakCounter } from "@/components/growth/streak-counter";

/* ── Day detail modal (inline) ── */

interface DayDetailProps {
  date: string;
  onClose: () => void;
}

function DayDetail({ date, onClose }: DayDetailProps) {
  const { data: today } = useGrowthToday();

  // For non-today dates we only show score from the graph data
  // Today's detail has briefing + reflection
  const isToday = date === new Date().toISOString().split("T")[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="mx-4 w-full max-w-md rounded-[2px] border border-[rgba(245,240,232,0.1)] bg-[var(--pq-ink)] p-6 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg font-semibold text-[var(--pq-ivory)]">
            <span className="font-mono tabular-nums">{date}</span>
          </h3>
          <button
            onClick={onClose}
            className="text-[rgba(245,240,232,0.45)] hover:text-[var(--pq-bronze)]"
            aria-label="Close"
          >
            <svg width={20} height={20} viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        {isToday && today?.briefing && (
          <div className="mt-4">
            <h4 className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
              Priorities
            </h4>
            <ul className="mt-2 space-y-1">
              {today.briefing.priorities.map((p, i) => (
                <li key={i} className="text-sm text-[rgba(245,240,232,0.82)]">
                  <span className="font-mono tabular-nums text-[var(--pq-bronze)]">
                    {i + 1}.
                  </span>{" "}
                  {p}
                </li>
              ))}
            </ul>
            {today.briefing.motivation && (
              <p className="mt-3 border-t border-[rgba(245,240,232,0.08)] pt-3 text-sm text-[rgba(245,240,232,0.65)]">
                {today.briefing.motivation}
              </p>
            )}
          </div>
        )}

        {isToday && today?.reflection && (
          <div className="mt-4">
            <h4 className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
              Reflection
            </h4>
            {today.reflection.answers ? (
              <ul className="mt-2 space-y-2">
                {today.reflection.questions.map((q, i) => (
                  <li key={i}>
                    <p className="text-xs text-[rgba(245,240,232,0.45)]">
                      Q: {q}
                    </p>
                    <p className="text-sm text-[rgba(245,240,232,0.82)]">
                      A: {today.reflection!.answers![i] ?? "-"}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-[rgba(245,240,232,0.45)]">
                아직 답변하지 않았습니다.
              </p>
            )}
          </div>
        )}

        {isToday && today?.score && (
          <div className="mt-5 flex gap-4 border-t border-[rgba(245,240,232,0.08)] pt-4 text-center">
            <div className="flex-1">
              <p className="font-mono text-lg font-bold tabular-nums text-[var(--pq-ivory)]">
                {today.score.total}
              </p>
              <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
                Total
              </p>
            </div>
            <div className="flex-1">
              <p className="font-mono text-lg font-bold tabular-nums text-[var(--pq-bronze)]">
                {today.score.activity}
              </p>
              <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
                Activity
              </p>
            </div>
            <div className="flex-1">
              <p className="font-mono text-lg font-bold tabular-nums text-[var(--pq-bronze-light)]">
                {today.score.reflection}
              </p>
              <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
                Reflection
              </p>
            </div>
          </div>
        )}

        {!isToday && (
          <p className="mt-4 text-sm text-[rgba(245,240,232,0.45)]">
            상세 데이터는 오늘 날짜에서만 확인할 수 있습니다.
          </p>
        )}
      </div>
    </div>
  );
}

/* ── Main Page ── */

export default function GrowthPage() {
  const { data: graphData, isLoading: graphLoading } = useGrowthData("365d");
  const {
    data: todayData,
    isLoading: todayLoading,
    mutate: refreshToday,
  } = useGrowthToday();
  const { data: weeklyData } = useGrowthWeekly();

  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const handleDayClick = useCallback((date: string) => {
    setSelectedDate(date);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedDate(null);
  }, []);

  const handleReflectionSubmitted = useCallback(() => {
    refreshToday();
  }, [refreshToday]);

  const currentStreak = todayData?.score?.streak ?? 0;

  return (
    <ErrorBoundary>
      <div className="space-y-6 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-bold text-[var(--pq-ivory)]">Growth OS</h1>
          <p className="text-sm text-[rgba(245,240,232,0.55)]">
            Personal growth tracking and reflection
          </p>
        </div>

        {/* Streak + Score row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StreakCounter streak={currentStreak} />

          {todayData?.score ? (
            <>
              <div className="flex items-center gap-3 rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[rgba(34,197,94,0.12)]">
                  <span className="text-lg font-bold text-[#7DD897]">
                    {todayData.score.activity}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--pq-ivory)]">Activity</p>
                  <p className="text-xs text-[rgba(245,240,232,0.55)]">Today&apos;s activity score</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: "rgba(226,185,111,0.14)" }}>
                  <span className="text-lg font-bold" style={{ color: "#E2B96F" }}>
                    {todayData.score.reflection}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--pq-ivory)]">
                    Reflection
                  </p>
                  <p className="text-xs text-[rgba(245,240,232,0.55)]">
                    Today&apos;s reflection score
                  </p>
                </div>
              </div>
            </>
          ) : (
            <div className="col-span-2 flex items-center justify-center rounded-sm border border-dashed border-[rgba(245,240,232,0.12)] px-4 py-3">
              <p className="text-sm text-[rgba(245,240,232,0.55)]">
                {todayLoading
                  ? "Loading..."
                  : "아직 오늘의 점수가 없습니다."}
              </p>
            </div>
          )}
        </div>

        {/* Morning Briefing */}
        {todayData?.briefing && (
          <section className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5">
            <h2 className="text-base font-semibold text-[var(--pq-ivory)]">
              Today&apos;s Priorities
            </h2>
            <ul className="mt-3 space-y-2">
              {todayData.briefing.priorities.map((priority, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-[rgba(245,240,232,0.82)]"
                >
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(34,197,94,0.12)] text-xs font-medium text-[#7DD897]">
                    {i + 1}
                  </span>
                  {priority}
                </li>
              ))}
            </ul>
            {todayData.briefing.motivation && (
              <p className="mt-3 border-t border-[rgba(245,240,232,0.08)] pt-3 text-sm text-[rgba(245,240,232,0.55)]">
                {todayData.briefing.motivation}
              </p>
            )}
          </section>
        )}

        {/* Reflection Form */}
        {todayData?.reflection && (
          <section className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5">
            <h2 className="text-base font-semibold text-[var(--pq-ivory)]">
              Evening Reflection
            </h2>
            <div className="mt-3">
              <ReflectionForm
                reflection={todayData.reflection}
                onSubmitted={handleReflectionSubmitted}
              />
            </div>
          </section>
        )}

        {/* Growth Graph */}
        <section className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5">
          <h2 className="text-base font-semibold text-[var(--pq-ivory)]">
            Growth Graph
          </h2>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.55)]">
            Past 365 days. Click a day for details.
          </p>
          <div className="mt-4">
            {graphLoading ? (
              <div className="flex h-32 items-center justify-center">
                <p className="text-sm text-[rgba(245,240,232,0.55)]">Loading...</p>
              </div>
            ) : (
              <GrowthGraph
                data={graphData ?? []}
                onDayClick={handleDayClick}
              />
            )}
          </div>
        </section>

        {/* Weekly Trend */}
        <section className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5">
          <h2 className="text-base font-semibold text-[var(--pq-ivory)]">
            Weekly Trend
          </h2>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.55)]">
            Activity vs reflection over the last 4 weeks.
          </p>
          <div className="mt-4">
            {graphLoading ? (
              <div className="flex h-40 items-center justify-center">
                <p className="text-sm text-[rgba(245,240,232,0.55)]">Loading...</p>
              </div>
            ) : (
              <WeeklyTrendChart data={graphData ?? []} />
            )}
          </div>
        </section>

        {/* Weekly Reports */}
        {weeklyData && weeklyData.length > 0 && (
          <section className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5">
            <h2 className="text-base font-semibold text-[var(--pq-ivory)]">
              Weekly Reports
            </h2>
            <div className="mt-3 space-y-4">
              {weeklyData.map((report) => (
                <div
                  key={report.id}
                  className="rounded-sm border border-[rgba(245,240,232,0.06)] bg-[rgba(255,255,255,0.02)] p-4"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium text-[rgba(245,240,232,0.82)]">
                      Week of {report.week_start}
                    </h3>
                    <span className="rounded-full bg-[rgba(34,197,94,0.12)] px-2.5 py-0.5 text-xs font-medium text-[#7DD897]">
                      {report.week_score}/100
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-[rgba(245,240,232,0.82)] whitespace-pre-line">
                    {report.summary}
                  </p>
                  {report.patterns.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-[rgba(245,240,232,0.55)]">
                        Patterns
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {report.patterns.map((p, i) => (
                          <li
                            key={i}
                            className="text-xs text-[rgba(245,240,232,0.55)]"
                          >
                            - {p}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {report.next_week_suggestions.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-[rgba(245,240,232,0.55)]">
                        Next Week
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {report.next_week_suggestions.map((s, i) => (
                          <li
                            key={i}
                            className="text-xs text-[rgba(245,240,232,0.55)]"
                          >
                            {i + 1}. {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Day detail modal */}
        {selectedDate && (
          <DayDetail date={selectedDate} onClose={handleCloseDetail} />
        )}
      </div>
    </ErrorBoundary>
  );
}
