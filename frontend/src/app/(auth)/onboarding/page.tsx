"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { Check, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { PQ_EASE, PQ_DUR_BASE, PQ_DUR_SLOW } from "@/lib/motion";
import { useLocale } from "@/lib/locale";
import {
  WIZARD_QUESTIONS,
  LEGAL_QUESTION,
  CATEGORIES,
} from "@/data/onboarding-questions";
import type {
  DeclaredStatement,
  OnboardingOption,
  OnboardingQuestion,
} from "@/data/onboarding-questions";

// ── Constants ────────────────────────────────────────────────────────────────

const STORAGE_KEY = "pivoxquant_onboarding_answers";
const TOTAL_STEPS = WIZARD_QUESTIONS.length + 1; // 5 wizard + 1 legal

/** Shape of POST /api/profile/onboarding for a V3 submission. */
interface OnboardingV3Response {
  ok: boolean;
  questionnaire_version?: number;
  declared?: DeclaredStatement[];
}

// ── Icon mapping (Lucide-compatible simple shapes) ───────────────────────────

const ICON_MAP: Record<string, string> = {
  seedling: "\u{1F331}", sprout: "\u{1F33F}", leaf: "\u{1F343}", tree: "\u{1F333}", mountain: "\u{26F0}\u{FE0F}",
  wallet: "\u{1F45B}", banknote: "\u{1F4B5}", "piggy-bank": "\u{1F416}", safe: "\u{1F512}", building: "\u{1F3E6}",
  coin: "\u{1FA99}", coins: "\u{1FA99}", "trending-up": "\u{1F4C8}", shield: "\u{1F6E1}\u{FE0F}",
  briefcase: "\u{1F4BC}", laptop: "\u{1F4BB}", zap: "\u{26A1}", book: "\u{1F4D6}",
  archive: "\u{1F4E6}", clock: "\u{1F551}", repeat: "\u{1F501}", activity: "\u{1F4CA}",
  sun: "\u{2600}\u{FE0F}", calendar: "\u{1F4C5}", "calendar-range": "\u{1F5D3}\u{FE0F}",
  hourglass: "\u{231B}", infinity: "\u{267E}\u{FE0F}", bot: "\u{1F916}",
  "calendar-days": "\u{1F4C6}", "calendar-check": "\u{2705}",
  target: "\u{1F3AF}", crosshair: "\u{1F3AF}", layers: "\u{1F4DA}", grid: "\u{1F3F2}", globe: "\u{1F30D}",
  "bar-chart": "\u{1F4CA}", rocket: "\u{1F680}", flame: "\u{1F525}", star: "\u{2B50}",
  landmark: "\u{1F3DB}\u{FE0F}", "book-open": "\u{1F4D6}",
};

function getIcon(key?: string): string {
  if (!key) return "";
  return ICON_MAP[key] ?? "";
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function loadSavedAnswers(): Record<string, string | string[] | number> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, string | string[] | number>) : {};
  } catch {
    return {};
  }
}

function saveAnswers(answers: Record<string, string | string[] | number>) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(answers));
  } catch {
    // storage full -- silent fail
  }
}

// ── Subcomponents ────────────────────────────────────────────────────────────

/** Progress bar at the top of the wizard. */
function ProgressBar({ current, total, category }: { current: number; total: number; category: string }) {
  const pct = Math.round((current / total) * 100);
  const catMeta = CATEGORIES[category];
  const { locale } = useLocale();

  return (
    <div className="w-full">
      {/* Header row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
          >
            {locale === "ko" ? (catMeta?.label_kr || catMeta?.label || category) : (catMeta?.label ?? category)}
          </span>
        </div>
        <span
          className="text-xs tabular-nums font-medium"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.45)" }}
        >
          {current} of {total}
        </span>
      </div>

      {/* Bar */}
      <div
        className="relative h-1.5 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: "rgba(var(--pq-ivory-rgb), 0.08)" }}
      >
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: "linear-gradient(90deg, var(--pq-bronze-light), var(--pq-bronze))" }}
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        />
      </div>
    </div>
  );
}

