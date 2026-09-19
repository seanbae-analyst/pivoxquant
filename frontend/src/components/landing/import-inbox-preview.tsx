"use client";

/**
 * ImportInboxPreview — "숫자는 손으로 치지 않습니다."
 * ----------------------------------------------------------------------
 * Sits directly under <ThreeSteps/>. The 기록 card there says in passing
 * that a broker file or a fill notification fills the numbers in; this
 * section shows that one sentence at full size, because "typing every fill
 * by hand" is the objection the landing was not answering (2026-09-19).
 *
 * Every claim below is a route, same rule as three-steps.tsx:
 *   /journal/import          — CSV/XLSX/XLS/PDF ≤2MB or pasted text
 *                              (app/(dashboard)/journal/import/page.tsx)
 *   share_target → /journal/import — Android share sheet, GET ?text=
 *                              (app/manifest.ts)
 *   /settings#import-tokens  — personal token, own automation POSTs to the
 *                              webhook (components/settings/import-tokens-section.tsx,
 *                              routes/imports.py Phase 2)
 *   parser                   — services/imports/text_parser.py: one fill per
 *                              line; 주문 접수·정정·취소·미체결 lines are skipped
 *                              with a reason; no date on the line → today.
 *   approval gate            — nothing reaches trade_history until the user
 *                              writes a thesis and approves (import-inbox.tsx)
 *
 * The demo rows are the parser's own documented sample shapes, not live
 * data. The side label comes from @/lib/pre-trade so it reads exactly as
 * it does inside the app ("Long Entry · 진입"), never a raw BUY/SELL.
 *
 * What it must not say: account linking (BROKER_LINKING_AVAILABLE=false),
 * image upload (never accepted — OCR is on the user's device), anything
 * that sounds like the tool judges the fill. Copy lives in
 * messages/{ko,en}.json under `landing.inbox`.
 *
 * Palette: Vantablack + Bronze + Ivory only. No italic.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";

import { Eyebrow } from "./eyebrow";
import { fadeUp, stagger } from "@/lib/motion";
import { useT } from "@/lib/locale";
import { sideLabel } from "@/lib/pre-trade";

const IMPORT_ROUTE = "/journal/import";
const TOKEN_ROUTE = "/settings#import-tokens";

/** The three ways a fill reaches the inbox. Route is printed as the receipt. */
const PATHS = [
  { key: "p1", route: IMPORT_ROUTE },
  { key: "p2", route: IMPORT_ROUTE },
  { key: "p3", route: TOKEN_ROUTE },
] as const;

/** Parsed demo rows — mirror text_parser.py's documented sample lines. */
type ParsedRow = {
  rawKey: "raw1" | "raw3";
  ticker: string;
  side: "ENTRY" | "EXIT";
  qty: string;
  price: string;
  /** i18n key for the time cell, or a literal when the line carried one. */
  time: { literal: string } | { key: "timeToday" };
};

const PARSED: readonly ParsedRow[] = [
  {
    rawKey: "raw1",
    ticker: "삼성전자",
    side: "ENTRY",
    qty: "10",
    price: "₩71,200",
    time: { literal: "09/01 10:32" },
  },
  {
    rawKey: "raw3",
    ticker: "AAPL",
    side: "ENTRY",
    qty: "5",
    price: "$190.12",
    time: { key: "timeToday" },
  },
] as const;

const FIELD_LABEL_STYLE = {
  color: "var(--pq-ivory-faint)",
  fontSize: "var(--pq-text-eyebrow)",
  letterSpacing: "0.18em",
} as const;

const FIELD_VALUE_STYLE = {
  color: "var(--pq-ivory)",
  fontSize: "var(--pq-text-body-sm)",
  lineHeight: 1.4,
} as const;

