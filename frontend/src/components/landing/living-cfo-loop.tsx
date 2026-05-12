"use client";

/**
 * LivingCfoLoop — Weekly learning cycle visualization.
 * -----------------------------------------------------------------------
 * Onboarding → Weekly Pulse → Drift Detect → Re-classify → New Report → Feedback → (loop)
 * Radial layout on desktop, linear stack on mobile.
 */

import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import {
  Fingerprint,
  Activity,
  AlertTriangle,
  RefreshCcw,
  FileText,
  MessageSquare,
} from "lucide-react";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
};
const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

type Step = {
  n: number;
  label: string;
  en: string;
  ko: string;
  icon: typeof Fingerprint;
};

const STEPS: readonly Step[] = [
  {
    n: 1,
    label: "Onboarding",
    en: "Identity anchored (20Q)",
    ko: "20문항으로 투자 정체성 고정",
    icon: Fingerprint,
  },
  {
    n: 2,
    label: "Weekly Pulse",
    en: "Portfolio reviewed each Friday",
    ko: "매주 금요일 포트폴리오 점검",
    icon: Activity,
  },
  {
    n: 3,
    label: "Drift Detect",
    en: "Rolling window flags divergence",
    ko: "롤링 윈도우로 이탈 감지",
    icon: AlertTriangle,
  },
  {
    n: 4,
    label: "Re-classify",
    en: "Persona recalibrated if needed",
    ko: "필요 시 페르소나 재분류",
    icon: RefreshCcw,
  },
  {
    n: 5,
    label: "New Report",
    en: "Fresh artifact filed to dossier",
    ko: "새 Artifact 발행",
    icon: FileText,
  },
  {
    n: 6,
    label: "Feedback",
    en: "Your notes shape next cycle",
    ko: "당신의 피드백이 다음 사이클을 바꾼다",
    icon: MessageSquare,
  },
] as const;

export function LivingCfoLoop() {
  const reduce = useReducedMotion();

  return (
    <section
      id="pq-loop"
      className="relative py-24 md:py-36"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-10 inline-flex items-center gap-2.5"
        >
          <span
            aria-hidden
            className="h-px w-7"
            style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
          />
          <span
            className="font-serif text-[11px] uppercase"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            The Loop · Why It Gets Smarter
          </span>
        </motion.div>

        <motion.h2
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="pq-silver-matte font-serif mb-6"
          style={{
            fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
            lineHeight: 1.08,
            letterSpacing: "-0.02em",
            fontWeight: 500,
          }}
        >
          Six steps.
          <br />
          Every week. For years.
        </motion.h2>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="font-serif mb-16 max-w-xl"
          style={{
            fontSize: "clamp(15px, 1.3vw, 17px)",
            lineHeight: 1.65,
            color: "rgba(245, 240, 232, 0.65)",
          }}
        >
          처음 만난 CFO와 2년 뒤 CFO는 다르다. 매주 한 번, 조용히 당신을
          다시 배운다.
        </motion.p>

        <motion.ol
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {STEPS.map((s) => {
            const Icon = s.icon;
            return (
              <motion.li
                key={s.n}
                variants={fadeUp}
                className="relative overflow-hidden rounded-sm p-6 md:p-7"
                style={{
                  backgroundColor: "#0D0D0D",
                  border: "0.5px solid rgba(139,111,71,0.28)",
                  minHeight: 180,
                }}
              >
                <div className="mb-4 flex items-center justify-between">
                  <div
                    className="flex h-9 w-9 items-center justify-center rounded-sm"
                    style={{
                      border: "0.5px solid rgba(139,111,71,0.45)",
                      color: "var(--pq-bronze)",
                    }}
                    aria-hidden
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <span
                    className="font-mono tabular-nums text-[11px]"
                    style={{
                      letterSpacing: "0.22em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    STEP {String(s.n).padStart(2, "0")}
                  </span>
                </div>
                <h3
                  className="font-serif mb-2"
                  style={{
                    fontSize: "var(--pq-text-h5)",
                    lineHeight: 1.2,
                    color: "var(--pq-ivory)",
                    fontWeight: 500,
                  }}
                >
                  {s.label}
                </h3>
                <p
                  className="font-serif mb-2"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    lineHeight: 1.55,
                    color: "rgba(245,240,232,0.72)",
                  }}
                >
                  {s.en}
                </p>
                <p
                  className="font-serif italic"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "rgba(139,111,71,0.75)",
                  }}
                >
                  {s.ko}
                </p>
              </motion.li>
            );
          })}
        </motion.ol>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mt-16 font-serif italic text-center"
          style={{
            fontSize: "var(--pq-text-body)",
            color: "rgba(139,111,71,0.85)",
            letterSpacing: "0.01em",
          }}
        >
          — Onboarding → Pulse → Drift → Re-classify → Report → Feedback →
          Pulse …
        </motion.p>
      </div>
    </section>
  );
}

export default LivingCfoLoop;
