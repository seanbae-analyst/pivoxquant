"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { Check, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import {
  WIZARD_QUESTIONS,
  LEGAL_QUESTION,
  CATEGORIES,
  INVESTOR_TYPES,
  PROFILE_HIGHLIGHTS,
} from "@/data/onboarding-questions";
import type { OnboardingOption, OnboardingQuestion } from "@/data/onboarding-questions";

// ── Constants ────────────────────────────────────────────────────────────────

const STORAGE_KEY = "pivoxquant_onboarding_answers";
const TOTAL_STEPS = WIZARD_QUESTIONS.length + 1; // 19 wizard + 1 legal
const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

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

  return (
    <div className="w-full">
      {/* Header row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {catMeta?.label ?? category}
          </span>
        </div>
        <span className="text-xs tabular-nums font-medium text-slate-500">
          {current} of {total}
        </span>
      </div>

      {/* Bar */}
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: "linear-gradient(90deg, #8b5cf6, #3b82f6)" }}
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
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

  return (
    <motion.button
      type="button"
      onClick={onSelect}
      whileTap={{ scale: 0.98 }}
      className={`
        group relative flex w-full items-center gap-3 rounded-2xl border-2 px-5 py-4
        text-left transition-all duration-300
        ${
          selected
            ? "border-[#8b5cf6] bg-[#8b5cf6]/[0.04] shadow-[0_0_0_1px_rgba(139,92,246,0.1)]"
            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
        }
      `}
      style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
    >
      {/* Selection indicator */}
      <div
        className={`
          flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all duration-200
          ${
            selected
              ? "border-[#8b5cf6] bg-[#8b5cf6]"
              : "border-slate-300 bg-white group-hover:border-slate-400"
          }
        `}
      >
        {selected && <Check size={12} strokeWidth={3} className="text-white" />}
      </div>

      {/* Icon */}
      {icon && <span className="text-lg leading-none">{icon}</span>}

      {/* Text */}
      <span
        className={`text-[15px] leading-snug font-medium ${
          selected ? "text-slate-900" : "text-slate-600 group-hover:text-slate-800"
        }`}
      >
        {option.label}
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
  return (
    <motion.button
      type="button"
      onClick={onToggle}
      whileTap={{ scale: 0.98 }}
      className={`
        group relative flex w-full items-center gap-3 rounded-2xl border-2 px-5 py-4
        text-left transition-all duration-300
        ${
          selected
            ? "border-[#8b5cf6] bg-[#8b5cf6]/[0.04]"
            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
        }
      `}
      style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
    >
      {/* Checkbox */}
      <div
        className={`
          flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all duration-200
          ${
            selected
              ? "border-[#8b5cf6] bg-[#8b5cf6]"
              : "border-slate-300 bg-white group-hover:border-slate-400"
          }
        `}
      >
        {selected && <Check size={12} strokeWidth={3} className="text-white" />}
      </div>

      {/* Text */}
      <span
        className={`text-[15px] leading-snug font-medium ${
          selected ? "text-slate-900" : "text-slate-600 group-hover:text-slate-800"
        }`}
      >
        {option.label}
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

  return (
    <div className="flex flex-col gap-6">
      {/* Current value display */}
      <div className="text-center">
        <div className="mb-1 text-4xl font-bold text-[#8b5cf6]">{value}</div>
        <div className="text-sm font-medium text-slate-600">
          {currentOption?.label ?? ""}
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
          className="slider-input w-full"
        />

        {/* Labels below */}
        <div className="mt-3 flex items-start justify-between">
          <span className="max-w-[120px] text-xs text-slate-400 leading-tight">
            {question.min_label}
          </span>
          <span className="max-w-[120px] text-right text-xs text-slate-400 leading-tight">
            {question.max_label}
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
              flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-all duration-200
              ${
                Number(opt.value) === value
                  ? "bg-[#8b5cf6] text-white shadow-lg shadow-purple-200/50"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
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
  return (
    <div className="flex flex-col gap-4">
      <div className="mb-2">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">{"\u{1F6E1}\u{FE0F}"}</span>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Legal & Compliance
          </span>
        </div>
        <h2 className="text-xl font-bold text-slate-900 leading-tight">
          {LEGAL_QUESTION.question}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          All confirmations are required to proceed.
        </p>
      </div>

      {LEGAL_QUESTION.options.map((opt) => {
        const checked = answers.includes(String(opt.value));
        return (
          <motion.button
            key={String(opt.value)}
            type="button"
            onClick={() => onToggle(String(opt.value))}
            whileTap={{ scale: 0.98 }}
            className={`
              flex items-start gap-4 rounded-2xl border-2 px-5 py-4 text-left transition-all duration-300
              ${
                checked
                  ? "border-[#10b981] bg-[#10b981]/[0.04]"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }
            `}
            style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
          >
            <div
              className={`
                mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all duration-200
                ${checked ? "border-[#10b981] bg-[#10b981]" : "border-slate-300 bg-white"}
              `}
            >
              {checked && <Check size={12} strokeWidth={3} className="text-white" />}
            </div>
            <span className={`text-[14px] leading-relaxed ${checked ? "text-slate-800 font-medium" : "text-slate-600"}`}>
              {opt.label}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}

/** Result screen after completing all questions. */
function ResultScreen({
  investorType,
  onContinue,
  loading,
}: {
  investorType: string;
  onContinue: () => void;
  loading: boolean;
}) {
  const typeData = INVESTOR_TYPES[investorType];
  const highlights = PROFILE_HIGHLIGHTS[investorType];

  if (!typeData || !highlights) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col items-center px-4 py-8"
    >
      {/* Badge */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.2, ...SPRING }}
        className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-[#8b5cf6] to-[#3b82f6] shadow-xl shadow-purple-200/40"
      >
        <span className="text-3xl">{"\u{1F3AF}"}</span>
      </motion.div>

      {/* Title */}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="text-sm font-semibold uppercase tracking-wider text-slate-400"
      >
        Your Investor Profile
      </motion.p>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="mt-2 text-center text-3xl font-bold tracking-tight"
      >
        <span className="gradient-text">{typeData.label}</span>
      </motion.h1>

      {/* Tagline */}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="mt-3 max-w-sm text-center text-[15px] leading-relaxed text-slate-500"
      >
        {highlights.tagline}
      </motion.p>

      {/* Features */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.5 }}
        className="mt-8 w-full max-w-sm space-y-3"
      >
        {highlights.features.map((feat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.7 + i * 0.1 }}
            className="flex items-center gap-3 rounded-xl bg-[#10b981]/[0.06] px-4 py-3"
          >
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#10b981]">
              <Check size={14} strokeWidth={3} className="text-white" />
            </div>
            <span className="text-sm font-medium text-slate-700">{feat}</span>
          </motion.div>
        ))}
      </motion.div>

      {/* CTA */}
      <motion.button
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
        onClick={onContinue}
        disabled={loading}
        className="mt-10 flex w-full max-w-sm items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#8b5cf6] to-[#3b82f6] px-8 py-4 text-base font-bold text-white shadow-lg shadow-purple-200/40 transition-all duration-300 hover:shadow-xl hover:shadow-purple-200/50 active:scale-[0.98] disabled:opacity-60"
        style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
      >
        {loading ? (
          <Loader2 size={20} className="animate-spin" />
        ) : (
          <>
            Go to Dashboard
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

  // Steps: 0..18 = wizard questions, 19 = legal, 20 = result screen
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | string[] | number>>(loadSavedAnswers);
  const [direction, setDirection] = useState(1); // 1 = forward, -1 = back
  const [submitting, setSubmitting] = useState(false);
  const [investorType, setInvestorType] = useState<string>("steady_accumulator");

  const containerRef = useRef<HTMLDivElement>(null);

  // Redirect if not logged in, or if onboarding is already complete
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
      return;
    }
    if (!authLoading && user && user.onboarding_completed === true) {
      router.replace("/home");
    }
  }, [authLoading, user, router]);

  // Restore saved step from answers
  useEffect(() => {
    const saved = loadSavedAnswers();
    if (Object.keys(saved).length > 0) {
      setAnswers(saved);
    }
  }, []);

  // Save answers to localStorage whenever they change
  useEffect(() => {
    saveAnswers(answers);
  }, [answers]);

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

  const goNext = useCallback(() => {
    if (!isStepValid && !isResultScreen) return;
    setDirection(1);
    if (step < TOTAL_STEPS) {
      setStep((s) => s + 1);
      containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [step, isStepValid, isResultScreen]);

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
    } catch {
      // Fall through — still navigate so user isn't stuck if backend is down.
    } finally {
      router.replace("/home");
    }
  }, [router, refresh, skipping]);

  // Determine investor type when reaching result screen
  useEffect(() => {
    if (step === TOTAL_STEPS) {
      const type = classifyInvestorTypeLocal(answers);
      setInvestorType(type);
    }
  }, [step, answers]);

  // Submit answers to backend
  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    try {
      // Store full 20 answers in localStorage
      localStorage.setItem("pivoxquant_onboarding_full_answers", JSON.stringify(answers));

      // POST the answers to the onboarding endpoint
      await apiFetch(API.profile.onboarding, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });

      // Refresh user (onboarding_completed should flip to true)
      await refresh();

      // Clean up stored progress
      localStorage.removeItem(STORAGE_KEY);

      router.replace("/home");
    } catch {
      // Don't redirect — show error and let user retry
      alert("Failed to save profile. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }, [answers, refresh, router]);

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
    return (
      <div className="flex min-h-[100dvh] items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[#8b5cf6]" />
      </div>
    );
  }

  if (!user) return null;

  // Already onboarded — don't flash the wizard while redirect runs
  if (user.onboarding_completed === true) return null;

  // ── Result screen ────────────────────────────────────────────────────────

  if (isResultScreen) {
    return (
      <div className="min-h-[100dvh] bg-white">
        <div className="mx-auto max-w-lg">
          <ResultScreen
            investorType={investorType}
            onContinue={handleSubmit}
            loading={submitting}
          />
        </div>
      </div>
    );
  }

  // ── Wizard ───────────────────────────────────────────────────────────────

  const displayStep = step + 1;
  const category = isLegalStep ? "F" : (currentQuestion?.category ?? "A");

  return (
    <div className="flex min-h-[100dvh] flex-col bg-white">
      {/* Top bar */}
      <header className="sticky top-0 z-20 border-b border-slate-100 bg-white/80 backdrop-blur-xl px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-lg">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-base font-bold text-slate-900">PivoxQuant</span>
            <button
              type="button"
              onClick={handleSkip}
              disabled={skipping}
              className="text-xs font-medium text-slate-400 transition-colors hover:text-slate-600 disabled:opacity-50"
            >
              {skipping ? "Skipping…" : "Skip for now"}
            </button>
          </div>
          <ProgressBar current={displayStep} total={TOTAL_STEPS} category={category} />
        </div>
      </header>

      {/* Content */}
      <main ref={containerRef} className="flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="mx-auto max-w-lg py-6">
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
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
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
      <footer className="sticky bottom-0 z-20 border-t border-slate-100 bg-white/80 backdrop-blur-xl px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-4">
          {/* Back */}
          <button
            type="button"
            onClick={goBack}
            disabled={step === 0}
            className="flex items-center gap-1 rounded-full px-5 py-2.5 text-sm font-semibold text-slate-500 transition-all duration-200 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent"
          >
            <ChevronLeft size={16} />
            Back
          </button>

          {/* Next */}
          <button
            type="button"
            onClick={goNext}
            disabled={!isStepValid}
            className={`
              flex items-center gap-1 rounded-full px-7 py-2.5 text-sm font-bold transition-all duration-300
              ${
                isStepValid
                  ? "bg-[#8b5cf6] text-white shadow-md shadow-purple-200/40 hover:bg-[#7c3aed] hover:shadow-lg active:scale-[0.97]"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
              }
            `}
            style={{ transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)" }}
          >
            {isLegalStep ? "See Results" : "Next"}
            <ChevronRight size={16} />
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
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {catMeta.label}
            </span>
          </div>
        )}
        <h2 className="text-xl font-bold text-slate-900 leading-tight sm:text-2xl">
          {question.question}
        </h2>
        {question.type === "multi" && (
          <p className="mt-1.5 text-sm text-slate-500">Select all that apply</p>
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
          value={typeof answer === "number" ? answer : (question.min ?? 1)}
          onChange={(v) => onSliderChange(question.id, v)}
        />
      )}
    </div>
  );
}

// ── Local investor type classification (simplified frontend version) ─────────

function classifyInvestorTypeLocal(answers: Record<string, string | string[] | number>): string {
  // Simplified scoring to determine type on the frontend.
  // The real scoring happens server-side; this is for the result preview.

  let riskRaw = 0;
  let activityRaw = 0;

  // Risk from scenario questions
  const dropScores: Record<string, number> = { sell_all: 1, sell_half: 3, hold: 6, buy_some: 8, buy_heavy: 10 };
  const crashScores: Record<string, number> = { cut_loss: 2, trim: 4, hold: 6, avg_down: 8, double_down: 10 };
  const relativeScores: Record<string, number> = { too_much: 2, acceptable: 5, opportunistic: 8, regret_upside: 10 };
  const coinScores: Record<string, number> = { never: 1, maybe_small: 4, yes_once: 7, yes_repeat: 10 };

  riskRaw += dropScores[String(answers.scenario_portfolio_drop)] ?? 5;
  riskRaw += crashScores[String(answers.scenario_single_stock_crash)] ?? 5;
  riskRaw += relativeScores[String(answers.scenario_market_crash_relative)] ?? 5;
  riskRaw += coinScores[String(answers.loss_aversion_coinflip)] ?? 5;

  // Leverage
  const levMap: Record<string, number> = { never: 0, etf_only: 2, light: 5, moderate: 8, full: 10 };
  const leverageScore = levMap[String(answers.leverage_appetite)] ?? 0;
  riskRaw += leverageScore;

  // Concentration
  const concMap: Record<string, number> = { ultra_focused: 10, focused: 7, moderate: 5, diversified: 3, broad: 1 };
  riskRaw += (concMap[String(answers.concentration_preference)] ?? 5) * 0.5;

  // Activity
  const freqMap: Record<string, number> = { rare: 1, few: 3, moderate: 5, frequent: 8, daily: 10 };
  const holdMap: Record<string, number> = { intraday: 10, days: 8, weeks: 5, months: 3, years: 1 };
  const rebalMap: Record<string, number> = { auto_daily: 9, weekly: 7, biweekly: 5, monthly: 3, quarterly: 1 };
  activityRaw += freqMap[String(answers.trading_frequency)] ?? 3;
  activityRaw += holdMap[String(answers.holding_period)] ?? 3;
  activityRaw += rebalMap[String(answers.rebalance_preference)] ?? 3;

  const riskNorm = Math.min(riskRaw / 5.5, 10);
  const activityNorm = Math.min(activityRaw / 3.0, 10);

  // Return ambition
  const retMap: Record<string, number> = { lt5: 1, "5to10": 3, "10to20": 6, "20to40": 8, "40plus": 10 };
  const rvsMap: Record<string, number> = { ultra_steady: 1, mostly_steady: 4, volatile_mid: 7, volatile_high: 10 };
  const minRetMap: Record<string, number> = { positive: 1, beat_bank: 3, beat_spy: 6, beat_20: 9 };
  let returnRaw = 0;
  returnRaw += retMap[String(answers.expected_annual_return)] ?? 5;
  returnRaw += rvsMap[String(answers.return_vs_stability)] ?? 4;
  returnRaw += minRetMap[String(answers.min_acceptable_return)] ?? 4;
  const returnNorm = Math.min(returnRaw / 3.0, 10);

  // Experience
  const expMap: Record<string, number> = { none: 0, lt1: 2, "1to3": 5, "3to5": 7, "5plus": 10 };
  const experienceNorm = Math.min((expMap[String(answers.experience_years)] ?? 3) / 1.0, 10);

  // Knowledge
  const concepts = (answers.knowledge_concepts ?? []) as string[];
  const conceptScores: Record<string, number> = {
    pe_ratio: 1, market_cap: 1, short_selling: 2, candlestick: 2,
    rsi_macd: 2, options_greeks: 3, beta_alpha: 2, kelly_criterion: 3,
  };
  let knowledgeRaw = concepts.reduce((sum, c) => sum + (conceptScores[c] ?? 0), 0);
  knowledgeRaw = Math.min(knowledgeRaw, 10);
  const selfRating = typeof answers.knowledge_self_rating === "number" ? answers.knowledge_self_rating : 3;
  const knowledgeScore = Math.min(Math.round((knowledgeRaw + selfRating * 2) / 2), 10);

  // Weighted distance classification (same as Python)
  const typeCentroids: Record<string, number[]> = {
    passive_index_hugger: [2.0, 1.0, 2.0, 2.0, 2.0, 0.0],
    steady_accumulator: [3.5, 2.5, 4.0, 3.0, 3.5, 0.0],
    value_hunter: [4.5, 3.0, 5.5, 6.0, 6.0, 1.0],
    risk_managed_growth: [5.0, 5.0, 6.0, 4.5, 5.0, 1.5],
    swing_trader: [6.0, 6.5, 6.5, 5.0, 6.0, 3.0],
    momentum_rider: [7.5, 7.5, 8.0, 5.5, 5.5, 6.0],
    macro_rotator: [5.0, 5.0, 6.0, 7.5, 8.0, 3.0],
    aggressive_scalper: [9.5, 9.5, 9.5, 7.0, 7.0, 8.0],
  };
  const dimWeights = [2.5, 2.0, 1.5, 1.0, 1.0, 1.5];
  const userVector = [riskNorm, activityNorm, returnNorm, experienceNorm, knowledgeScore, leverageScore];

  let bestType = "steady_accumulator";
  let bestDist = Infinity;

  for (const [typeName, centroid] of Object.entries(typeCentroids)) {
    let dist = 0;
    for (let i = 0; i < 6; i++) {
      dist += dimWeights[i] * Math.pow(userVector[i] - centroid[i], 2);
    }
    if (dist < bestDist) {
      bestDist = dist;
      bestType = typeName;
    }
  }

  // Override rules
  const holdVal = String(answers.holding_period ?? "weeks");
  const freqVal = String(answers.trading_frequency ?? "moderate");
  const tradingStyle =
    holdVal === "intraday" || freqVal === "daily"
      ? activityNorm >= 8 ? "scalp" : "day"
      : holdVal === "days" || holdVal === "weeks" || freqVal === "moderate" || freqVal === "frequent"
        ? "swing"
        : holdVal === "months"
          ? "position"
          : "buy_and_hold";

  if (tradingStyle === "scalp" && activityNorm >= 8.5) bestType = "aggressive_scalper";
  if (riskNorm <= 2 && activityNorm <= 2) bestType = "passive_index_hugger";
  if (knowledgeScore >= 8 && experienceNorm >= 7 && activityNorm >= 4 && activityNorm <= 6)
    bestType = "macro_rotator";
  if (bestType === "aggressive_scalper" && tradingStyle !== "scalp") {
    if (activityNorm >= 6 && riskNorm >= 6) bestType = "momentum_rider";
  }

  return bestType;
}
