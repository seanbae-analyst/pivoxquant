"use client";

/**
 * <MoodNudgeCard /> — /home top nudge (CEO 2026-05-24, Mood 알림 quick-win v1).
 *
 * A persona-toned, dismissible check-in that asks "지금 기분 어때요?" and, on
 * mood select, returns a single §101-safe behavioural-reflection line. The
 * line is OBSERVATION / SELF-CHECK only — never a buy/sell/target instruction
 * (자본시장법 §101 면제 트랙). No backend: mood is not logged in v1; the
 * persona tone reads `user.risk_profile` from the existing session.
 *
 * Frequency: once per calendar day, gated via localStorage so it "pops" on the
 * first /home load of the day, then stays out of the way until dismissed/chosen.
 */

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { PQ_EASE, PQ_DUR_SLOW } from "@/lib/motion";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/locale";

type Mood = "calm" | "excited" | "anxious";

const STORAGE_KEY = "pq_mood_nudge_seen_on";

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

export function MoodNudgeCard() {
  const { user } = useAuth();
  const reduce = useReducedMotion();
  const t = useT();

  // Mood labels resolved from i18n — keeps component logic locale-agnostic.
  const MOODS: { id: Mood; label: string }[] = [
    { id: "calm", label: t("dashboard.moodNudge.calm") },
    { id: "excited", label: t("dashboard.moodNudge.excited") },
    { id: "anxious", label: t("dashboard.moodNudge.anxious") },
  ];

  // §101-safe reflective coaching — observation / self-check tone only.
  const COACHING: Record<Mood, string> = {
    calm: t("dashboard.moodNudge.coachingCalm"),
    excited: t("dashboard.moodNudge.coachingExcited"),
    anxious: t("dashboard.moodNudge.coachingAnxious"),
  };

  // Light persona tint for the eyebrow only (tone, not advice).
  // §101: collapse every declared risk_profile → one of the 3 disclosed
  // surface buckets (성장형 / 균형형 / 수익형). Never name a short-horizon
  // persona ("스윙 트레이더" / "공격형 스캘퍼") on the surface.
  const PERSONA_LABEL: Record<string, string> = {
    risk_managed_growth: t("persona.surfaceNames.balanced"),
    swing_trader: t("persona.surfaceNames.growth"),
    momentum_rider: t("persona.surfaceNames.growth"),
    macro_rotator: t("persona.surfaceNames.balanced"),
    aggressive_scalper: t("persona.surfaceNames.growth"),
    conservative: t("persona.surfaceNames.income"),
    moderate: t("persona.surfaceNames.balanced"),
    aggressive: t("persona.surfaceNames.growth"),
  };
  // Start hidden; reveal only after the client confirms it hasn't been seen
  // today (avoids SSR/hydration flash + respects the once-a-day gate).
  const [visible, setVisible] = React.useState(false);
  const [picked, setPicked] = React.useState<Mood | null>(null);

  React.useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) !== todayKey()) {
        setVisible(true);
      }
    } catch {
      // localStorage unavailable (private mode) — show once for this mount.
      setVisible(true);
    }
  }, []);

  const markSeen = React.useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, todayKey());
    } catch {
      // ignore — best effort
    }
  }, []);

  const dismiss = React.useCallback(() => {
    markSeen();
    setVisible(false);
  }, [markSeen]);

  const choose = React.useCallback(
    (m: Mood) => {
      setPicked(m);
      markSeen(); // chosen today → don't pop again until tomorrow
    },
    [markSeen],
  );

  if (!visible) return null;

  const personaLabel =
    (user?.risk_profile && PERSONA_LABEL[user.risk_profile]) || t("dashboard.moodNudge.personaFallback");

  return (
    <motion.section
      aria-label={t("dashboard.moodNudge.ariaLabel")}
      initial={reduce ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
      style={{
        marginBottom: 20,
        border: "1px solid var(--pq-ivory-line)",
        background:
          "linear-gradient(180deg, rgba(184,149,106,0.06), rgba(255,255,255,0.02))",
        borderRadius: 4,
        padding: "18px 22px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 6,
            }}
          >
            Mood check · {personaLabel}
          </div>
          {picked == null ? (
            <h2
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-h4)",
                letterSpacing: "-0.01em",
                color: "var(--pq-ivory)",
                margin: 0,
              }}
            >
              {t("dashboard.moodNudge.question")}
            </h2>
          ) : (
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.6,
                color: "rgba(245,240,232,0.86)",
                margin: 0,
                maxWidth: 560,
                wordBreak: "keep-all",
              }}
            >
              {COACHING[picked]}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={dismiss}
          aria-label={t("dashboard.moodNudge.dismissAriaLabel")}
          className="font-mono"
          style={{
            flexShrink: 0,
            background: "none",
            border: "none",
            color: "rgba(245,240,232,0.45)",
            cursor: "pointer",
            fontSize: "var(--pq-text-body)",
            lineHeight: 1,
            padding: 4,
          }}
        >
          ✕
        </button>
      </div>

      {picked == null && (
        <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          {MOODS.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => choose(m.id)}
              className="font-mono uppercase"
              style={{
                padding: "8px 18px",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--pq-ivory-line)",
                borderRadius: 999,
                color: "var(--pq-ivory)",
                cursor: "pointer",
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.14em",
                transition: "border-color 120ms, background 120ms",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--pq-bronze)";
                e.currentTarget.style.background = "rgba(184,149,106,0.10)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--pq-ivory-line)";
                e.currentTarget.style.background = "rgba(255,255,255,0.03)";
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}
    </motion.section>
  );
}

export default MoodNudgeCard;
