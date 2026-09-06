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
import { useT } from "@/lib/locale";

type Step = {
  /** Ledger numeral — editorial, not a progress indicator. */
  numeral: string;
  /** i18n key prefix under `landing.steps` (s1/s2/s3). */
  key: string;
  /** The route this step is, so the claim stays checkable. */
  route: string;
};

// Copy lives in messages/{ko,en}.json under `landing.steps` — the rest of the
// landing reads through useT() and this section must too. It was hardcoded
// Korean when first written (2026-09-02), which rendered a half-Korean page for
// anyone on the en locale.
const STEPS: readonly Step[] = [
  { numeral: "I", key: "s1", route: "/pre-trade" },
  { numeral: "II", key: "s2", route: "/journal" },
  { numeral: "III", key: "s3", route: "/mirror" },
] as const;

export default function ThreeSteps() {
  const t = useT();
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
          <Eyebrow className="mb-6">{t("landing.steps.eyebrow")}</Eyebrow>
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
            {t("landing.steps.heading")}
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
            {t("landing.steps.deck")}
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
              key={s.key}
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
                  {t(`landing.steps.${s.key}verb`)}
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
                {t(`landing.steps.${s.key}body`)}
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
                {t(`landing.steps.${s.key}limit`)}
              </p>
            </motion.li>
          ))}
        </motion.ol>
      </div>
    </section>
  );
}
