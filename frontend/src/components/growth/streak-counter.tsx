"use client";

/**
 * StreakCounter — displays the current consecutive usage streak.
 */

interface StreakCounterProps {
  streak: number;
}

export function StreakCounter({ streak }: StreakCounterProps) {
  return (
    <div className="flex items-center gap-3 rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] px-4 py-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[rgba(184,149,106,0.14)]">
        <svg
          width={20}
          height={20}
          viewBox="0 0 20 20"
          fill="none"
          style={{ color: "var(--pq-bronze)" }}
        >
          <path
            d="M10 2C10 2 6 6 6 10C6 12.21 7.79 14 10 14C12.21 14 14 12.21 14 10C14 6 10 2 10 2Z"
            fill="currentColor"
            fillOpacity={0.2}
          />
          <path
            d="M10 2C10 2 6 6 6 10C6 12.21 7.79 14 10 14C12.21 14 14 12.21 14 10C14 6 10 2 10 2Z"
            stroke="currentColor"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M10 10C10 10 8.5 12 8.5 13.5C8.5 14.33 9.17 15 10 15C10.83 15 11.5 14.33 11.5 13.5C11.5 12 10 10 10 10Z"
            fill="currentColor"
          />
        </svg>
      </div>
      <div>
        <p className="font-mono text-2xl font-bold tabular-nums text-[var(--pq-ivory)]">
          {streak}
          <span className="ml-1 text-sm font-normal text-[rgba(245,240,232,0.55)]">days</span>
        </p>
        <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          Current streak
        </p>
      </div>
    </div>
  );
}
