"use client";

/**
 * Zone2 ANALYTICS — Quant four-pillar composite (bars).
 *
 * KR convention colours via the price-direction tokens (carmine high /
 * indigo low / bronze mid). Heading is one level below Zone1 and upright.
 */

import { cn } from "@/lib/utils";
import { FieldLabel } from "@/components/ui/editorial";
import { SectionHeading, EmptyNote } from "./shared";
import type { SignalDetail } from "./types";

function PillarCard({
  label,
  score,
  observation,
}: {
  label: string;
  score: number;
  observation: string;
}) {
  const safe = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const token: "POSITIVE" | "NEGATIVE" | "NEUTRAL" =
    safe >= 65 ? "POSITIVE" : safe <= 35 ? "NEGATIVE" : "NEUTRAL";
  // KR convention (CEO 2026-04-26): POSITIVE → carmine (▲), NEGATIVE → indigo (▼).
  const barColor =
    token === "POSITIVE"
      ? "bg-[var(--up)]"
      : token === "NEGATIVE"
        ? "bg-[var(--down)]"
        : "bg-[var(--pq-bronze)]";
  const textColor =
    token === "POSITIVE"
      ? "text-[var(--up)]"
      : token === "NEGATIVE"
        ? "text-[var(--down)]"
        : "text-[var(--pq-ivory-mid)]";
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-sm pq-ink-card-interactive">
      <div className="flex items-center justify-between">
        <FieldLabel>{label}</FieldLabel>
        <span
          className={cn(
            "text-pq-mono-tiny tracking-[0.12em] uppercase font-medium",
            textColor,
          )}
        >
          {token}
        </span>
      </div>
      <div className={cn("pq-ink-num mt-3 leading-none", textColor)}>
        {safe.toFixed(0)}
        <span className="text-pq-caption text-[var(--pq-ivory-faint)] ml-1.5">
          / 100
        </span>
      </div>
      <div className="mt-3 h-1.5 bg-[var(--pq-ivory-line)] overflow-hidden rounded-[1px]">
        <div
          className={cn("h-full transition-all rounded-[1px]", barColor)}
          style={{ width: `${safe}%` }}
        />
      </div>
      <p className="mt-3 pq-detail-body text-pq-body-sm">{observation}</p>
    </div>
  );
}

export function PillarGrid({
  signal,
  hasPillars,
  loading = false,
}: {
  signal: SignalDetail | undefined;
  hasPillars: boolean;
  loading?: boolean;
}) {
  return (
    <section>
      <div className="mb-5">
        <SectionHeading eyebrow="Quant breakdown" title="Four-pillar composite" />
      </div>
      {loading && !hasPillars ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-sm h-[120px] animate-pulse"
            />
          ))}
        </div>
      ) : hasPillars ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <PillarCard
            label="Technical"
            score={signal?.tech_score ?? 0}
            observation="가격 흐름·모멘텀·이동평균"
          />
          <PillarCard
            label="Fundamental"
            score={signal?.fund_score ?? 0}
            observation="실적·마진·부채·성장성"
          />
          <PillarCard
            label="Sentiment"
            score={signal?.news_score ?? 0}
            observation="뉴스 논조·미디어 커버리지"
          />
          <PillarCard
            label="Quant"
            score={signal?.quant_score ?? 0}
            observation="분산비율·모멘텀·52주 위치"
          />
        </div>
      ) : (
        <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-8 rounded-sm text-center">
          <EmptyNote>
            Pillar breakdown pending — composite calibration in progress.
          </EmptyNote>
        </div>
      )}
    </section>
  );
}
