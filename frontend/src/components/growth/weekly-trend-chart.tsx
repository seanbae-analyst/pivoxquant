"use client";

/**
 * WeeklyTrendChart — simple SVG line chart comparing activity vs reflection
 * scores over the last 4 weeks. No charting library — pure SVG.
 */

import { useMemo } from "react";
import type { GrowthScoreEntry } from "@/lib/types";

const CHART_WIDTH = 600;
const CHART_HEIGHT = 160;
const PADDING_X = 40;
const PADDING_Y = 20;
const PLOT_WIDTH = CHART_WIDTH - PADDING_X * 2;
const PLOT_HEIGHT = CHART_HEIGHT - PADDING_Y * 2;

interface WeeklyTrendChartProps {
  data: GrowthScoreEntry[];
}

/** Aggregate daily scores into weekly averages. */
function aggregateWeekly(
  data: GrowthScoreEntry[],
): Array<{ week: string; activity: number; reflection: number }> {
  const weeks = new Map<
    string,
    { activity: number[]; reflection: number[] }
  >();

  for (const entry of data) {
    const d = new Date(entry.date);
    // ISO week start (Monday)
    const day = d.getDay();
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((day + 6) % 7));
    const weekKey = monday.toISOString().split("T")[0];

    if (!weeks.has(weekKey)) {
      weeks.set(weekKey, { activity: [], reflection: [] });
    }
    const w = weeks.get(weekKey)!;
    w.activity.push(entry.activity);
    w.reflection.push(entry.reflection);
  }

  const result = Array.from(weeks.entries())
    .map(([week, vals]) => ({
      week,
      activity: Math.round(
        vals.activity.reduce((a, b) => a + b, 0) / vals.activity.length,
      ),
      reflection: Math.round(
        vals.reflection.reduce((a, b) => a + b, 0) / vals.reflection.length,
      ),
    }))
    .sort((a, b) => a.week.localeCompare(b.week));

  // Last 4 weeks only
  return result.slice(-4);
}

function buildPath(
  points: number[],
  count: number,
): string {
  if (count < 2) return "";
  const stepX = PLOT_WIDTH / Math.max(count - 1, 1);

  return points
    .map((val, i) => {
      const x = PADDING_X + i * stepX;
      const y = PADDING_Y + PLOT_HEIGHT - (val / 100) * PLOT_HEIGHT;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

export function WeeklyTrendChart({ data }: WeeklyTrendChartProps) {
  const weeks = useMemo(() => aggregateWeekly(data), [data]);

  if (weeks.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-slate-400">
        주간 트렌드 데이터가 아직 없습니다.
      </div>
    );
  }

  const activityPath = buildPath(
    weeks.map((w) => w.activity),
    weeks.length,
  );
  const reflectionPath = buildPath(
    weeks.map((w) => w.reflection),
    weeks.length,
  );

  const stepX = PLOT_WIDTH / Math.max(weeks.length - 1, 1);

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="block w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Weekly trend chart: activity vs reflection scores"
      >
        {/* Y-axis grid lines */}
        {[0, 25, 50, 75, 100].map((val) => {
          const y = PADDING_Y + PLOT_HEIGHT - (val / 100) * PLOT_HEIGHT;
          return (
            <g key={val}>
              <line
                x1={PADDING_X}
                y1={y}
                x2={PADDING_X + PLOT_WIDTH}
                y2={y}
                stroke="#e2e8f0"
                strokeWidth={1}
                strokeDasharray={val === 0 ? "0" : "4 2"}
              />
              <text
                x={PADDING_X - 6}
                y={y + 4}
                textAnchor="end"
                fontSize={10}
                className="fill-slate-400"
              >
                {val}
              </text>
            </g>
          );
        })}

        {/* Activity line */}
        {activityPath && (
          <path
            d={activityPath}
            fill="none"
            stroke="#22c55e"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* Reflection line */}
        {reflectionPath && (
          <path
            d={reflectionPath}
            fill="none"
            stroke="#E2B96F"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* Data points — activity */}
        {weeks.map((w, i) => {
          const x = PADDING_X + i * stepX;
          const y =
            PADDING_Y + PLOT_HEIGHT - (w.activity / 100) * PLOT_HEIGHT;
          return (
            <circle key={`a-${w.week}`} cx={x} cy={y} r={3} fill="#22c55e" />
          );
        })}

        {/* Data points — reflection */}
        {weeks.map((w, i) => {
          const x = PADDING_X + i * stepX;
          const y =
            PADDING_Y + PLOT_HEIGHT - (w.reflection / 100) * PLOT_HEIGHT;
          return (
            <circle key={`r-${w.week}`} cx={x} cy={y} r={3} fill="#E2B96F" />
          );
        })}

        {/* X-axis labels */}
        {weeks.map((w, i) => {
          const x = PADDING_X + i * stepX;
          // Format as "4/14"
          const parts = w.week.split("-");
          const label = `${parseInt(parts[1], 10)}/${parseInt(parts[2], 10)}`;
          return (
            <text
              key={`x-${w.week}`}
              x={x}
              y={CHART_HEIGHT - 4}
              textAnchor="middle"
              fontSize={10}
              className="fill-slate-400"
            >
              {label}
            </text>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="mt-1 flex items-center justify-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
          Activity
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: "#E2B96F" }}
          />
          Reflection
        </span>
      </div>
    </div>
  );
}
