"use client";

/**
 * <WeeklyPulsePrompt /> — Monday-only, one-line nudge on /portfolio that links
 * to the weekly pulse form on /journal (#weekly-pulse).
 *
 * 2026-09-29: replaces the invisible <WeeklyPulseCard /> that auto-opened a
 * modal form here every Monday. The form now has a single home (/journal); this
 * line only points at it. It renders nothing when:
 *   - it is not Monday 07:00–24:00 KST (the old modal's window),
 *   - a pulse was already submitted this KST week (since Monday 00:00 KST),
 *   - the pulse history has not loaded yet (no flash for users who answered),
 *   - the user hid it today ("Hide for today", per-browser localStorage).
 *
 * Legal: a factual reminder about the user's own self-report — no advice.
 */

import * as React from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { usePulse, type PulseEntry } from "@/lib/cfo/hooks";
import { parseUtcSafe } from "@/lib/relative-time";
import { useT } from "@/lib/locale";

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DISMISS_KEY = "pq_pulse_prompt_dismissed";

/** KST calendar date (YYYY-MM-DD) of `now`. */
function kstDate(now: Date): string {
  return new Date(now.getTime() + KST_OFFSET_MS).toISOString().slice(0, 10);
}

/**
 * True on Monday 07:00–24:00 KST when no pulse in `history` was submitted
 * since Monday 00:00 KST. Pure — exported for tests.
 */
export function isPulsePromptDue(
  history: ReadonlyArray<Pick<PulseEntry, "submitted_at">>,
  now: Date,
): boolean {
  const kst = new Date(now.getTime() + KST_OFFSET_MS);
  if (kst.getUTCDay() !== 1 || kst.getUTCHours() < 7) return false;
  const mondayStartUtc =
    Date.UTC(kst.getUTCFullYear(), kst.getUTCMonth(), kst.getUTCDate()) -
    KST_OFFSET_MS;
  return !history.some((p) => {
    const t = parseUtcSafe(p.submitted_at);
    return Number.isFinite(t) && t >= mondayStartUtc;
  });
}

function readDismissed(): string | null {
  try {
    return window.localStorage.getItem(DISMISS_KEY);
  } catch {
    return null;
  }
}

export function WeeklyPulsePrompt() {
  const t = useT();
  const { data } = usePulse();
  // Evaluated after mount only — the server render has no clock or storage.
  const [today, setToday] = React.useState<string | null>(null);
  const [dismissed, setDismissed] = React.useState<string | null>(null);

  React.useEffect(() => {
    setToday(kstDate(new Date()));
    setDismissed(readDismissed());
  }, []);

  if (!today || !data?.history) return null;
  if (dismissed === today) return null;
  if (!isPulsePromptDue(data.history, new Date())) return null;

  const hide = () => {
    try {
      window.localStorage.setItem(DISMISS_KEY, today);
    } catch {
      /* storage blocked — hiding for this render is enough */
    }
    setDismissed(today);
  };

  return (
    <div
      role="status"
      className="flex items-center justify-between gap-3 rounded-[2px] border px-4 py-3"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <p
        className="font-serif text-pq-body-sm"
        style={{ margin: 0, color: "var(--pq-ivory-soft)", wordBreak: "keep-all" }}
      >
        {t("journal.pulsePrompt.text")}{" "}
        <Link
          href="/journal#weekly-pulse"
          className="whitespace-nowrap"
          style={{
            color: "var(--pq-bronze)",
            textDecoration: "underline",
            textUnderlineOffset: 3,
          }}
        >
          {t("journal.pulsePrompt.link")}
        </Link>
      </p>
      <button
        type="button"
        onClick={hide}
        aria-label={t("journal.pulsePrompt.dismiss")}
        title={t("journal.pulsePrompt.dismiss")}
        className="-mr-2 flex h-9 w-9 shrink-0 items-center justify-center text-[var(--pq-ivory-faint)] hover:text-[var(--pq-ivory)]"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export default WeeklyPulsePrompt;
