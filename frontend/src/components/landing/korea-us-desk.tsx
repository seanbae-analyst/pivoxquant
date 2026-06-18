"use client";

/**
 * KoreaUsDesk — Dual-market CFO desk (Seoul + New York).
 * -----------------------------------------------------------------------
 * Timeline visualization: KST 07:30 Pre-Seoul brief · EST 09:00 NY brief.
 * Korean "잠들기 전에 오늘 시장을, 일어나면 어젯밤 시장을." headline.
 */

import { motion, useReducedMotion } from "motion/react";
import { fadeUp } from "@/lib/motion";

type Tick = {
  local: string;
  zone: string;
  paired: string;
  title_en: string;
  title_ko: string;
  flag: string;
};

const TICKS: readonly Tick[] = [
  {
    local: "07:30",
    zone: "KST",
    paired: "17:30 EST prior",
    title_en: "Seoul Pre-Market Brief",
    title_ko: "서울 개장 전 보고서",
    flag: "KR",
  },
  {
    local: "09:30",
    zone: "EST",
    paired: "22:30 KST same",
    title_en: "New York Open Brief",
    title_ko: "뉴욕 개장 보고서",
    flag: "US",
  },
  {
    local: "16:00",
    zone: "EST",
    paired: "05:00 KST next",
    title_en: "US Close & Overnight Prep",
    title_ko: "미국 마감 · 오버나이트 준비",
    flag: "US",
  },
  {
    local: "23:00",
    zone: "KST",
    paired: "10:00 EST same",
    title_en: "Seoul Wrap · NY Tape-Read",
    title_ko: "서울 마감 · 뉴욕 장중 독해",
    flag: "KR",
  },
] as const;

export function KoreaUsDesk() {
  const reduce = useReducedMotion();

  return (
    <section
      id="pq-kr-us-desk"
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
            style={{ backgroundColor: "rgba(var(--pq-bronze-wash-rgb), 0.7)" }}
          />
          <span
            className="font-serif text-pq-mono-sm uppercase"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            Korea × US · A Desk That Doesn&rsquo;t Sleep
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
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
            fontWeight: 500,
          }}
        >
          잠들기 전엔 오늘 시장을.
          <br />
          일어나면 어젯밤 시장을.
        </motion.h2>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="font-serif mb-20 max-w-xl"
          style={{
            fontSize: "clamp(15px, 1.3vw, 17px)",
            lineHeight: 1.65,
            color: "rgba(245, 240, 232, 0.65)",
          }}
        >
          Seoul session ends, New York opens. New York closes, Seoul warms up.
          Both of your markets, observed at each end of the day — 한국 시간과
          뉴욕 시간을 잇는 연속 관측.
        </motion.p>

        {/* Timeline */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={fadeUp}
          className="relative"
        >
          {/* Horizontal rail (desktop) */}
          <div
            aria-hidden
            className="absolute left-0 right-0 top-6 h-px hidden md:block"
            style={{ backgroundColor: "rgba(var(--pq-bronze-wash-rgb),0.35)" }}
          />

          <ol className="grid grid-cols-1 gap-10 md:grid-cols-4 md:gap-6">
            {TICKS.map((t, idx) => (
              <li key={idx} className="relative">
                {/* Dot */}
                <div
                  aria-hidden
                  className="absolute -top-1 left-0 md:left-0 h-3 w-3 rounded-full"
                  style={{
                    backgroundColor:
                      t.flag === "KR"
                        ? "rgba(245,240,232,0.9)"
                        : "rgba(184,149,106,0.95)",
                    boxShadow:
                      t.flag === "KR"
                        ? "0 0 12px rgba(245,240,232,0.55)"
                        : "0 0 12px rgba(184,149,106,0.45)",
                  }}
                />
                <div className="pt-8 md:pt-12">
                  <div className="mb-3 flex items-baseline gap-2">
                    <span
                      className="font-mono tabular-nums text-pq-callout"
                      style={{
                        color: "var(--pq-ivory)",
                        letterSpacing: "-0.01em",
                      }}
                    >
                      {t.local}
                    </span>
                    <span
                      className="font-mono text-pq-eyebrow uppercase tabular-nums"
                      style={{
                        color: "var(--pq-bronze)",
                        letterSpacing: "0.2em",
                      }}
                    >
                      {t.zone}
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
                    {t.title_en}
                  </h3>
                  <p
                    className="font-serif mb-2"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      color: "rgba(var(--pq-bronze-wash-rgb),0.8)",
                    }}
                  >
                    {t.title_ko}
                  </p>
                  <p
                    className="font-mono text-pq-caption tabular-nums"
                    style={{
                      color: "rgba(245,240,232,0.45)",
                      letterSpacing: "0.02em",
                    }}
                  >
                    paired · {t.paired}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </motion.div>
      </div>
    </section>
  );
}

export default KoreaUsDesk;