/** Single-select option card. */
function OptionCard({
  option,
  selected,
  onSelect,
}: {
  option: OnboardingOption;
  selected: boolean;
  onSelect: () => void;
}) {
  const icon = getIcon(option.icon);
  const { locale } = useLocale();
  const displayLabel = locale === "ko" ? (option.label_kr || option.label) : option.label;

  return (
    <motion.button
      type="button"
      onClick={onSelect}
      whileTap={{ scale: 0.98 }}
      className={`
        group relative flex w-full items-center gap-3 border px-5 py-4
        text-left transition-all duration-300
        ${
          selected
            ? "border-[var(--pq-bronze-light)] bg-[rgba(184,149,106,0.08)] shadow-[0_0_0_1px_rgba(184,149,106,0.25)]"
            : "border-[rgba(245,240,232,0.1)] bg-[var(--pq-ivory-line-ghost)] hover:border-[rgba(245,240,232,0.25)] hover:bg-[var(--pq-ivory-line-faint)]"
        }
      `}
      style={{
        transitionTimingFunction: "var(--motion-easing-emphasized, cubic-bezier(0.16, 1, 0.3, 1))",
        borderRadius: "var(--pq-radius-card)",
      }}
    >
      {/* Selection indicator */}
      <div
        className={`
          flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all duration-200
          ${
            selected
              ? "border-[var(--pq-bronze-light)] bg-[var(--pq-bronze-light)]"
              : "border-[rgba(245,240,232,0.3)] bg-transparent group-hover:border-[rgba(245,240,232,0.5)]"
          }
        `}
      >
        {selected && <Check size={12} strokeWidth={3} style={{ color: "var(--pq-ink)" }} />}
      </div>

      {/* Icon */}
      {icon && <span className="text-lg leading-none">{icon}</span>}

      {/* Text */}
      <span
        className="text-pq-lead leading-snug font-medium"
        style={{
          color: selected
            ? "var(--pq-ivory)"
            : "rgba(var(--pq-ivory-rgb), 0.7)",
        }}
      >
        {displayLabel}
      </span>
    </motion.button>
  );
}

/** Multi-select option card with checkbox style. */
function MultiOptionCard({
  option,
  selected,
  onToggle,
}: {
  option: OnboardingOption;
  selected: boolean;
  onToggle: () => void;
}) {
  const { locale } = useLocale();
  const displayLabel = locale === "ko" ? (option.label_kr || option.label) : option.label;
  return (
    <motion.button
      type="button"
      onClick={onToggle}
      whileTap={{ scale: 0.98 }}
      className={`
        group relative flex w-full items-center gap-3 border px-5 py-4
        text-left transition-all duration-300
        ${
          selected
            ? "border-[var(--pq-bronze-light)] bg-[rgba(184,149,106,0.08)]"
            : "border-[rgba(245,240,232,0.1)] bg-[var(--pq-ivory-line-ghost)] hover:border-[rgba(245,240,232,0.25)] hover:bg-[var(--pq-ivory-line-faint)]"
        }
      `}
      style={{
        transitionTimingFunction: "var(--motion-easing-emphasized, cubic-bezier(0.16, 1, 0.3, 1))",
        borderRadius: "var(--pq-radius-card)",
      }}
    >
      {/* Checkbox */}
      <div
        className={`
          flex h-5 w-5 shrink-0 items-center justify-center rounded-[2px] border-2 transition-all duration-200
          ${
            selected
              ? "border-[var(--pq-bronze-light)] bg-[var(--pq-bronze-light)]"
              : "border-[rgba(245,240,232,0.3)] bg-transparent group-hover:border-[rgba(245,240,232,0.5)]"
          }
        `}
      >
        {selected && <Check size={12} strokeWidth={3} style={{ color: "var(--pq-ink)" }} />}
      </div>

      {/* Text */}
      <span
        className="text-pq-lead leading-snug font-medium"
        style={{
          color: selected
            ? "var(--pq-ivory)"
            : "rgba(var(--pq-ivory-rgb), 0.7)",
        }}
      >
        {displayLabel}
      </span>
    </motion.button>
  );
}

