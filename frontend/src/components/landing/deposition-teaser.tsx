"use client";

/**
 * DepositionTeaser — "Pre-Trade Checklist" signature ritual.
 * -----------------------------------------------------------------------
 * Legal-safe framing: "Pre-Trade Checklist" (NOT "Deposition" in user-facing UI).
 * Seven gates before every trade. Not advice — a reflection tool.
 *
 * Layout: courtroom-ledger mockup on left, question list on right.
 * Palette: Vantablack + Ivory + Bronze. No violet.
 */

import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { Gavel } from "lucide-react";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] },
  },
};

const QUESTIONS: readonly { n: number; q_en: string; q_ko: string }[] = [
  {
    n: 1,
    q_en: "What is your thesis in one sentence?",
    q_ko: "한 문장으로 이 포지션 진입 논리를 말해보라.",
  },
  {
    n: 2,
    q_en: "What would prove you wrong?",
    q_ko: "어떤 사실이 확인되면 당신이 틀린 것인가?",
  },
  {
    n: 3,
    q_en: "How does this fit your persona allocation?",
    q_ko: "현재 페르소나 배분에 이 포지션이 부합하는가?",
  },
  {
    n: 4,
    q_en: "Is this inside your drift band?",
    q_ko: "당신의 Drift 허용 범위 안에 있는가?",
  },
  {
    n: 5,
    q_en: "Size: is this a normal position for you?",
    q_ko: "평소 크기인가? 이례적으로 크다면 왜인가?",
  },
  {
    n: 6,
    q_en: "Have you seen a similar setup before — and what happened?",
    q_ko: "비슷한 국면에서 당신은 어떻게 행동했고 결과는?",
  },
  {
    n: 7,
    q_en: "If it drops 20% tomorrow — are you adding or cutting?",
    q_ko: "내일 -20% 라면 더 담는가, 잘라내는가?",
  },
] as const;

export function DepositionTeaser() {
  const reduce = useReducedMotion();

  return (
    <section
      id="pq-deposition"
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
            Signature · Pre-Trade Checklist
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
          Seven questions.
          <br />
          Before every trade.
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
          진입 결정 앞에 서는 7개의 관문. 당신을 변호할 기회가 아니라,
          당신의 논리를 스스로 검증할 기회다. 이것은 조언이 아니라 규율이다.
        </motion.p>

        <div className="grid grid-cols-1 gap-10 md:grid-cols-[minmax(0,0.95fr)_minmax(0,1fr)] md:gap-14 items-start">
          {/* LEFT: Courtroom-ledger mockup */}
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUp}
            className="relative rounded-sm p-8 md:p-10"
            style={{
              backgroundColor: "#F5F0E8",
              color: "#050505",
              boxShadow:
                "0 30px 80px -20px rgba(0,0,0,0.6), 0 0 0 0.5px rgba(139,111,71,0.25)",
              aspectRatio: "3/4",
              minHeight: 360,
            }}
          >
            <div className="flex items-start justify-between mb-7">
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <Gavel
                    className="h-3.5 w-3.5"
                    style={{ color: "rgba(139,111,71,0.8)" }}
                    aria-hidden
                  />
                  <span
                    className="font-mono text-[9px] uppercase tabular-nums"
                    style={{
                      letterSpacing: "0.22em",
                      color: "rgba(139,111,71,0.8)",
                    }}
                  >
                    Pre-Trade Checklist
                  </span>
                </div>
                <h3
                  className="font-serif"
                  style={{
                    fontSize: "var(--pq-text-quote)",
                    lineHeight: 1.15,
                    letterSpacing: "-0.01em",
                    fontWeight: 500,
                  }}
                >
                  Record of Reasoning
                </h3>
                <p
                  className="mt-1 font-serif italic"
                  style={{ fontSize: "var(--pq-text-eyebrow)", color: "rgba(10,10,10,0.55)" }}
                >
                  Counterparty · Yourself
                </p>
              </div>
              <div
                className="text-right font-mono tabular-nums"
                style={{ fontSize: "var(--pq-text-eyebrow)", color: "rgba(10,10,10,0.55)" }}
              >
                <div>DOCKET · PQ-0074</div>
                <div>SESSION · 09:42 KST</div>
              </div>
            </div>

            <div
              className="mb-6 h-px"
              style={{ backgroundColor: "rgba(10,10,10,0.15)" }}
            />

            <div className="space-y-3">
              {QUESTIONS.slice(0, 4).map((q) => (
                <div
                  key={q.n}
                  className="grid grid-cols-[auto_minmax(0,1fr)] gap-3"
                >
                  <span
                    className="font-mono text-[10px] tabular-nums"
                    style={{
                      color: "rgba(139,111,71,0.85)",
                      letterSpacing: "0.1em",
                      paddingTop: 2,
                    }}
                  >
                    {String(q.n).padStart(2, "0")}
                  </span>
                  <div>
                    <p
                      className="font-serif"
                      style={{ fontSize: "var(--pq-text-body)", lineHeight: 1.45 }}
                    >
                      {q.q_en}
                    </p>
                    <div
                      className="mt-2 h-px"
                      style={{
                        backgroundColor: "rgba(10,10,10,0.12)",
                        width: "82%",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <p
              className="mt-8 font-serif italic"
              style={{ fontSize: "var(--pq-text-eyebrow)", color: "rgba(10,10,10,0.45)" }}
            >
              Not investment advice. A reflection tool, logged to your
              compounding memory.
            </p>
          </motion.div>

          {/* RIGHT: full 7-question list */}
          <motion.ol
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUp}
            className="space-y-5"
          >
            {QUESTIONS.map((q) => (
              <li
                key={q.n}
                className="grid grid-cols-[auto_minmax(0,1fr)] gap-5 border-t pt-5"
                style={{ borderColor: "var(--pq-border)" }}
              >
                <span
                  className="font-mono text-[11px] tabular-nums"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  {String(q.n).padStart(2, "0")}
                </span>
                <div>
                  <p
                    className="font-serif mb-1"
                    style={{
                      fontSize: "var(--pq-text-lead)",
                      lineHeight: 1.5,
                      color: "var(--pq-ivory)",
                    }}
                  >
                    {q.q_en}
                  </p>
                  <p
                    className="font-serif italic"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      lineHeight: 1.5,
                      color: "rgba(139,111,71,0.75)",
                    }}
                  >
                    {q.q_ko}
                  </p>
                </div>
              </li>
            ))}
          </motion.ol>
        </div>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mt-12 font-serif italic"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-muted)",
            borderTop: "0.5px solid var(--pq-border)",
            paddingTop: 16,
          }}
        >
          <span style={{ color: "rgba(139, 111, 71, 0.9)" }}>— </span>
          Pre-Trade Checklist is a reflection tool. It does not constitute
          investment advice or a recommendation to buy or sell any security.
        </motion.p>
      </div>
    </section>
  );
}

export default DepositionTeaser;
