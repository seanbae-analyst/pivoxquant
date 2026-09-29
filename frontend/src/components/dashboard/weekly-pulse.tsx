"use client";

/**
 * <WeeklyPulseCard /> — the 5-field weekly pulse form + its history curve.
 *
 * Inline only. It is rendered in exactly one place, /journal's
 * <WeeklyPulseSection /> (the single input surface for the pulse).
 *
 * 2026-09-29: the modal mode was removed. /portfolio used to mount this card
 * invisibly and auto-open it as a modal on Mondays from 07:00 KST, which made
 * two input surfaces for the same answer. The Monday nudge survives as a
 * one-line link on /portfolio (<WeeklyPulsePrompt />) that sends the user to
 * this form on /journal.
 *
 * Legal: records self-reported sentiment, not investment advice.
 * No BUY/SELL/HOLD language.
 */

import * as React from "react";
import { toast } from "sonner";
import { usePulse, type PulseEntry } from "@/lib/cfo/hooks";

const TOPICS = [
  "Macro",
  "Earnings",
  "Sector rotation",
  "Single name",
  "Risk",
  "Options",
  "Korean market",
  "US market",
];

export function WeeklyPulseCard({ className }: { className?: string }) {
  const { data, submit } = usePulse();
  const history = data?.history ?? [];

  return (
    <div className={className}>
      <PulseForm
        onSubmit={async (entry) => {
          try {
            await submit(entry);
            toast.success("Pulse recorded.");
          } catch {
            toast.error("Could not save pulse.");
          }
        }}
      />
      {history.length > 0 && <PulseHistory history={history} />}
    </div>
  );
}

/* ── Form ── */

function PulseForm({
  onSubmit,
}: {
  onSubmit: (entry: Omit<PulseEntry, "submitted_at">) => Promise<void>;
}) {
  const [mood, setMood] = React.useState(3);
  const [confidence, setConfidence] = React.useState(3);
  const [worry, setWorry] = React.useState("");
  const [topics, setTopics] = React.useState<string[]>([]);
  const [learn, setLearn] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const toggleTopic = (t: string) =>
    setTopics((cur) =>
      cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t],
    );

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await onSubmit({ mood, confidence, worry, topics, learn });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={handle} className="space-y-5">
      <LikertRow
        label="Investing mood this week"
        value={mood}
        onChange={setMood}
      />
      <LikertRow
        label="Confidence level"
        value={confidence}
        onChange={setConfidence}
      />

      <div>
        <label
          className="block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1.5"
          htmlFor="pulse-worry"
        >
          One concern on your mind
        </label>
        <input
          id="pulse-worry"
          type="text"
          value={worry}
          onChange={(e) => setWorry(e.target.value)}
          placeholder="e.g. Fed pause odds"
          className="pq-ink-input w-full"
          maxLength={200}
        />
      </div>

      <div>
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-2">
          Topics you&apos;re watching
        </div>
        <div className="flex flex-wrap gap-1.5">
          {TOPICS.map((t) => {
            const active = topics.includes(t);
            return (
              <button
                key={t}
                type="button"
                onClick={() => toggleTopic(t)}
                className="text-pq-mono-sm px-2.5 py-1 rounded-[2px] border transition-colors"
                style={{
                  borderColor: active
                    ? "var(--pq-bronze)"
                    : "rgba(245,240,232,0.1)",
                  background: active
                    ? "rgba(var(--pq-bronze-wash-rgb),0.18)"
                    : "rgba(255,255,255,0.02)",
                  color: active ? "var(--pq-ivory)" : "rgba(245,240,232,0.7)",
                }}
              >
                {t}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <label
          className="block text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1.5"
          htmlFor="pulse-learn"
        >
          Something you want to learn
        </label>
        <input
          id="pulse-learn"
          type="text"
          value={learn}
          onChange={(e) => setLearn(e.target.value)}
          placeholder="e.g. Disposition effect basics"
          className="pq-ink-input w-full"
          maxLength={200}
        />
      </div>

      <button
        type="submit"
        disabled={busy}
        className="pq-ink-btn-bronze w-full disabled:opacity-50"
      >
        {busy ? "Saving…" : "Record pulse"}
      </button>
    </form>
  );
}

function LikertRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-1.5">
        {label}
      </div>
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => {
          const active = n === value;
          return (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              aria-label={`${label} — ${n} of 5`}
              aria-pressed={active}
              className="flex-1 h-9 rounded-[2px] border font-mono text-pq-body-sm transition-colors"
              style={{
                borderColor: active
                  ? "var(--pq-bronze)"
                  : "rgba(245,240,232,0.1)",
                background: active
                  ? "rgba(var(--pq-bronze-wash-rgb),0.22)"
                  : "rgba(255,255,255,0.02)",
                color: active ? "var(--pq-ivory)" : "rgba(245,240,232,0.55)",
              }}
            >
              {n}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── History (8-week curves) ── */

function PulseHistory({ history }: { history: PulseEntry[] }) {
  const recent = history.slice(-8);
  const w = 280;
  const h = 60;
  const pad = 3;
  const path = (values: number[], color: string) => {
    if (values.length < 2) return null;
    const step = (w - pad * 2) / (values.length - 1);
    const y = (v: number) => h - pad - ((v - 1) / 4) * (h - pad * 2);
    const d = values
      .map((v, i) => `${i === 0 ? "M" : "L"} ${pad + i * step},${y(v)}`)
      .join(" ");
    // SVG presentation attrs don't resolve var() — use style prop instead so
    // the v3 token (e.g. var(--pq-live)) actually renders.
    return (
      <path
        d={d}
        style={{ stroke: color }}
        strokeWidth={1.25}
        fill="none"
        strokeLinejoin="round"
      />
    );
  };

  const moodValues = recent.map((r) => r.mood);
  const confValues = recent.map((r) => r.confidence);

  return (
    <section className="mt-6 pt-5 border-t border-[var(--pq-ivory-line)]">
      <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        Pulse history · last {recent.length} weeks
      </div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        width="100%"
        height={h}
        preserveAspectRatio="none"
        className="mt-2"
        role="img"
        aria-label="Emotion and confidence curves"
      >
        {path(moodValues, "#B8956A")}
        {path(confValues, "var(--pq-live)")}
      </svg>
      <div className="mt-2 flex gap-4 text-pq-caption">
        <span className="flex items-center gap-1.5" style={{ color: "rgba(245,240,232,0.7)" }}>
          <span
            aria-hidden
            style={{
              width: 10,
              height: 2,
              background: "#B8956A",
              display: "inline-block",
            }}
          />
          Mood
        </span>
        <span className="flex items-center gap-1.5" style={{ color: "rgba(245,240,232,0.7)" }}>
          <span
            aria-hidden
            style={{
              width: 10,
              height: 2,
              background: "var(--pq-live)",
              display: "inline-block",
            }}
          />
          Confidence
        </span>
      </div>
    </section>
  );
}

export default WeeklyPulseCard;