/** Slider question (Market Knowledge self-rating). */
function SliderInput({
  question,
  value,
  onChange,
}: {
  question: OnboardingQuestion;
  value: number;
  onChange: (v: number) => void;
}) {
  const min = question.min ?? 1;
  const max = question.max ?? 5;
  const currentOption = question.options.find((o) => o.value === value);
  const { locale } = useLocale();
  const displayOptionLabel = locale === "ko" ? (currentOption?.label_kr || currentOption?.label || "") : (currentOption?.label ?? "");
  const displayMinLabel = locale === "ko" ? (question.min_label_kr || question.min_label) : question.min_label;
  const displayMaxLabel = locale === "ko" ? (question.max_label_kr || question.max_label) : question.max_label;

  return (
    <div className="flex flex-col gap-6">
      {/* Current value display */}
      <div className="text-center">
        <div
          className="mb-1 text-4xl font-bold font-display"
          style={{
            color: "var(--pq-bronze-light)",
          }}
        >
          {value}
        </div>
        <div
          className="text-sm font-medium"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.75)" }}
        >
          {displayOptionLabel}
        </div>
      </div>

      {/* Slider */}
      <div className="px-2">
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={locale === "ko" ? (question.question_kr || question.question) : question.question}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-valuetext={displayOptionLabel}
          className="slider-input w-full"
        />

        {/* Labels below */}
        <div className="mt-3 flex items-start justify-between">
          <span
            className="max-w-[120px] text-xs leading-tight"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.5)" }}
          >
            {displayMinLabel}
          </span>
          <span
            className="max-w-[120px] text-right text-xs leading-tight"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.5)" }}
          >
            {displayMaxLabel}
          </span>
        </div>
      </div>

      {/* Step indicators */}
      <div className="flex justify-between px-2">
        {question.options.map((opt) => (
          <button
            key={String(opt.value)}
            type="button"
            onClick={() => onChange(Number(opt.value))}
            className={`
              flex h-11 w-11 items-center justify-center rounded-full text-sm font-semibold transition-all duration-200
              ${
                Number(opt.value) === value
                  ? "bg-[var(--pq-bronze)] text-[var(--pq-ink)] shadow-lg shadow-[rgba(184,149,106,0.3)]"
                  : "bg-[var(--pq-ivory-line-soft)] text-[var(--pq-ivory-dim)] hover:bg-[rgba(245,240,232,0.12)]"
              }
            `}
          >
            {String(opt.value)}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Legal confirmations -- all checkboxes on one screen. */
function LegalStep({
  answers,
  onToggle,
}: {
  answers: string[];
  onToggle: (val: string) => void;
}) {
  const { locale } = useLocale();
  return (
    <div className="flex flex-col gap-4">
      <div className="mb-2">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">{"\u{1F6E1}\u{FE0F}"}</span>
          <span
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--pq-bronze)", letterSpacing: "var(--pq-track-eyebrow)" }}
          >
            Legal & Compliance
          </span>
        </div>
        <h2
          className="text-xl font-bold leading-tight font-display"
          style={{
            color: "var(--pq-ivory)",
            letterSpacing: "var(--pq-track-tight)",
          }}
        >
          {locale === "ko" ? (LEGAL_QUESTION.question_kr || LEGAL_QUESTION.question) : LEGAL_QUESTION.question}
        </h2>
        <p
          className="mt-1 text-sm"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
        >
          {locale === "ko" ? "모든 항목을 확인해야 계속 진행할 수 있습니다." : "All confirmations are required to proceed."}
        </p>
      </div>

      {LEGAL_QUESTION.options.map((opt) => {
        const checked = answers.includes(String(opt.value));
        const optLabel = locale === "ko" ? (opt.label_kr || opt.label) : opt.label;
        return (
          <motion.button
            key={String(opt.value)}
            type="button"
            onClick={() => onToggle(String(opt.value))}
            whileTap={{ scale: 0.98 }}
            className={`
              flex items-start gap-4 border px-5 py-4 text-left transition-all duration-300
              ${
                checked
                  ? "border-[var(--pq-bronze-light)] bg-[rgba(184,149,106,0.08)]"
                  : "border-[rgba(245,240,232,0.1)] bg-[var(--pq-ivory-line-ghost)] hover:border-[rgba(245,240,232,0.25)]"
              }
            `}
            style={{
              transitionTimingFunction: "var(--motion-easing-emphasized, cubic-bezier(0.16, 1, 0.3, 1))",
              borderRadius: "var(--pq-radius-card)",
            }}
          >
            <div
              className={`
                mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[2px] border-2 transition-all duration-200
                ${
                  checked
                    ? "border-[var(--pq-bronze-light)] bg-[var(--pq-bronze-light)]"
                    : "border-[rgba(245,240,232,0.3)] bg-transparent"
                }
              `}
            >
              {checked && <Check size={12} strokeWidth={3} style={{ color: "var(--pq-ink)" }} />}
            </div>
            <span
              className="text-pq-body leading-relaxed"
              style={{
                color: checked
                  ? "var(--pq-ivory)"
                  : "rgba(var(--pq-ivory-rgb), 0.7)",
                fontWeight: checked ? 500 : 400,
              }}
            >
              {optLabel}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}

/**
 * Result screen — the user's own answers, echoed back verbatim.
 *
 * v3 (2026-09-06): no persona label, no tagline, no "features activated".
 * The competitor research (docs/strategy/onboarding-competitor-research_
 * 2026-09-06.md §5) found self-report risk questionnaires explain little of
 * later behaviour and regulators found most profiling tools defective; the
 * only honest use of these answers is as a baseline the mirror can hold up
 * against real trades later. So this screen says exactly that.
 */
function ResultScreen({
  statements,
  onContinue,
  loading,
}: {
  statements: DeclaredStatement[];
  onContinue: () => void;
  loading: boolean;
}) {
  const { locale } = useLocale();
  const ko = locale === "ko";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
      className="flex flex-col items-center px-4 py-8"
    >
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        className="text-sm font-semibold uppercase tracking-wider"
        style={{
          color: "var(--pq-bronze)",
          letterSpacing: "var(--pq-track-eyebrow)",
        }}
      >
        {ko ? "기록해 두었습니다" : "Recorded"}
      </motion.p>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        className="mt-2 text-center text-2xl font-bold tracking-tight font-display sm:text-3xl"
        style={{
          color: "var(--pq-ivory)",
          letterSpacing: "var(--pq-track-tight)",
        }}
      >
        {ko ? "오늘 이렇게 말씀하셨습니다." : "This is what you said today."}
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        className="mt-3 max-w-sm text-center text-pq-lead leading-relaxed"
        style={{ color: "rgba(var(--pq-ivory-rgb), 0.7)" }}
      >
        {ko
          ? "점수도 유형도 매기지 않습니다. 거래가 쌓이면 이 문장을 실제 기록 옆에 나란히 보여드립니다."
          : "No score, no type. Once trades accumulate, these lines are shown next to what you actually did."}
      </motion.p>

      {/* The user's own words */}
      <motion.dl
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        className="mt-8 w-full max-w-sm space-y-3"
      >
        {statements.map((st, i) => (
          <motion.div
            key={st.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 + i * 0.08, duration: PQ_DUR_SLOW, ease: PQ_EASE }}
            className="px-4 py-3"
            style={{
              backgroundColor: "rgba(184,149,106,0.06)",
              border: "1px solid rgba(184,149,106,0.2)",
              borderRadius: "var(--pq-radius-card)",
            }}
          >
            <dt
              className="text-xs leading-snug"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
            >
              {ko ? st.question_kr : st.question}
            </dt>
            <dd
              className="mt-1 text-pq-lead font-medium"
              style={{ color: "var(--pq-ivory)" }}
            >
              {ko ? st.label_kr : st.label}
            </dd>
          </motion.div>
        ))}
      </motion.dl>

      {/* CTA */}
      <motion.button
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0, duration: PQ_DUR_SLOW, ease: PQ_EASE }}
        onClick={onContinue}
        disabled={loading}
        className="mt-10 flex w-full max-w-sm items-center justify-center gap-2 px-8 py-4 text-base font-bold transition-all duration-300 hover:shadow-xl active:scale-[0.98] disabled:opacity-60"
        style={{
          transitionTimingFunction: "var(--motion-easing-emphasized, cubic-bezier(0.16, 1, 0.3, 1))",
          backgroundColor: "var(--pq-bronze)",
          color: "var(--pq-ink)",
          borderRadius: "var(--pq-radius-cta)",
          boxShadow: "0 8px 24px rgba(var(--pq-bronze-rgb),0.25)",
        }}
      >
        {loading ? (
          <Loader2 size={20} className="animate-spin" />
        ) : (
          <>
            {ko ? "거울로 가기" : "Go to the mirror"}
            <ChevronRight size={18} />
          </>
        )}
      </motion.button>
    </motion.div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading: authLoading, refresh } = useAuth();

  // Steps: 0..4 = wizard questions, 5 = legal, 6 = result screen
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | string[] | number>>(loadSavedAnswers);
  const [direction, setDirection] = useState(1); // 1 = forward, -1 = back
  const [submitting, setSubmitting] = useState(false);
  // The backend's echo of the user's own answers (v3). Set once the POST
  // succeeds; the result screen renders it verbatim.
  const [declared, setDeclared] = useState<DeclaredStatement[]>([]);
  const [finishing, setFinishing] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Redirect if not logged in, or if onboarding is already complete
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
      return;
    }
    if (!authLoading && user && user.onboarding_completed === true) {
      router.replace("/mirror");
    }
  }, [authLoading, user, router]);

  // Restore saved step from answers — server draft wins if present so
  // a user who answered N questions on mobile picks up at N on desktop.
  // localStorage is the fallback when the network call fails / first paint.
  useEffect(() => {
    const local = loadSavedAnswers();
    if (Object.keys(local).length > 0) {
      setAnswers(local);
    }
    // Fire-and-forget server hydrate. apiFetch handles CSRF + cookies.
    apiFetch<{ draft: Record<string, string | string[] | number> | null }>(
      API.profile.onboardingDraft,
    )
      .then((data) => {
        if (data?.draft && Object.keys(data.draft).length > 0) {
          // Server has fresher data (or local was empty) → adopt it.
          setAnswers(data.draft);
        }
      })
      .catch(() => {
        // Best-effort hydrate. localStorage already populated above.
      });
  }, []);

  // Save answers to localStorage + server draft whenever they change.
  // 2026-05-17 wave 12 UX P0 (PR #427): localStorage stays as the hot
  // path (synchronous, instant); a debounced server PUT every 2 seconds
  // syncs the draft so device switch / ITP eviction doesn't lose work.
  // 2s debounce balances network chatter vs how much answer drift we
  // tolerate (≤2s, well under the wizard's per-question rhythm).
  useEffect(() => {
    saveAnswers(answers);
    if (Object.keys(answers).length === 0) return;
    const t = setTimeout(() => {
      apiFetch(API.profile.onboardingDraft, {
        method: "PUT",
        body: JSON.stringify({ answers }),
      }).catch(() => {
        // Silent — localStorage already holds the answers and the next
        // change will retry. No user-facing toast for background syncs.
      });
    }, 2_000);
    return () => clearTimeout(t);
  }, [answers]);

  // 2026-05-17 wave 12 UX P1 (PR #428): beforeunload guard. The wizard
  // has localStorage + server-side draft (PR #427) but those sync 2s
  // after the most recent answer change — a user who answers a question
  // then immediately closes the tab inside that window can still lose
  // the most recent answer. The guard fires only when the user has
  // invested non-trivial progress (>=3 questions answered) so it never
  // annoys someone who barely started. The result-screen / submitting
  // path is excluded inline (step === TOTAL_STEPS) so we don't
  // shadow-reference `isResultScreen` which is declared a few lines
  // below.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const answeredCount = Object.keys(answers).length;
    const onResult = step === TOTAL_STEPS;
    const shouldGuard = answeredCount >= 3 && !onResult && !submitting;
    if (!shouldGuard) return;

    function handleBeforeUnload(e: BeforeUnloadEvent) {
      // Per the spec, browsers ignore the custom message and show a
      // native confirm dialog. Setting returnValue triggers it.
      e.preventDefault();
      e.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [answers, step, submitting]);

  // Current question
  const isLegalStep = step === WIZARD_QUESTIONS.length;
  const isResultScreen = step === TOTAL_STEPS;
  const currentQuestion: OnboardingQuestion | null =
    step < WIZARD_QUESTIONS.length ? WIZARD_QUESTIONS[step] : null;

  // Check if current step answer is valid
  const isStepValid = useMemo(() => {
    if (isResultScreen) return true;

    if (isLegalStep) {
      const legalAnswers = (answers.legal_confirmations ?? []) as string[];
      const requiredValues = LEGAL_QUESTION.options
        .filter((o) => o.required)
        .map((o) => String(o.value));
      return requiredValues.every((v) => legalAnswers.includes(v));
    }

    if (!currentQuestion) return false;

    const ans = answers[currentQuestion.id];

    if (currentQuestion.type === "single") {
      return ans !== undefined && ans !== "";
    }
    if (currentQuestion.type === "multi") {
      return Array.isArray(ans) && ans.length > 0;
    }
    if (currentQuestion.type === "slider") {
      return ans !== undefined;
    }
    return false;
  }, [answers, isLegalStep, isResultScreen, currentQuestion]);

  // ── Answer handlers ──────────────────────────────────────────────────────

  const handleSingleSelect = useCallback(
    (questionId: string, value: string) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
    },
    [],
  );

  const handleMultiToggle = useCallback(
    (questionId: string, value: string) => {
      setAnswers((prev) => {
        const existing = (prev[questionId] ?? []) as string[];

        // "None of the above" logic: selecting it clears others, selecting others clears "none"
        if (value === "none") {
          return { ...prev, [questionId]: existing.includes("none") ? [] : ["none"] };
        }

        let updated = existing.filter((v) => v !== "none");
        if (updated.includes(value)) {
          updated = updated.filter((v) => v !== value);
        } else {
          updated = [...updated, value];
        }
        return { ...prev, [questionId]: updated };
      });
    },
    [],
  );

  const handleSliderChange = useCallback(
    (questionId: string, value: number) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
    },
    [],
  );

  // Slider steps never wrote their value to `answers`, so isStepValid
  // (ans !== undefined) stayed false and "Next" was dead until the user
  // dragged the handle — a silent onboarding dead-end at knowledge_self_rating
  // (every new user hit it). Seed the range midpoint on entry: for the only
  // slider (min 1 / max 5) that is 3, which matches the backend's missing-value
  // default (questionnaire.py: answers.get("knowledge_self_rating", 3)), so a
  // user who never touches the handle is classified at the same neutral score
  // as before — not the lowest (min). The functional updater + prev-guard keeps
  // it idempotent and lets us drop `answers` from deps (no render burst).
  useEffect(() => {
    if (currentQuestion && currentQuestion.type === "slider") {
      const mid = Math.round(
        ((currentQuestion.min ?? 1) + (currentQuestion.max ?? 5)) / 2,
      );
      setAnswers((prev) =>
        prev[currentQuestion.id] === undefined
          ? { ...prev, [currentQuestion.id]: mid }
          : prev,
      );
    }
  }, [currentQuestion]);

  const handleLegalToggle = useCallback((value: string) => {
    setAnswers((prev) => {
      const existing = (prev.legal_confirmations ?? []) as string[];
      const updated = existing.includes(value)
        ? existing.filter((v) => v !== value)
        : [...existing, value];
      return { ...prev, legal_confirmations: updated };
    });
  }, []);

  // ── Navigation ───────────────────────────────────────────────────────────

  // Submit answers to backend. v3: the POST happens when the user leaves the
  // legal step, and the result screen shows what the server recorded — so
  // the screen can never display something that was not saved.
  const handleSubmit = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await apiFetch<OnboardingV3Response>(API.profile.onboarding, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setDeclared(Array.isArray(res?.declared) ? res.declared : []);
      // Clean up stored progress (answers now live server-side).
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem("pivoxquant_onboarding_full_answers");
      setDirection(1);
      setStep(TOTAL_STEPS);
      containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      // Sonner toast keeps the user in-flow; answers stay in localStorage so
      // the next click retries cleanly.
      toast.error(
        "저장에 실패했습니다. 다시 시도해 주세요. " +
          "(Failed to save — please retry)",
      );
    } finally {
      setSubmitting(false);
    }
  }, [answers, submitting]);

  const goNext = useCallback(() => {
    if (!isStepValid && !isResultScreen) return;
    if (isLegalStep) {
      void handleSubmit();
      return;
    }
    setDirection(1);
    if (step < TOTAL_STEPS) {
      setStep((s) => s + 1);
      containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [step, isStepValid, isResultScreen, isLegalStep, handleSubmit]);

  const goBack = useCallback(() => {
    if (step > 0) {
      setDirection(-1);
      setStep((s) => s - 1);
      containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [step]);

  const [skipping, setSkipping] = useState(false);
  const handleSkip = useCallback(async () => {
    if (skipping) return;
    // 2026-05-17 wave 12 UX P2: "Skip for now" sits in the sticky header
    // at rgba opacity 0.5 — mid-onboarding mis-tap would permanently
    // mark the user's investor profile as "skipped" with no recovery.
    // Confirm step protects against that without blocking the deliberate
    // skip flow. window.confirm is fine here — this is a one-off click,
    // not a recurring surface (no design system promotion needed).
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        "다섯 문항을 건너뛰시겠습니까?\n" +
          "(Skip the five questions?)\n" +
          "건너뛰면 거울이 비교할 기준이 없습니다.",
      );
      if (!ok) return;
    }
    setSkipping(true);
    try {
      // Mark onboarding completed on the backend with empty answers,
      // otherwise the dashboard layout redirects us back to /onboarding.
      await apiFetch(API.profile.onboarding, {
        method: "POST",
        body: JSON.stringify({ answers: {} }),
      });
      await refresh();
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem("pivoxquant_onboarding_full_answers");
    } catch {
      // Fall through — still navigate so user isn't stuck if backend is down.
    } finally {
      router.replace("/mirror");
    }
  }, [router, refresh, skipping]);

  // Result screen CTA: refresh the user (onboarding_completed flips to true)
  // and go to the mirror. Done here, not in handleSubmit, so the auth guard
  // above does not redirect away before the user has read the screen.
  const handleFinish = useCallback(async () => {
    if (finishing) return;
    setFinishing(true);
    try {
      await refresh();
    } catch {
      // Fall through — /mirror re-fetches the user anyway.
    } finally {
      router.replace("/mirror");
    }
  }, [finishing, refresh, router]);

  // ── Keyboard shortcuts ───────────────────────────────────────────────────

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Enter" && isStepValid && !isResultScreen) {
        e.preventDefault();
        goNext();
      }
      if (e.key === "ArrowRight" && isStepValid && !isResultScreen) {
        e.preventDefault();
        goNext();
      }
      if (e.key === "ArrowLeft" && step > 0 && !isResultScreen) {
        e.preventDefault();
        goBack();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [goNext, goBack, isStepValid, step, isResultScreen]);

  // ── Loading / auth guard ─────────────────────────────────────────────────

  if (authLoading) {
    // Page-load skeleton — Vantablack ink surface matching the wizard
    // chrome. Mirrors top progress + question card so layout shift on
    // mount is minimal. Replaces the legacy Loader2 spinner.
    return (
      <div
        className="flex min-h-[100dvh] flex-col items-center px-6 pt-12"
        style={{ backgroundColor: "var(--pq-ink)" }}
        role="status"
        aria-live="polite"
        aria-label="Loading onboarding"
      >
        <div className="w-full max-w-md flex flex-col gap-4">
          <div className="pq-skeleton-dark h-1.5 w-full rounded-full" />
          <div className="pq-skeleton-dark mt-6 h-3 w-24 rounded" />
          <div className="pq-skeleton-dark h-8 w-3/4 rounded" />
          <div className="pq-skeleton-dark h-4 w-2/3 rounded" />
          <div className="pq-skeleton-dark mt-6 h-14 w-full rounded-sm" />
          <div className="pq-skeleton-dark h-14 w-full rounded-sm" />
          <div className="pq-skeleton-dark h-14 w-full rounded-sm" />
          <span className="sr-only">Loading onboarding…</span>
        </div>
      </div>
    );
  }

  if (!user) return null;

  // Already onboarded — don't flash the wizard while redirect runs
  if (user.onboarding_completed === true) return null;

  // ── Result screen ────────────────────────────────────────────────────────

  if (isResultScreen) {
    return (
      <div
        className="min-h-[100dvh]"
        style={{
          backgroundColor: "var(--pq-ink)",
          color: "var(--pq-ivory)",
        }}
      >
        <div className="mx-auto max-w-lg">
          <ResultScreen
            statements={declared}
            onContinue={handleFinish}
            loading={finishing}
          />
        </div>
      </div>
    );
  }

  // ── Wizard ───────────────────────────────────────────────────────────────

  const displayStep = step + 1;
  const category = isLegalStep ? "F" : (currentQuestion?.category ?? "A");

  return (
    <div
      className="flex min-h-[100dvh] flex-col"
      style={{
        backgroundColor: "var(--pq-ink)",
        color: "var(--pq-ivory)",
      }}
    >
      {/* Top bar */}
      <header
        className="sticky top-0 z-20 backdrop-blur-xl px-4 py-3 sm:px-6"
        style={{
          borderBottom: "1px solid var(--pq-border)",
          backgroundColor: "rgba(5,5,5,0.85)",
        }}
      >
        <div className="mx-auto max-w-lg">
          <div className="mb-3 flex items-center justify-between">
            <span
              className="text-base font-bold font-display"
              style={{
                color: "var(--pq-ivory)",
                letterSpacing: "var(--pq-track-wordmark)",
              }}
            >
              PivoxQuant
            </span>
            {/* P1-6 (2026-05-20 ux-flow fix): Skip was opacity-0.5 plain text
                — easy to miss, hurting first-run completion for users who
                want to explore before answering the questions. Bumped to a
                higher-contrast hairline-bordered affordance so it reads as a
                real, tappable escape hatch (44px touch target retained). */}
            <button
              type="button"
              onClick={handleSkip}
              disabled={skipping}
              className="text-xs font-semibold transition-colors disabled:opacity-50"
              style={{
                color: "rgba(var(--pq-ivory-rgb), 0.85)",
                border: "1px solid var(--pq-border)",
                borderRadius: "var(--pq-radius-cta, 2px)",
                padding: "8px 14px",
              }}
            >
              {skipping ? "Skipping…" : "Skip for now →"}
            </button>
          </div>
          <ProgressBar current={displayStep} total={TOTAL_STEPS} category={category} />
        </div>
      </header>

      {/* Content */}
      {/* 2026-05-18 v44.8 F-4 deferred Bug #10: pb-24 (96px) ensures last
          option of 6+ option multi-select clears the sticky footer (~80px
          tall). Without bottom padding, the scrollable container's last
          child sits flush against the footer top edge and the footer's
          backdrop-blur overlay obscures it. */}
      <main ref={containerRef} className="flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="mx-auto max-w-lg py-6 pb-24">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              custom={direction}
              variants={{
                enter: (d: number) => ({ x: d * 80, opacity: 0 }),
                center: { x: 0, opacity: 1 },
                exit: (d: number) => ({ x: d * -80, opacity: 0 }),
              }}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: PQ_DUR_BASE, ease: PQ_EASE }}
            >
              {isLegalStep ? (
                <LegalStep
                  answers={(answers.legal_confirmations ?? []) as string[]}
                  onToggle={handleLegalToggle}
                />
              ) : currentQuestion ? (
                <QuestionScreen
                  question={currentQuestion}
                  answer={answers[currentQuestion.id]}
                  onSingleSelect={handleSingleSelect}
                  onMultiToggle={handleMultiToggle}
                  onSliderChange={handleSliderChange}
                />
              ) : null}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Footer navigation */}
      <footer
        className="sticky bottom-0 z-20 backdrop-blur-xl px-4 py-4 sm:px-6"
        style={{
          borderTop: "1px solid var(--pq-border)",
          backgroundColor: "rgba(5,5,5,0.85)",
        }}
      >
        <div className="mx-auto flex max-w-lg items-center justify-between gap-4">
          {/* Back */}
          <button
            type="button"
            onClick={goBack}
            disabled={step === 0}
            className="flex items-center gap-1 px-5 py-2.5 text-sm font-semibold transition-all duration-200 disabled:opacity-30 disabled:hover:bg-transparent"
            style={{
              color: "rgba(var(--pq-ivory-rgb), 0.6)",
              borderRadius: "var(--pq-radius-cta)",
            }}
          >
            <ChevronLeft size={16} />
            Back
          </button>

          {/* Next */}
          <button
            type="button"
            onClick={goNext}
            disabled={!isStepValid}
            className="flex items-center gap-1 px-7 py-2.5 text-sm font-bold transition-all duration-300 active:scale-[0.97] disabled:cursor-not-allowed"
            style={{
              transitionTimingFunction: "var(--motion-easing-emphasized, cubic-bezier(0.16, 1, 0.3, 1))",
              borderRadius: "var(--pq-radius-cta)",
              backgroundColor: isStepValid ? "var(--pq-bronze)" : "rgba(var(--pq-ivory-rgb), 0.06)",
              color: isStepValid ? "var(--pq-ink)" : "rgba(var(--pq-ivory-rgb), 0.35)",
              boxShadow: isStepValid ? "0 6px 16px rgba(var(--pq-bronze-rgb),0.25)" : "none",
              border: isStepValid ? "none" : "1px solid var(--pq-border)",
            }}
          >
            {isLegalStep
              ? submitting
                ? <Loader2 size={16} className="animate-spin" />
                : "Save"
              : "Next"}
            {!(isLegalStep && submitting) && <ChevronRight size={16} />}
          </button>
        </div>
      </footer>
    </div>
  );
}

