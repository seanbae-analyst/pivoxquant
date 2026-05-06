"use client";

/**
 * <SectionFeedbackBar /> — 3-button reaction row for artifact cards.
 *
 * Useful · Meh · Skip. Records feedback to /api/profile/feedback, then
 * persists the last vote locally so the user sees their own signal
 * reflected even before the backend learns from it.
 *
 * Placed at the foot of each artifact card (or any section of a report).
 * Stateless host — the hook `useFeedback` handles persistence + retry.
 *
 * Legal: reactions describe the reader's preference, not an investment
 * signal. No BUY/SELL/HOLD language.
 */

import * as React from "react";
import { motion } from "motion/react";
import { useFeedback, type FeedbackVote } from "@/lib/cfo/hooks";

interface Props {
  /** Unique identifier of the artifact (or a stable slug for catalog items). */
  artifactId: string;
  /** Section heading the vote applies to. Defaults to "overall". */
  section?: string;
  /** Compact spacing for cramped card footers. Default false. */
  compact?: boolean;
  className?: string;
}

const BUTTONS: { id: FeedbackVote; glyph: string; label: string }[] = [
  { id: "useful", glyph: "🔥", label: "Useful" },
  { id: "meh", glyph: "😐", label: "Meh" },
  { id: "skip", glyph: "😴", label: "Skip" },
];

const LS_KEY = "pq_cfo_feedback_votes_v1";

function readLocalVote(artifactId: string, section: string): FeedbackVote | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const map = JSON.parse(raw) as Record<string, FeedbackVote>;
    return map[`${artifactId}:${section}`] ?? null;
  } catch {
    return null;
  }
}

function writeLocalVote(
  artifactId: string,
  section: string,
  vote: FeedbackVote,
): void {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    const map = (raw ? JSON.parse(raw) : {}) as Record<string, FeedbackVote>;
    map[`${artifactId}:${section}`] = vote;
    window.localStorage.setItem(LS_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export function SectionFeedbackBar({
  artifactId,
  section = "overall",
  compact = false,
  className = "",
}: Props) {
  const { submit } = useFeedback();
  const [vote, setVote] = React.useState<FeedbackVote | null>(() =>
    readLocalVote(artifactId, section),
  );
  const [busy, setBusy] = React.useState<FeedbackVote | null>(null);

  const handleClick = async (choice: FeedbackVote) => {
    if (busy) return;
    setBusy(choice);
    setVote(choice);
    writeLocalVote(artifactId, section, choice);
    try {
      await submit({ artifact_id: artifactId, section, vote: choice });
    } catch {
      // Rollback
      setVote(null);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      className={`flex items-center gap-2 font-mono ${className}`}
      role="group"
      aria-label="Section feedback"
    >
      <span
        className="text-[12px] uppercase tracking-[0.22em]"
        style={{ color: "var(--pq-bronze)" }}
      >
        {vote ? "Recorded" : "Helpful?"}
      </span>
      <div className="flex items-center gap-1">
        {BUTTONS.map((b) => {
          const active = vote === b.id;
          return (
            <motion.button
              key={b.id}
              type="button"
              onClick={() => handleClick(b.id)}
              whileTap={{ scale: 0.92 }}
              disabled={busy !== null}
              aria-label={`${b.label} feedback`}
              aria-pressed={active}
              className="flex items-center gap-1 rounded-[2px] border transition-colors"
              style={{
                padding: compact ? "3px 7px" : "4px 9px",
                fontSize: compact ? 11 : 12,
                borderColor: active
                  ? "var(--pq-bronze)"
                  : "rgba(245,240,232,0.1)",
                background: active
                  ? "rgba(139,111,71,0.18)"
                  : "rgba(255,255,255,0.02)",
                color: active
                  ? "var(--pq-ivory)"
                  : "rgba(245,240,232,0.7)",
                opacity: busy && busy !== b.id ? 0.4 : 1,
                cursor: busy ? "default" : "pointer",
              }}
            >
              <span aria-hidden>{b.glyph}</span>
              <span
                className="hidden sm:inline text-[12px] uppercase tracking-[0.18em]"
              >
                {b.label}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

export default SectionFeedbackBar;
