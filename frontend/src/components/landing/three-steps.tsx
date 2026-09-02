"use client";

/**
 * ThreeSteps — 멈춤 · 기록 · 거울.
 * ----------------------------------------------------------------------
 * Replaces <MarqueeLogos/> in the slot directly under the Hero.
 *
 * ⚠️ Why the marquee is gone (2026-09-02)
 * The strip that lived here said "Built on the methodology of" and scrolled
 * twelve wordmarks: DUPONT IDENTITY · HRP PORTFOLIO · LEDOIT-WOLF SHRINKAGE ·
 * BLACK-LITTERMAN · FAMA-FRENCH 5 · GKYZ VOLATILITY · STATISTICAL ARBITRAGE ·
 * TS-MOMENTUM · CONDITIONAL VAR · MEAN REVERSION · DISPOSITION EFFECT ·
 * ANCHORING BIAS. Its own source comment asserted "these are the actual models
 * PivoxQuant runs".
 *
 * Measured 2026-09-02 with `grep -ril <term> services/ models/ routes/`:
 * eleven of the twelve return zero files. The only two hits were
 * `services/us_stocks_data.json` — the string "DuPont de Nemours" (a ticker
 * name) and the symbol "CVAR". `services/quant/` was deleted wholesale on
 * 2026-08-31. The real count of implemented models is zero.
 *
 * That made the most prominent trust element on the public landing a false
 * statement of fact about the service (표시광고법 §3 부당표시·기만적 표시).
 * Fabricated credibility is also the exact opposite of the product's premise:
 * the pitch is that we do NOT score you and do NOT know better than you.
 *
 * What replaces it is the loop that actually ships — three routes, three
 * verbs. Everything below is checkable against the running app:
 *   멈춤  → /pre-trade   7 questions before the order (routes/pre_trade.py)
 *   기록  → /journal     the record + 5 behavior mirrors (services/behavior/)
 *   거울  → /mirror      declared persona vs observed persona over 30 days
 *
 * None of the three calls a price feed. `services/behavior/*.py` imports no
 * quote service — `averaging_down_mirror.py` says so in its own docstring.
 * Do not add a claim here that a route does not do.
 *
 * Palette: Vantablack + Bronze + Ivory only. No italic (CEO 2026-06-15).
 */

import { motion, useReducedMotion } from "motion/react";

import { Eyebrow } from "./eyebrow";
import { fadeUp, stagger } from "@/lib/motion";

type Step = {
  /** Ledger numeral — editorial, not a progress indicator. */
  numeral: string;
  /** Korean verb — the section's spine. */
  verb: string;
  /** The route this step is, so the claim stays checkable. */
  route: string;
  /** What the user does. Second person, present tense. */
  body: string;
  /** The honest limit of the step — what it deliberately does NOT do. */
  limit: string;
};

const STEPS: readonly Step[] = [
  {
    numeral: "I",
    verb: "멈춤",
    route: "/pre-trade",
    body: "매수 버튼을 누르기 전에 일곱 개의 질문에 답합니다. 왜 지금인지, 무엇이 틀리면 파는지, 이 돈을 잃어도 되는지. 답을 적는 데 걸리는 시간이 유일한 마찰입니다.",
    limit: "종목을 골라주지 않습니다.",
  },
  {
    numeral: "II",
    verb: "기록",
    route: "/journal",
    body: "산 것과 사려다 만 것이 같은 자리에 남습니다. 보유기간, 회전율, 집중도, 물타기, 손익 처분 — 다섯 가지 습관이 당신의 기록에서 그대로 계산됩니다.",
    limit: "점수를 매기지 않습니다.",
  },
  {
    numeral: "III",
    verb: "거울",
    route: "/mirror",
    body: "온보딩에서 스스로 선언한 투자자와, 최근 30일 거래가 말해주는 투자자를 나란히 놓습니다. 아홉 개 축에서 둘이 갈라지는 지점이 이 도구의 전부입니다.",
    limit: "어느 쪽이 옳다고 말하지 않습니다.",
  },
] as const;

export default function ThreeSteps() {
  const reduce = useReducedMotion();

  return (
    <section
      id="how-it-works"
      aria-labelledby="pq-steps-heading"
      className="relative py-24 md:py-32 lg:py-40"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-14 max-w-2xl md:mb-20"
        >
          <Eyebrow className="mb-6">The loop</Eyebrow>
          <h2
            id="pq-steps-heading"
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              marginBottom: 24,
            }}
          >
            화면은 셋뿐입니다.
          </h2>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-deck)",
              lineHeight: 1.65,
              color: "rgba(245,240,232,0.65)",
              maxWidth: 560,
            }}
          >
            리포트를 받아보는 서비스가 아닙니다. 당신이 남긴 기록이 유일한
            재료이고, 도구가 하는 일은 그것을 나중에 다시 보여주는 것뿐입니다.
          </p>
        </motion.div>

        <motion.ol
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-px md:grid-cols-3"
          style={{ backgroundColor: "rgba(184,149,106,0.18)" }}
        >
          {STEPS.map((s) => (
            <motion.li
              key={s.verb}
              variants={fadeUp}
              className="flex flex-col p-7 md:p-8 lg:p-9"
              style={{ backgroundColor: "#050505" }}
            >
              <div className="mb-7 flex items-baseline gap-3">
                <span
                  className="font-serif"
                  style={{
                    color: "var(--pq-bronze)",
                    fontSize: "var(--pq-text-caption)",
                    letterSpacing: "0.22em",
                  }}
                >
                  {s.numeral}
                </span>
                <h3
                  className="font-serif"
                  style={{
                    color: "var(--pq-ivory)",
                    fontSize: "clamp(1.5rem, 2.6vw, 1.9rem)",
                    fontWeight: 500,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {s.verb}
                </h3>
                {/* The route is the receipt: every claim in this card is
                    checkable by opening that path in the app. */}
                <span
                  className="ml-auto font-mono"
                  style={{
                    color: "rgba(245,240,232,0.34)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.04em",
                  }}
                >
                  {s.route}
                </span>
              </div>

              <p
                className="mb-7 flex-1 font-serif"
                style={{
                  color: "rgba(245,240,232,0.74)",
                  fontSize: "var(--pq-text-body-sm)",
                  lineHeight: 1.7,
                }}
              >
                {s.body}
              </p>

              {/* Stating the limit is the point, not a disclaimer bolt-on:
                  the product's only defensible claim is what it refuses to do. */}
              <p
                className="font-serif"
                style={{
                  color: "rgba(245,240,232,0.42)",
                  fontSize: "var(--pq-text-eyebrow)",
                  lineHeight: 1.6,
                  letterSpacing: "0.02em",
                  borderTop: "0.5pt solid var(--pq-ivory-line)",
                  paddingTop: 14,
                }}
              >
                {s.limit}
              </p>
            </motion.li>
          ))}
        </motion.ol>
      </div>
    </section>
  );
}
