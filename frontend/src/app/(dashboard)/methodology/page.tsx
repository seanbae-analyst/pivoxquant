"use client";

/**
 * /methodology — Methodology & Data Transparency (Data-trust Stage 1).
 *
 * Per docs/strategy/DATA_TRUST_STRATEGY.md Stage 1: the strongest proof of
 * trustworthiness is *reproducibility* — every number we show can be
 * re-derived from public, licensed data. This page surfaces, in one place:
 *
 *   - the engine model catalog grouped by category, each model carrying its
 *     published `academic_source` (the reproducibility anchor);
 *   - the system data lineage (FMP / SEC EDGAR / FRED), pulled live from the
 *     backend so the provenance is never hardcoded in the frontend — the very
 *     anti-pattern services/artifacts/data_source_resolver.py was built to
 *     prevent (표시광고법 §3);
 *   - a reproducibility statement + the observation-only disclaimer.
 *
 * Legal posture: observation-only. POSITIVE / NEGATIVE / NEUTRAL only; no
 * 추천 / 조언 / 매수 / 매도. The (dashboard)/layout.tsx mounts the bottom legal
 * banner ("signal" type for /methodology); the API additionally returns a
 * model-scoped disclaimer rendered in the footer.
 *
 * v3 design: Vantablack + Bronze + Playfair, composed from the editorial
 * primitive library (no raw hex — design tokens only).
 */

import type { CSSProperties } from "react";
import {
  RuledKicker,
  EditorialHead,
  DeckLine,
  Caption,
  NumDisplay,
  HairlineSoft,
} from "@/components/ui/editorial";
import { useMethodology } from "@/lib/hooks";
import type { MethodologyModel } from "@/lib/types";

const PAGE = "mx-auto w-full max-w-2xl px-4 py-8 sm:px-6";

const CARD: CSSProperties = {
  border: "0.5px solid var(--pq-ivory-line)",
  background: "var(--pq-card-veil)",
  borderRadius: 3,
  padding: "16px 18px",
};

const EYEBROW: CSSProperties = {
  fontSize: "var(--pq-text-eyebrow)",
  textTransform: "uppercase",
  letterSpacing: "0.14em",
  color: "rgba(245,240,232,0.5)",
};

export default function MethodologyPage() {
  const { data, error, isLoading } = useMethodology();

  if (isLoading) {
    return (
      <div className={PAGE}>
        <Caption>방법론 정보를 불러오는 중…</Caption>
      </div>
    );
  }

  if (error || !data?.ok) {
    return (
      <div className={`${PAGE} space-y-3`}>
        <RuledKicker>방법론 · METHODOLOGY</RuledKicker>
        <Caption>
          방법론 정보를 일시적으로 불러올 수 없습니다. 잠시 후 다시 시도해
          주세요.
        </Caption>
      </div>
    );
  }

  // Group models by category, preserving the backend's category ordering.
  const byCategory: Record<string, MethodologyModel[]> = {};
  for (const m of data.models) {
    (byCategory[m.category] ??= []).push(m);
  }

  return (
    <div className={`${PAGE} space-y-12 pb-20`}>
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="space-y-3">
        <RuledKicker>방법론 · 투명성 · METHODOLOGY</RuledKicker>
        <EditorialHead as="h1" size={36}>
          모든 수치의 출처와 산출 방법
        </EditorialHead>
        <DeckLine>{data.reproducibility.statement_kr}</DeckLine>
        <Caption>{data.reproducibility.statement_en}</Caption>
      </header>

      {/* ── Stat strip ──────────────────────────────────────── */}
      <div className="flex flex-wrap gap-x-10 gap-y-4">
        <Stat
          value={`${data.active}`}
          suffix={`/ ${data.total}`}
          label="공개 모델 · ACTIVE MODELS"
        />
        <Stat
          value={`${data.categories.length}`}
          label="카테고리 · CATEGORIES"
        />
        <Stat
          value={`${data.data_lineage.length}`}
          label="데이터 출처 · DATA SOURCES"
        />
      </div>

      {/* ── Data sources ────────────────────────────────────── */}
      <section className="space-y-5">
        <RuledKicker>데이터 출처 · DATA SOURCES</RuledKicker>
        <Caption>
          모든 분석은 아래 공개·라이선스 데이터 위에서만 계산됩니다. 연결된
          브로커가 없으면 어떤 브로커도 출처로 표기하지 않습니다.
        </Caption>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {data.data_lineage.map((src) => (
            <div key={src.source} style={CARD}>
              <EditorialHead as="h3" size={18} tone="bronze">
                {src.source}
              </EditorialHead>
              <p
                className="mt-1.5 font-serif"
                style={{
                  fontSize: 13.5,
                  lineHeight: 1.45,
                  color: "var(--pq-ivory)",
                }}
              >
                {src.description}
              </p>
              <p
                className="mt-1 font-sans"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  lineHeight: 1.4,
                  color: "rgba(245,240,232,0.5)",
                }}
              >
                {src.coverage}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Engine models ───────────────────────────────────── */}
      <section className="space-y-7">
        <div className="space-y-2">
          <RuledKicker>엔진 모델 · ENGINE MODELS</RuledKicker>
          <Caption>
            각 모델은 관찰 도구이며, 공개된 학술 출처의 산출식을 따릅니다.
            점수·추천이 아니라 정보 고지입니다.
          </Caption>
        </div>

        {data.categories.map((cat) => {
          const models = byCategory[cat] ?? [];
          if (models.length === 0) return null;
          return (
            <div key={cat} className="space-y-3">
              <div className="flex items-baseline gap-3">
                <EditorialHead as="h2" size={22}>
                  {cat}
                </EditorialHead>
                <NumDisplay size={14}>{models.length}</NumDisplay>
              </div>
              <HairlineSoft />
              <div className="space-y-5">
                {models.map((m) => (
                  <article key={m.name} className="space-y-1">
                    <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
                      <span
                        className="font-mono"
                        style={{
                          fontSize: 13.5,
                          color: "var(--pq-ivory)",
                          letterSpacing: "-0.01em",
                        }}
                      >
                        {m.name}
                      </span>
                      <span className="font-sans" style={EYEBROW}>
                        {m.module}
                      </span>
                    </div>
                    <p
                      className="font-serif"
                      style={{
                        fontSize: 13.5,
                        lineHeight: 1.5,
                        color: "rgba(245,240,232,0.72)",
                      }}
                    >
                      {m.description_kr}
                    </p>
                    <p
                      className="font-sans"
                      style={{
                        fontSize: "var(--pq-text-eyebrow)",
                        lineHeight: 1.45,
                        color: "var(--pq-bronze)",
                      }}
                    >
                      근거 · {m.academic_source}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          );
        })}
      </section>

      {/* ── Disclaimer footer ───────────────────────────────── */}
      <footer className="space-y-3 pt-2">
        <HairlineSoft />
        <Caption>{data.disclaimer}</Caption>
      </footer>
    </div>
  );
}

/** Compact stat — mono value + uppercase editorial label. */
function Stat({
  value,
  suffix,
  label,
}: {
  value: string;
  suffix?: string;
  label: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline gap-1.5">
        <NumDisplay size={30}>{value}</NumDisplay>
        {suffix ? (
          <span
            className="font-mono"
            style={{ fontSize: 14, color: "rgba(245,240,232,0.45)" }}
          >
            {suffix}
          </span>
        ) : null}
      </div>
      <div className="font-sans" style={EYEBROW}>
        {label}
      </div>
    </div>
  );
}
