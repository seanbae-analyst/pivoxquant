"use client";

/**
 * /onboarding on a phone (2026-10-09, matching the 멈춤 phone flow): the five
 * questions and the legal step are screens you swipe between, with a
 * segmented progress bar. Built on lib/use-swipe-pager (the same hooks
 * /pre-trade uses) — no second pager.
 *
 * Gate rules (the page's step validity is the only gate):
 *   - a forward swipe pages only from a step that is already answered, and
 *     never answers anything itself;
 *   - the legal step never pages forward by swipe — saving is the button's
 *     job, so its required confirmations cannot be skipped by a gesture;
 *   - back always works except from the first question;
 *   - nothing pages while the answers are being saved.
 * The result screen is not part of the pager (the page renders it on its
 * own, without these handlers), so it cannot be swiped back into a resubmit.
 * At md and up the hooks are inert and nothing here renders.
 */

import { useState, type RefObject } from "react";
import {
  type PagerDir,
  useSlideIn,
  useSwipePager,
} from "@/lib/use-swipe-pager";

/**
 * May the wizard be on `target` (the system forward gesture)? Every step
 * before it must be answered, and the legal step is never passed by a
 * history move — the result screen is reached only by saving.
 * `answered[i]` is the page's own validity check for step i.
 */
export function onboardingStepReachable(target: number, answered: boolean[]): boolean {
  if (target < 0 || target >= answered.length) return false;
  for (let i = 0; i < target; i++) {
    if (!answered[i]) return false;
  }
  return true;
}

/** Why the last forward swipe was refused, shown under the screen. */
export type OnboardingSwipeHint = "answer" | "legal" | "save";

export interface OnboardingPagerArgs {
  /** The element that slides (the step screen). */
  screenRef: RefObject<HTMLDivElement | null>;
  step: number;
  dir: PagerDir;
  /** The page's own validity check for the current step. */
  stepValid: boolean;
  isLegalStep: boolean;
  /** Saving in flight — no paging. */
  busy: boolean;
  goNext: () => void;
  goBack: () => void;
}

export function useOnboardingPager({
  screenRef,
  step,
  dir,
  stepValid,
  isLegalStep,
  busy,
  goNext,
  goBack,
}: OnboardingPagerArgs) {
  const [blockedAt, setBlockedAt] = useState<number | null>(null);
  // A new step starts without the last step's refusal (derived-state reset
  // during render, not an effect).
  const [shownStep, setShownStep] = useState(step);
  if (shownStep !== step) {
    setShownStep(step);
    setBlockedAt(null);
  }

  const swipe = useSwipePager(screenRef, {
    enabled: !busy,
    onNext: () => {
      if (isLegalStep || !stepValid) {
        setBlockedAt(step);
        return "blocked";
      }
      goNext();
      return "moved";
    },
    onPrev: () => {
      if (step === 0) return "blocked";
      goBack();
      return "moved";
    },
  });
  useSlideIn(screenRef, step, dir, { enabled: true, animateOnMount: false });

  let hint: OnboardingSwipeHint | null = null;
  if (blockedAt === step) {
    if (isLegalStep) hint = stepValid ? "save" : "legal";
    else if (!stepValid) hint = "answer";
  }
  return { swipe, hint };
}

const HINT_COPY: Record<OnboardingSwipeHint, { ko: string; en: string }> = {
  answer: {
    ko: "답을 하나 고르면 다음 문항으로 넘어갑니다.",
    en: "Pick an answer to move on.",
  },
  legal: {
    ko: "모든 항목을 확인해야 저장할 수 있습니다.",
    en: "Tick every confirmation to save.",
  },
  save: {
    ko: "아래 저장 버튼을 눌러야 저장됩니다.",
    en: "Press Save below to record your answers.",
  },
};

export function OnboardingSwipeHintLine({
  hint,
  ko,
}: {
  hint: OnboardingSwipeHint | null;
  ko: boolean;
}) {
  if (!hint) return null;
  return (
    <p
      role="status"
      aria-live="polite"
      className="mt-5 text-[13px] leading-snug text-[var(--pq-bronze)] md:hidden"
      data-testid="onboarding-swipe-hint"
    >
      {ko ? HINT_COPY[hint].ko : HINT_COPY[hint].en}
    </p>
  );
}

/**
 * Phone progress: one segment per step (five questions + legal). A segment
 * is filled once that step is answered, so going back shows what is kept.
 */
export function OnboardingPhoneProgress({
  step,
  questionCount,
  answered,
  ko,
}: {
  step: number;
  questionCount: number;
  /** answered[i] — step i passes the page's validity check. */
  answered: boolean[];
  ko: boolean;
}) {
  const onLegal = step >= questionCount;
  const answeredQuestions = answered.slice(0, questionCount).filter(Boolean).length;
  const label = onLegal
    ? ko ? "마지막 확인" : "Confirmations"
    : ko ? `문항 ${step + 1} / ${questionCount}` : `Question ${step + 1} / ${questionCount}`;
  return (
    <div className="md:hidden" data-testid="onboarding-phone-progress">
      <div className="flex items-center justify-between text-[13px] text-[var(--pq-ivory-dim)]">
        <span>{label}</span>
        <span>
          {ko ? "답" : "Answered"} {answeredQuestions} / {questionCount}
        </span>
      </div>
      <div
        className="mt-2 flex gap-1"
        role="progressbar"
        aria-label={ko ? "온보딩 진행" : "Onboarding progress"}
        aria-valuemin={1}
        aria-valuemax={answered.length}
        aria-valuenow={step + 1}
      >
        {answered.map((done, i) => (
          <span
            key={i}
            data-testid={`onboarding-seg-${i}`}
            data-state={done ? "done" : i === step ? "current" : "todo"}
            className={`h-[3px] flex-1 transition-colors ${
              done
                ? "bg-[var(--pq-bronze)]"
                : i === step
                  ? "bg-[var(--pq-ivory-mid)]"
                  : "bg-[var(--pq-ivory-line)]"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