export default function ImportInboxPreview() {
  const t = useT();
  const reduce = useReducedMotion();

  return (
    <section
      id="import-inbox"
      aria-labelledby="pq-inbox-heading"
      className="relative py-24 md:py-32 lg:py-40"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="grid grid-cols-1 gap-14 lg:grid-cols-12 lg:gap-12">
          {/* ── Copy + the three paths ─────────────────────────────── */}
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-80px" }}
            variants={stagger}
            className="lg:col-span-5"
          >
            <motion.div variants={fadeUp}>
              <Eyebrow className="mb-6">{t("landing.inbox.eyebrow")}</Eyebrow>
              <h2
                id="pq-inbox-heading"
                className="pq-silver-matte font-serif"
                style={{
                  fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                  lineHeight: 1.08,
                  letterSpacing: "-0.02em",
                  fontWeight: 500,
                  marginBottom: 24,
                }}
              >
                {t("landing.inbox.heading")}
              </h2>
              <p
                className="font-serif"
                style={{
                  fontSize: "var(--pq-text-deck)",
                  lineHeight: 1.65,
                  color: "var(--pq-ivory-mid)",
                  maxWidth: 480,
                }}
              >
                {t("landing.inbox.deck")}
              </p>
            </motion.div>

            <motion.ol
              variants={stagger}
              className="mt-12 flex flex-col"
              style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
            >
              {PATHS.map((p, i) => (
                <motion.li
                  key={p.key}
                  variants={fadeUp}
                  className="grid grid-cols-[2.25rem_1fr] gap-x-3 py-5"
                  style={{ borderBottom: "0.5pt solid var(--pq-ivory-line)" }}
                >
                  <span
                    className="font-serif pt-0.5"
                    style={{
                      color: "var(--pq-bronze)",
                      fontSize: "var(--pq-text-caption)",
                      letterSpacing: "0.22em",
                    }}
                  >
                    {["I", "II", "III"][i]}
                  </span>
                  <div>
                    <div className="flex items-baseline gap-3">
                      <h3
                        className="font-serif"
                        style={{
                          color: "var(--pq-ivory)",
                          fontSize: "var(--pq-text-body)",
                          fontWeight: 500,
                        }}
                      >
                        {t(`landing.inbox.${p.key}title`)}
                      </h3>
                      {/* The route is the receipt, exactly as on ThreeSteps. */}
                      <Link
                        href={p.route}
                        className="ml-auto font-mono transition-colors hover:text-[var(--pq-bronze)]"
                        style={{
                          color: "var(--pq-ivory-faint)",
                          fontSize: "var(--pq-text-eyebrow)",
                          letterSpacing: "0.04em",
                        }}
                      >
                        {p.route}
                      </Link>
                    </div>
                    <p
                      className="mt-2 font-serif"
                      style={{
                        color: "rgba(245,240,232,0.74)",
                        fontSize: "var(--pq-text-body-sm)",
                        lineHeight: 1.7,
                      }}
                    >
                      {t(`landing.inbox.${p.key}body`)}
                    </p>
                  </div>
                </motion.li>
              ))}
            </motion.ol>
          </motion.div>

          {/* ── The receipt: pasted lines → tagged rows ───────────── */}
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-80px" }}
            variants={stagger}
            className="lg:col-span-7"
            aria-label={t("landing.inbox.demoAria")}
          >
            <motion.div
              variants={fadeUp}
              className="p-6 md:p-8"
              style={{
                border: "0.5pt solid rgba(184,149,106,0.28)",
                backgroundColor: "var(--pq-card-veil)",
              }}
            >
              {/* Pasted notification text, verbatim */}
              <div
                className="mb-3 font-serif uppercase"
                style={FIELD_LABEL_STYLE}
              >
                {t("landing.inbox.rawLabel")}
              </div>
              <pre
                className="overflow-x-auto whitespace-pre-wrap font-mono"
                style={{
                  color: "rgba(245,240,232,0.82)",
                  fontSize: "var(--pq-text-caption)",
                  lineHeight: 1.9,
                  padding: "14px 16px",
                  border: "0.5pt solid var(--pq-ivory-line)",
                  backgroundColor: "#050505",
                }}
              >
                {t("landing.inbox.raw1")}
                {"\n"}
                {t("landing.inbox.raw2")}
                {"\n"}
                {t("landing.inbox.raw3")}
              </pre>

              {/* Hairline connector — the parse step, drawn not narrated */}
              <div className="my-6 flex items-center gap-4" aria-hidden>
                <span
                  className="h-px flex-1"
                  style={{ backgroundColor: "rgba(184,149,106,0.35)" }}
                />
                <span
                  className="font-serif uppercase"
                  style={{
                    color: "var(--pq-bronze)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.22em",
                  }}
                >
                  {t("landing.inbox.parsedLabel")}
                </span>
                <span
                  className="h-px flex-1"
                  style={{ backgroundColor: "rgba(184,149,106,0.35)" }}
                />
              </div>

              {/* Tagged rows */}
              <motion.ul variants={stagger} className="flex flex-col gap-3">
                {PARSED.map((row) => (
                  <motion.li
                    key={row.rawKey}
                    variants={fadeUp}
                    className="grid grid-cols-2 gap-x-4 gap-y-4 p-4 sm:grid-cols-3 md:grid-cols-6"
                    style={{
                      border: "0.5pt solid var(--pq-ivory-line)",
                      backgroundColor: "#050505",
                    }}
                  >
                    <Field label={t("landing.inbox.fTicker")} value={row.ticker} />
                    <Field
                      label={t("landing.inbox.fSide")}
                      value={sideLabel(row.side)}
                      bronze
                    />
                    <Field
                      label={t("landing.inbox.fQty")}
                      value={t("landing.inbox.qtyUnit", { n: row.qty })}
                    />
                    <Field label={t("landing.inbox.fPrice")} value={row.price} />
                    <Field
                      label={t("landing.inbox.fTime")}
                      value={
                        "literal" in row.time
                          ? row.time.literal
                          : t(`landing.inbox.${row.time.key}`)
                      }
                      muted={!("literal" in row.time)}
                    />
                    {/* The one cell that stays empty on purpose. */}
                    <div className="col-span-2 sm:col-span-3 md:col-span-1">
                      <div className="mb-1.5 font-serif uppercase" style={FIELD_LABEL_STYLE}>
                        {t("landing.inbox.fWhy")}
                      </div>
                      <div
                        className="font-serif"
                        style={{
                          color: "var(--pq-bronze)",
                          fontSize: "var(--pq-text-caption)",
                          lineHeight: 1.4,
                          borderBottom: "0.5pt dashed rgba(184,149,106,0.6)",
                          paddingBottom: 3,
                        }}
                      >
                        {t("landing.inbox.whyEmpty")}
                      </div>
                    </div>
                  </motion.li>
                ))}

                {/* The line the parser refused — an order notice is not a fill. */}
                <motion.li
                  variants={fadeUp}
                  className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-baseline sm:gap-4"
                  style={{ border: "0.5pt dashed var(--pq-ivory-line)" }}
                >
                  <span
                    className="font-mono"
                    style={{
                      color: "var(--pq-ivory-faint)",
                      fontSize: "var(--pq-text-caption)",
                    }}
                  >
                    {t("landing.inbox.raw2")}
                  </span>
                  <span
                    className="font-serif sm:ml-auto sm:text-right"
                    style={{
                      color: "var(--pq-ivory-mid)",
                      fontSize: "var(--pq-text-caption)",
                      lineHeight: 1.5,
                    }}
                  >
                    {t("landing.inbox.skip")}
                  </span>
                </motion.li>
              </motion.ul>

              <p
                className="mt-5 font-serif"
                style={{
                  color: "var(--pq-ivory-faint)",
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.02em",
                  lineHeight: 1.6,
                }}
              >
                {t("landing.inbox.demoNote")}
              </p>
            </motion.div>

            {/* Limits — the product's only defensible claims, same as ThreeSteps. */}
            <motion.ul
              variants={stagger}
              className="mt-8 grid grid-cols-1 gap-px sm:grid-cols-3"
              style={{ backgroundColor: "rgba(184,149,106,0.18)" }}
            >
              {(["limit1", "limit2", "limit3"] as const).map((k) => (
                <motion.li
                  key={k}
                  variants={fadeUp}
                  className="p-5 font-serif"
                  style={{
                    backgroundColor: "#050505",
                    color: "var(--pq-ivory-faint)",
                    fontSize: "var(--pq-text-eyebrow)",
                    lineHeight: 1.6,
                    letterSpacing: "0.02em",
                  }}
                >
                  {t(`landing.inbox.${k}`)}
                </motion.li>
              ))}
            </motion.ul>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  bronze = false,
  muted = false,
}: {
  label: string;
  value: string;
  bronze?: boolean;
  muted?: boolean;
}) {
  return (
    <div>
      <div className="mb-1.5 font-serif uppercase" style={FIELD_LABEL_STYLE}>
        {label}
      </div>
      <div
        className="font-serif"
        style={{
          ...FIELD_VALUE_STYLE,
          color: bronze
            ? "var(--pq-bronze)"
            : muted
              ? "var(--pq-ivory-mid)"
              : FIELD_VALUE_STYLE.color,
        }}
      >
        {value}
      </div>
    </div>
  );
}