// ── Question screen wrapper ──────────────────────────────────────────────────

function QuestionScreen({
  question,
  answer,
  onSingleSelect,
  onMultiToggle,
  onSliderChange,
}: {
  question: OnboardingQuestion;
  answer: string | string[] | number | undefined;
  onSingleSelect: (qid: string, value: string) => void;
  onMultiToggle: (qid: string, value: string) => void;
  onSliderChange: (qid: string, value: number) => void;
}) {
  const catMeta = CATEGORIES[question.category];
  const { locale } = useLocale();
  const displayQuestion = locale === "ko" ? (question.question_kr || question.question) : question.question;
  const displayCatLabel = locale === "ko" ? (catMeta?.label_kr || catMeta?.label) : catMeta?.label;

  return (
    <div className="flex flex-col gap-5">
      {/* Category + question */}
      <div>
        {catMeta && (
          <div className="mb-2 flex items-center gap-2">
            <div
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: catMeta.color }}
            />
            <span
              className="text-xs font-semibold uppercase tracking-wider"
              style={{
                color: "var(--pq-bronze)",
                letterSpacing: "var(--pq-track-eyebrow)",
              }}
            >
              {displayCatLabel}
            </span>
          </div>
        )}
        <h2
          className="text-xl font-bold leading-tight sm:text-2xl font-display"
          style={{
            color: "var(--pq-ivory)",
            letterSpacing: "var(--pq-track-tight)",
          }}
        >
          {displayQuestion}
        </h2>
        {question.type === "multi" && (
          <p
            className="mt-1.5 text-sm"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
          >
            {locale === "ko" ? "해당하는 것을 모두 선택해 주세요." : "Select all that apply"}
          </p>
        )}
      </div>

      {/* Options */}
      {question.type === "single" && (
        <div className="flex flex-col gap-3">
          {question.options.map((opt) => (
            <OptionCard
              key={String(opt.value)}
              option={opt}
              selected={answer === String(opt.value)}
              onSelect={() => onSingleSelect(question.id, String(opt.value))}
            />
          ))}
        </div>
      )}

      {question.type === "multi" && (
        <div className="flex flex-col gap-3">
          {question.options.map((opt) => (
            <MultiOptionCard
              key={String(opt.value)}
              option={opt}
              selected={Array.isArray(answer) && answer.includes(String(opt.value))}
              onToggle={() => onMultiToggle(question.id, String(opt.value))}
            />
          ))}
        </div>
      )}

      {question.type === "slider" && (
        <SliderInput
          question={question}
          value={
            typeof answer === "number"
              ? answer
              : Math.round(((question.min ?? 1) + (question.max ?? 5)) / 2)
          }
          onChange={(v) => onSliderChange(question.id, v)}
        />
      )}
    </div>
  );
}
