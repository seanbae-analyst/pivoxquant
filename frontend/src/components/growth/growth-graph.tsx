"use client";

/**
 * GrowthGraph — GitHub-style contribution heatmap (365-day SVG).
 *
 * Each cell represents one day. Color intensity maps to the total_score.
 * Hover shows date + score tooltip. Click opens a detail callback.
 *
 * No external charting library — pure SVG for zero bundle cost.
 */

import { useMemo, useState, useCallback } from "react";
import type { GrowthScoreEntry } from "@/lib/types";
import { useT } from "@/lib/locale";

/* ── Constants ── */

const CELL_SIZE = 13;
const CELL_GAP = 3;
const CELL_RADIUS = 2;
const WEEKS_TO_SHOW = 53;
const DAYS_IN_WEEK = 7;
const LEFT_LABEL_WIDTH = 28;
const TOP_LABEL_HEIGHT = 20;
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_LABELS = ["", "Mon", "", "Wed", "", "Fri", ""];

/** Map a score (0-100) to a fill color.
 *  v3 lock-in (W6.2): faint ivory hairline for empty, bronze ramp otherwise.
 *  Replaces the GitHub-style green spectrum to honor the Vantablack palette. */
function scoreToColor(score: number | undefined): string {
  if (!score || score === 0) return "rgba(245,240,232,0.06)"; // empty cell — pq-ivory-line-soft
  if (score < 20) return "rgba(184,149,106,0.18)"; // bronze 18%
  if (score < 40) return "rgba(184,149,106,0.35)"; // bronze 35%
  if (score < 60) return "rgba(184,149,106,0.55)"; // bronze 55%
  if (score < 80) return "rgba(184,149,106,0.78)"; // bronze 78%
  return "#B8956A"; // bronze 100%
}

interface GrowthGraphProps {
  data: GrowthScoreEntry[];
  onDayClick?: (date: string) => void;
}

export function GrowthGraph({ data, onDayClick }: GrowthGraphProps) {
  const t = useT();
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    date: string;
    score: number;
  } | null>(null);

  // Build a lookup map: date string -> score entry
  const scoreMap = useMemo(() => {
    const map = new Map<string, GrowthScoreEntry>();
    for (const entry of data) {
      map.set(entry.date, entry);
    }
    return map;
  }, [data]);

  // Generate the 365-day grid starting from today going backwards
  const grid = useMemo(() => {
    const today = new Date();
    const cells: Array<{
      date: string;
      col: number;
      row: number;
      score: number;
    }> = [];

    // Find the Saturday of the current week (end column)
    const todayDay = today.getDay(); // 0=Sun, 6=Sat
    const endDate = new Date(today);
    endDate.setDate(endDate.getDate() + (6 - todayDay));

    // Go back 53 weeks from the end
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - (WEEKS_TO_SHOW * 7 - 1));

    const cursor = new Date(startDate);
    let col = 0;
    let row = cursor.getDay(); // 0=Sun

    while (cursor <= endDate) {
      const dateStr = cursor.toISOString().split("T")[0];
      const entry = scoreMap.get(dateStr);
      const isFuture = cursor > today;

      cells.push({
        date: dateStr,
        col,
        row,
        score: isFuture ? -1 : (entry?.total ?? 0),
      });

      // Advance
      row++;
      if (row >= DAYS_IN_WEEK) {
        row = 0;
        col++;
      }
      cursor.setDate(cursor.getDate() + 1);
    }

    return cells;
  }, [scoreMap]);

  // Month labels positioned at the start of each month
  const monthLabels = useMemo(() => {
    const labels: Array<{ label: string; col: number }> = [];
    let lastMonth = -1;

    for (const cell of grid) {
      const month = parseInt(cell.date.split("-")[1], 10) - 1;
      if (month !== lastMonth && cell.row === 0) {
        labels.push({ label: MONTH_LABELS[month], col: cell.col });
        lastMonth = month;
      }
    }

    return labels;
  }, [grid]);

  const svgWidth = LEFT_LABEL_WIDTH + WEEKS_TO_SHOW * (CELL_SIZE + CELL_GAP);
  const svgHeight = TOP_LABEL_HEIGHT + DAYS_IN_WEEK * (CELL_SIZE + CELL_GAP);

  const handleMouseEnter = useCallback(
    (e: React.MouseEvent<SVGRectElement>, date: string, score: number) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const container = e.currentTarget.closest("svg")?.getBoundingClientRect();
      if (!container) return;
      setTooltip({
        x: rect.left - container.left + CELL_SIZE / 2,
        y: rect.top - container.top - 8,
        date,
        score,
      });
    },
    [],
  );

  const handleMouseLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  const handleClick = useCallback(
    (date: string) => {
      onDayClick?.(date);
    },
    [onDayClick],
  );

  return (
    <div className="relative w-full overflow-x-auto">
      <svg
        width={svgWidth}
        height={svgHeight}
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="block"
        role="img"
        aria-label="Growth activity heatmap for the past year"
      >
        {/* Month labels */}
        {monthLabels.map(({ label, col }) => (
          <text
            key={`month-${col}`}
            x={LEFT_LABEL_WIDTH + col * (CELL_SIZE + CELL_GAP)}
            y={TOP_LABEL_HEIGHT - 6}
            fill="rgba(245,240,232,0.45)"
            fontSize={10}
            fontFamily="var(--font-sans)"
          >
            {label}
          </text>
        ))}

        {/* Day-of-week labels */}
        {DAY_LABELS.map((label, i) =>
          label ? (
            <text
              key={`day-${i}`}
              x={0}
              y={TOP_LABEL_HEIGHT + i * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 2}
              fill="rgba(245,240,232,0.45)"
              fontSize={10}
              fontFamily="var(--font-sans)"
            >
              {label}
            </text>
          ) : null,
        )}

        {/* Cells */}
        {grid.map(({ date, col, row, score }) => {
          if (score === -1) return null; // future date
          return (
            <rect
              key={date}
              x={LEFT_LABEL_WIDTH + col * (CELL_SIZE + CELL_GAP)}
              y={TOP_LABEL_HEIGHT + row * (CELL_SIZE + CELL_GAP)}
              width={CELL_SIZE}
              height={CELL_SIZE}
              rx={CELL_RADIUS}
              ry={CELL_RADIUS}
              fill={scoreToColor(score)}
              className="cursor-pointer transition-opacity hover:opacity-80"
              onMouseEnter={(e) => handleMouseEnter(e, date, score)}
              onMouseLeave={handleMouseLeave}
              onClick={() => handleClick(date)}
            />
          );
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-sm border border-[var(--pq-ivory-line)] bg-[var(--pq-ink)] px-2.5 py-1.5 font-mono text-xs text-[var(--pq-ivory)]"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
          }}
        >
          <span className="tabular-nums text-[var(--pq-bronze)]">{tooltip.date}</span>
          <span className="ml-2 tabular-nums text-[rgba(245,240,232,0.82)]">
            {tooltip.score > 0 ? `${tooltip.score}점` : "기록 없음"}
          </span>
        </div>
      )}

      {/* Legend */}
      <div className="mt-2 flex items-center justify-end gap-1 font-mono text-pq-mono-sm uppercase tracking-[0.22em] text-[rgba(245,240,232,0.55)]">
        <span>{t("growth.legendLess")}</span>
        {[0, 20, 40, 60, 80].map((level) => (
          <div
            key={level}
            className="h-3 w-3 rounded-sm"
            style={{ backgroundColor: scoreToColor(level || 0) }}
          />
        ))}
        <span>{t("growth.legendMore")}</span>
      </div>
    </div>
  );
}
