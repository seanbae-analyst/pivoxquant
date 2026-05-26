"use client";

/**
 * <WeeklyPulseCard /> — 5-question Monday-morning pulse.
 *
 * Triggers automatically once per week on Monday 07:00 KST when the user
 * lands on /home. Dismissible. Once submitted, the 8-week emotion +
 * confidence curve is rendered inline below the form.
 *
 * Props let any page host render the same component in a non-modal
 * context (e.g. Settings → Living CFO → "Submit early" or history view).
 *
 * Legal: records self-reported sentiment, not investment advice.
 * No BUY/SELL/HOLD language.
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { PQ_EASE, PQ_DUR_FAST, PQ_DUR_MICRO } from "@/lib/motion";
import { X } from "lucide-react";
import { toast } from "sonner";
import { usePulse, type PulseEntry } from "@/lib/cfo/hooks";
import { useFocusTrap } from "@/lib/useFocusTrap";

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

interface Props {
  /** External control of the modal. If omitted, component auto-opens
   *  on Monday 07:00 KST provided no pulse has been submitted this week. */
  open?: boolean;
  onClose?: () => void;
  /** Render inline (no modal chrome) — used by /settings history view. */
  inline?: boolean;
  className?: string;
}

export function WeeklyPulseCard({ open, onClose, inline, className }: Props) {
  const { data, submit } = usePulse();
  // Memo the array so the auto-open effect doesn't re-run on every render
  // (a fresh `?? []` would otherwise be a new identity each pass).
  const history = React.useMemo(() => data?.history ?? [], [data?.history]);

  // Auto-trigger logic: if `open` is undefined the host defers to the
  // component's own scheduler.
  const [autoOpen, setAutoOpen] = React.useState(false);

  React.useEffect(() => {
    if (open !== undefined || inline) return;
    if (typeof window === "undefined") return;

    const nowUtc = new Date();
    const kstOffsetMs = 9 * 60 * 60 * 1000;
    const kst = new Date(nowUtc.getTime() + kstOffsetMs);
    const isMonday = kst.getUTCDay() === 1;
    const hourKst = kst.getUTCHours();

    const lastSubmittedAt = history[history.length - 1]?.submitted_at;
    let alreadyThisWeek = false;
    if (lastSubmittedAt) {
      const last = new Date(lastSubmittedAt);
      const diffDays = (nowUtc.getTime() - last.getTime()) / 86400000;
      alreadyThisWeek = diffDays < 6;
    }

    if (isMonday && hourKst >= 7 && hourKst < 24 && !alreadyThisWeek) {
      // Respect a per-session dismiss.
      const dismissed = window.sessionStorage.getItem("pq_pulse_dismissed");
      if (!dismissed) setAutoOpen(true);
    }
  }, [open, inline, history]);

  const isOpen = inline || (open ?? autoOpen);
  const trapActive = Boolean(isOpen) && !inline;
  const dialogRef = useFocusTrap<HTMLDivElement>(trapActive);

  const handleDismiss = React.useCallback(() => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("pq_pulse_dismissed", "1");
    }
    setAutoOpen(false);
    onClose?.();
  }, [onClose]);

  // ESC + body scroll lock while modal open
  React.useEffect(() => {
    if (!trapActive) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleDismiss();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [trapActive, handleDismiss]);

  if (inline) {
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

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: PQ_DUR_MICRO }}
          style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)" }}
          onClick={handleDismiss}
          role="dialog"
          aria-modal="true"
          aria-label="Weekly pulse"
        >
          <motion.div
            ref={dialogRef}
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 10, opacity: 0 }}
            transition={{ duration: PQ_DUR_FAST, ease: PQ_EASE }}
            className="w-full max-w-lg bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] rounded-[2px] p-6"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="text-pq-eyebrow tracking-[0.26em] uppercase text-[var(--pq-bronze)]">
                  Layer 2 · Monday pulse
                </div>
                <h3 className="mt-1 font-serif text-xl text-[var(--pq-ivory)]">
                  How is this week looking?
                </h3>
              </div>
              <button
                type="button"
                onClick={handleDismiss}
                className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)]"
                aria-label="Dismiss pulse"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <PulseForm
              onSubmit={async (entry) => {
                try {
                  await submit(entry);
                  toast.success("Pulse recorded.");
                  handleDismiss();
                } catch {
                  toast.error("Could not save pulse.");
                }
              }}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
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
                    ? "rgba(139,111,71,0.18)"
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
                  ? "rgba(139,111,71,0.22)"
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
