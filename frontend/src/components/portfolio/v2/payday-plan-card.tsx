"use client";

/**
 * <PaydayPlanCard /> — 월급날 배분 on /portfolio (2026-10-14).
 *
 * On payday the user writes how they mean to split what came in — 생활비 ·
 * 저축 · 투자 · 기타, and optionally the amount itself. The 투자 part is then
 * set next to what their own recorded fills put in over that pay cycle; at
 * the next payday they say how the other parts went.
 *
 * Every amount stays in this browser (lib/payday-plan.ts — localStorage, one
 * key per user). The card never sends an amount anywhere: its only requests
 * are GETs of the user's own trades and the USD/KRW rate. Tests pin that
 * (no non-GET request, no amount in any URL).
 *
 * Look (CEO 2026-10-14 "너무 AI 같음"): drawn, not written — the way the
 * phone /portfolio summary went from a number table to a picture. A large
 * won figure, one split bar with the four parts labelled under it, and the
 * investment part as two bars on one scale (정한 몫 / 넣은 돈). The caveats
 * fold into "계산 방법"; storage is one line with a lock.
 *   Part colours are the brand neutrals (ivory 70% · bronze 62% · bronze ·
 *   ivory 38%) in this order — dataviz validator, dark surface: CVD ΔE 18.2,
 *   normal ΔE 18.8, all ≥ 3:1; the chroma / lightness-band checks fail by
 *   brand design (no saturated hues), so every segment is also named with
 *   its amount in the legend in the same order, with 2px gaps — identity is
 *   never colour alone.
 *
 * Posture (legal-kr-fintech review 2026-10-14 · docs/design/payday-allocation_2026-10-14.md):
 *  - four fixed parts, amounts only — no free-text labels;
 *  - no ratio, template or default amount — the numbers are the user's
 *    (no percentages printed either);
 *  - the comparison is a fact after the fact ("몫보다 많음"), never a
 *    directive, never shown before a trade;
 *  - none of the regulated trade verbs in copy — "산 금액 · 판 금액 · 넣은 돈".
 * Bronze, not carmine, for "몫보다 많음": information, not an alarm. No italic.
 * The USD/KRW rate is credited by the page footer (FxAttribution).
 */
import * as React from "react";
import { ChevronRight, Lock } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { fmtMoneyKo } from "@/lib/format";
import { useFxRate } from "@/lib/hooks";
import { useTransactions } from "@/components/portfolio/v2/hooks-v2";
import {
  PART_KEYS,
  PART_LABEL,
  REVIEW_LABEL,
  TRADE_FETCH_LIMIT,
  clearStore,
  cycleFlow,
  cycleFor,
  findCycle,
  kstToday,
  loadStore,
  parseAmount,
  partsTotal,
  previousCycle,
  saveStore,
  shortDate,
  unassigned,
  upsertCycle,
  won,
  type CyclePlan,
  type PartKey,
  type PartReview,
  type PaydayStore,
  type TradeRowLike,
} from "@/lib/payday-plan";

const IVORY = "var(--pq-ivory)";
const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const FAINT = "rgba(var(--pq-ivory-rgb), 0.38)";
const LINE = "1px solid var(--pq-ivory-line)";
const TRACK = "rgba(var(--pq-ivory-rgb), 0.07)";
const REVIEWED_PARTS = ["living", "saving", "other"] as const;

/** Part colours — fixed order, validated (see module doc). */
const PART_COLOR: Record<PartKey, string> = {
  living: "rgba(var(--pq-ivory-rgb), 0.70)",
  saving: "rgba(var(--pq-bronze-rgb), 0.62)",
  invest: "var(--pq-bronze)",
  other: "rgba(var(--pq-ivory-rgb), 0.38)",
};

/**
 * "150만원" when the amount is whole 만 — what people type for a split — and
 * the exact won otherwise, so two figures that look equal always are equal
 * (the 몫보다 많음 chip must never sit between two identical numbers).
 */
const man = (v: number) =>
  Math.round(v) % 10_000 === 0 ? fmtMoneyKo(v, "KRW", { compact: true }) : won(v);

/* ── small pieces ──────────────────────────────────────────────────────── */

function Dot({ color, hollow = false }: { color: string; hollow?: boolean }) {
  return (
    <span
      aria-hidden
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={hollow ? { border: `1px solid ${FAINT}` } : { background: color }}
    />
  );
}

function PrimaryButton({ className = "", style, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  // Disabled reads as a quiet neutral slab, not a dimmed bronze one.
  const off = Boolean(props.disabled);
  return (
    <button
      type="button"
      {...props}
      className={`h-11 px-5 text-[14px] font-semibold transition-colors ${className}`}
      style={{
        borderRadius: "var(--pq-radius-cta)",
        backgroundColor: off ? TRACK : "var(--pq-bronze)",
        color: off ? FAINT : "var(--pq-ink)",
        ...style,
      }}
    />
  );
}

function QuietButton({ className = "", style, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`text-[13px] transition-opacity hover:opacity-80 ${className}`}
      style={{ color: "var(--pq-bronze)", ...style }}
    />
  );
}

function OutlineButton({ className = "", style, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`h-10 px-4 text-[13px] transition-colors ${className}`}
      style={{
        borderRadius: "var(--pq-radius-cta)",
        border: LINE,
        color: IVORY,
        ...style,
      }}
    />
  );
}

/** Display the end of a [start, end) cycle as its last day. */
function lastDayBefore(end: string): string {
  const d = new Date(`${end}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return shortDate(d.toISOString().slice(0, 10));
}

function StorageLine({ onClear, detail = false }: { onClear?: () => void; detail?: boolean }) {
  return (
    <div className="mt-5 text-[12px]" style={{ color: DIM }}>
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5">
          <Lock size={12} strokeWidth={1.8} aria-hidden />
          이 기기에만 저장돼요 · 서버로 보내지 않아요
        </span>
        {onClear && (
          <button
            type="button"
            onClick={onClear}
            aria-label="이 기기에서 지우기"
            className="shrink-0 hover:opacity-80"
            style={{ color: DIM }}
          >
            지우기
          </button>
        )}
      </div>
      {detail && (
        <p className="mt-1 pl-[18px]" style={{ color: FAINT }}>
          그래서 다른 기기에선 보이지 않고, 브라우저 데이터를 지우면 함께 지워져요.
        </p>
      )}
    </div>
  );
}

/* ── the split, drawn ──────────────────────────────────────────────────── */

/**
 * One bar for the money: the four parts in fixed order, then whatever is not
 * yet given a part as plain track. 2px gaps, rounded outer ends. Over-split
 * (parts > income) scales to the parts and says so in the line below.
 */
function SplitBar({ income, parts }: Pick<CyclePlan, "income" | "parts">) {
  const total = partsTotal(parts);
  const scale = Math.max(total, income ?? 0, 1);
  const segs = PART_KEYS.filter((k) => (parts[k] ?? 0) > 0).map((k) => ({
    key: k,
    v: parts[k] as number,
    color: PART_COLOR[k],
  }));
  const rest = income !== null && income > total ? income - total : 0;
  return (
    <div
      className="flex h-2.5 w-full gap-[2px] overflow-hidden rounded-[4px]"
      style={{ background: segs.length === 0 ? TRACK : undefined }}
      aria-hidden
      data-testid="payday-split-bar"
    >
      {segs.map((s) => (
        <span
          key={s.key}
          title={`${PART_LABEL[s.key]} ${won(s.v)}`}
          style={{ width: `${(s.v / scale) * 100}%`, background: s.color }}
        />
      ))}
      {rest > 0 && <span title={`정하지 않음 ${won(rest)}`} style={{ flex: 1, background: TRACK }} />}
    </div>
  );
}

/**
 * Names and amounts under the bar, same order as the segments. Each entry is
 * name over amount at its natural width, wrapping — so it reads the same on a
 * phone and across a wide desktop card.
 */
function SplitLegend({ income, parts }: Pick<CyclePlan, "income" | "parts">) {
  const left = unassigned({ income, parts });
  const item = (key: string, dot: React.ReactNode, name: string, v: number, accent = false, testId?: string) => (
    <li key={key} className="min-w-[4.5rem]" data-testid={testId}>
      <span className="flex items-center gap-1.5 text-[12.5px]" style={{ color: DIM }}>
        {dot}
        {name}
      </span>
      <span
        className="mt-0.5 block pl-[14px] text-[15px] font-semibold tabular-nums"
        style={{ color: accent ? "var(--pq-bronze)" : IVORY }}
        title={won(v)}
      >
        {man(v)}
      </span>
    </li>
  );
  return (
    <ul className="mt-3 flex flex-wrap gap-x-7 gap-y-3">
      {PART_KEYS.filter((k) => parts[k] !== null).map((k) =>
        item(k, <Dot color={PART_COLOR[k]} />, PART_LABEL[k], parts[k] ?? 0),
      )}
      {left !== null &&
        left !== 0 &&
        item(
          "left",
          <Dot color="" hollow />,
          left > 0 ? "정하지 않음" : "넘게 나눔",
          Math.abs(left),
          left < 0,
          "payday-unassigned",
        )}
    </ul>
  );
}

/* ── payday picker ─────────────────────────────────────────────────────── */

function PaydayPicker({
  initial,
  onSave,
  onCancel,
  cta,
}: {
  initial: number | null;
  onSave: (day: number) => void;
  onCancel?: () => void;
  cta: string;
}) {
  const [day, setDay] = React.useState<number>(initial ?? 25);
  return (
    <div className="mt-5 flex flex-wrap items-center gap-3">
      <label
        htmlFor="payday-day"
        className="flex h-11 items-center gap-3 px-4"
        style={{ border: LINE, borderRadius: "var(--pq-radius-cta)" }}
      >
        <span className="text-[13px]" style={{ color: DIM }}>
          월급날
        </span>
        <select
          id="payday-day"
          aria-label="월급날"
          value={day}
          onChange={(e) => setDay(Number(e.target.value))}
          className="bg-transparent text-[15px] font-semibold tabular-nums outline-none"
          style={{ color: IVORY }}
        >
          {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
            <option key={d} value={d} style={{ background: "var(--pq-ink)" }}>
              매월 {d === 31 ? "말일" : `${d}일`}
            </option>
          ))}
        </select>
      </label>
      <PrimaryButton onClick={() => onSave(day)}>{cta}</PrimaryButton>
      {onCancel && <QuietButton onClick={onCancel}>취소</QuietButton>}
    </div>
  );
}

/* ── plan form ─────────────────────────────────────────────────────────── */

type Draft = { income: string; parts: Record<PartKey, string> };

function draftFrom(plan?: Pick<CyclePlan, "income" | "parts">): Draft {
  const fmt = (n: number | null | undefined) => (n == null ? "" : n.toLocaleString("ko-KR"));
  return {
    income: fmt(plan?.income),
    parts: {
      living: fmt(plan?.parts.living),
      saving: fmt(plan?.parts.saving),
      invest: fmt(plan?.parts.invest),
      other: fmt(plan?.parts.other),
    },
  };
}

function AmountRow({
  id,
  label,
  dot,
  value,
  onChange,
}: {
  id: string;
  label: string;
  dot?: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-3" style={{ borderBottom: LINE }}>
      <label htmlFor={id} className="flex items-center gap-2 text-[14px]" style={{ color: IVORY }}>
        {dot !== undefined && <Dot color={dot} />}
        {label}
      </label>
      <span className="flex items-baseline gap-1">
        <input
          id={id}
          aria-label={label}
          inputMode="numeric"
          autoComplete="off"
          value={value}
          placeholder="0"
          onChange={(e) => {
            const n = parseAmount(e.target.value);
            onChange(n === null ? "" : n.toLocaleString("ko-KR"));
          }}
          className="w-36 bg-transparent text-right text-[17px] font-semibold tabular-nums outline-none placeholder:font-normal"
          style={{ color: IVORY }}
        />
        <span className="text-[13px]" style={{ color: DIM }}>
          원
        </span>
      </span>
    </div>
  );
}

function PlanForm({
  cycle,
  initial,
  previous,
  onSave,
  onCancel,
}: {
  cycle: { start: string; end: string };
  initial?: CyclePlan;
  previous?: CyclePlan;
  onSave: (income: number | null, parts: Record<PartKey, number | null>) => void;
  onCancel?: () => void;
}) {
  const [draft, setDraft] = React.useState<Draft>(() => draftFrom(initial));
  const parts = Object.fromEntries(
    PART_KEYS.map((k) => [k, parseAmount(draft.parts[k])]),
  ) as Record<PartKey, number | null>;
  const income = parseAmount(draft.income);
  const canSave = PART_KEYS.some((k) => (parts[k] ?? 0) > 0);

  return (
    <div className="mt-4" data-testid="payday-plan-form">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] tabular-nums" style={{ color: DIM }}>
          {shortDate(cycle.start)} – {lastDayBefore(cycle.end)}
        </span>
        {previous && !initial && (
          <QuietButton onClick={() => setDraft(draftFrom(previous))}>지난 배분 그대로</QuietButton>
        )}
      </div>

      {/* The bar fills in as the amounts are typed. */}
      <div className="mt-4">
        <SplitBar income={income} parts={parts} />
        {canSave && <SplitLegend income={income} parts={parts} />}
      </div>

      <div className="mt-4" style={{ borderTop: LINE }}>
        <AmountRow
          id="payday-income"
          label="들어온 돈 (선택)"
          value={draft.income}
          onChange={(v) => setDraft((d) => ({ ...d, income: v }))}
        />
        {PART_KEYS.map((k) => (
          <AmountRow
            key={k}
            id={`payday-part-${k}`}
            label={PART_LABEL[k]}
            dot={PART_COLOR[k]}
            value={draft.parts[k]}
            onChange={(v) => setDraft((d) => ({ ...d, parts: { ...d.parts, [k]: v } }))}
          />
        ))}
      </div>
      <p className="mt-3 text-[12px]" style={{ color: DIM }}>
        금액은 내가 정해요. 서비스는 비율이나 금액을 권하지 않아요.
      </p>

      <div className="mt-4 flex items-center gap-3">
        <PrimaryButton className="flex-1 md:flex-none md:px-8" disabled={!canSave} onClick={() => onSave(income, parts)}>
          저장
        </PrimaryButton>
        {onCancel && <OutlineButton onClick={onCancel}>취소</OutlineButton>}
      </div>
    </div>
  );
}

/* ── the investment part next to what the fills put in ─────────────────── */

function CompareBar({
  label,
  value,
  scale,
  fill,
  approx = false,
}: {
  label: string;
  value: number;
  scale: number;
  fill: boolean;
  approx?: boolean;
}) {
  const w = scale > 0 ? Math.max(0, Math.min(1, value / scale)) : 0;
  return (
    <div className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-3 text-[13px] tabular-nums">
      <span style={{ color: DIM }}>{label}</span>
      <span className="h-2 overflow-hidden rounded-[4px]" style={{ background: TRACK }} aria-hidden>
        <span
          className="block h-full rounded-[4px]"
          style={{
            width: `${w * 100}%`,
            background: fill ? "var(--pq-bronze)" : "transparent",
            border: fill || w === 0 ? undefined : "1px solid var(--pq-bronze)",
          }}
        />
      </span>
      <span className="text-right" style={{ color: IVORY }} title={won(value)}>
        {approx ? "약 " : ""}
        {man(value)}
      </span>
    </div>
  );
}

function InvestCompare({
  plan,
  rows,
  end,
  fx,
}: {
  plan: CyclePlan;
  rows: TradeRowLike[] | null;
  end: string;
  fx: number | null;
}) {
  const target = plan.parts.invest ?? 0;
  if (rows === null) {
    return (
      <p className="mt-5 text-[12.5px]" style={{ color: DIM }}>
        체결 기록을 불러오는 중이에요.
      </p>
    );
  }
  const flow = cycleFlow(rows, plan.start, end, fx);
  const hasUsd = flow.USD.in > 0 || flow.USD.out > 0;
  const put = flow.netKrw;
  const over = put !== null && put > target;
  const scale = Math.max(target, put ?? 0, 1);
  const usd = (v: number) => fmtMoneyKo(v, "USD", { compact: true });
  const legs = (name: string, f: { in: number; out: number }, fmt: (v: number) => string) =>
    f.in > 0 || f.out > 0
      ? [`${name} ${[f.in > 0 && `산 ${fmt(f.in)}`, f.out > 0 && `판 ${fmt(f.out)}`].filter(Boolean).join(" · ")}`]
      : [];
  const sources = [...legs("원화", flow.KRW, man), ...legs("달러", flow.USD, usd)];

  return (
    <div className="mt-6 pt-5" style={{ borderTop: LINE }} data-testid="payday-invest-compare">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-[14px] font-semibold" style={{ color: IVORY }}>
          <Dot color={PART_COLOR.invest} />
          투자
        </span>
        {over && (
          <span
            className="rounded-full px-2.5 py-0.5 text-[11.5px]"
            style={{ color: "var(--pq-bronze)", border: "1px solid rgba(var(--pq-bronze-rgb), 0.6)" }}
          >
            몫보다 많음
          </span>
        )}
      </div>

      <div className="mt-4 space-y-2.5">
        <CompareBar label="정한 몫" value={target} scale={scale} fill={false} />
        {put === null ? (
          <div className="grid grid-cols-[3.5rem_1fr] items-center gap-3 text-[13px]">
            <span style={{ color: DIM }}>넣은 돈</span>
            <span style={{ color: DIM }}>환율을 불러오지 못했어요</span>
          </div>
        ) : (
          <CompareBar label="넣은 돈" value={Math.max(0, put)} scale={scale} fill approx={hasUsd} />
        )}
      </div>
      {put !== null && put < 0 && (
        <p className="mt-2 text-[12px] tabular-nums" style={{ color: DIM }}>
          이번 주기엔 판 금액이 {man(-put)} 더 많아요.
        </p>
      )}

      {/* Where the 넣은 돈 figure comes from — one quiet group per currency, zero legs left out. */}
      <p className="mt-3 flex flex-col gap-0.5 text-[12px] tabular-nums md:flex-row md:gap-5" style={{ color: DIM }}>
        {sources.length === 0 ? (
          <span>이번 주기에 기록된 체결이 없어요</span>
        ) : (
          sources.map((g) => (
            <span key={g} className="whitespace-nowrap">
              {g}
            </span>
          ))
        )}
      </p>

      <details className="mt-3 text-[12px]" style={{ color: DIM }}>
        <summary className="cursor-pointer select-none" style={{ color: DIM }}>
          계산 방법
        </summary>
        <p className="mt-2 leading-relaxed">
          넣은 돈 = 산 금액 − 판 금액. 이 서비스에 기록된 체결만 더한 대략값이에요
          {hasUsd ? " (달러는 오늘 환율로 환산)" : ""}. 은행·카드 내역과 가져오기 대기 중인 체결은 들어가지
          않아요.
          {flow.truncated ? ` 최근 ${TRADE_FETCH_LIMIT}건까지만 셌어요.` : ""}
        </p>
      </details>
    </div>
  );
}

/* ── last cycle look-back ──────────────────────────────────────────────── */

function Segmented({
  label,
  value,
  onChange,
}: {
  label: string;
  value: PartReview | undefined;
  onChange: (v: PartReview) => void;
}) {
  return (
    <span
      className="inline-flex p-0.5"
      role="group"
      aria-label={label}
      style={{ border: LINE, borderRadius: "var(--pq-radius-cta)" }}
    >
      {(Object.keys(REVIEW_LABEL) as PartReview[]).map((r) => {
        const on = value === r;
        return (
          <button
            key={r}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(r)}
            className="h-8 min-w-[3.25rem] px-2.5 text-[12.5px] transition-colors"
            style={{
              borderRadius: "calc(var(--pq-radius-cta) - 2px)",
              color: on ? "var(--pq-ink)" : DIM,
              background: on ? "var(--pq-bronze)" : "transparent",
              fontWeight: on ? 600 : 400,
            }}
          >
            {REVIEW_LABEL[r]}
          </button>
        );
      })}
    </span>
  );
}

function ReviewBlock({
  plan,
  onSave,
}: {
  plan: CyclePlan;
  onSave: (review: NonNullable<CyclePlan["review"]>) => void;
}) {
  const [review, setReview] = React.useState<NonNullable<CyclePlan["review"]>>(plan.review ?? {});
  const parts = REVIEWED_PARTS.filter((k) => plan.parts[k] !== null);
  if (parts.length === 0) return null;
  return (
    <div
      className="mt-4 p-4"
      style={{ border: LINE, borderRadius: "var(--pq-radius-card)" }}
      data-testid="payday-review"
    >
      <div className="text-[14px] font-semibold" style={{ color: IVORY }}>
        지난 주기는 어땠나요?
      </div>
      <p className="mt-1 text-[12px]" style={{ color: DIM }}>
        {shortDate(plan.start)}부터 · 투자는 체결 기록으로 따로 보여 드려요
      </p>
      <ul className="mt-3 space-y-2.5">
        {parts.map((k) => (
          <li key={k} className="flex flex-wrap items-center justify-between gap-2">
            <span className="flex items-center gap-2 text-[13.5px] tabular-nums" style={{ color: IVORY }}>
              <Dot color={PART_COLOR[k]} />
              {PART_LABEL[k]}
              <span style={{ color: DIM }}>{man(plan.parts[k] ?? 0)}</span>
            </span>
            <Segmented
              label={`${PART_LABEL[k]} 돌아보기`}
              value={review[k]}
              onChange={(r) => setReview((cur) => ({ ...cur, [k]: r }))}
            />
          </li>
        ))}
      </ul>
      <PrimaryButton className="mt-4 w-full md:w-auto" disabled={Object.keys(review).length === 0} onClick={() => onSave(review)}>
        돌아보기 저장
      </PrimaryButton>
    </div>
  );
}

/* ── the card ──────────────────────────────────────────────────────────── */

export function PaydayPlanCard({ variant = "card" }: { variant?: "card" | "plain" }) {
  const { user } = useAuth();
  const userId = typeof user?.id === "number" ? user.id : null;
  const { data: tradesData } = useTransactions(TRADE_FETCH_LIMIT);
  const { rate: fx } = useFxRate();

  // Read on the client only — localStorage does not exist during SSR.
  const [store, setStore] = React.useState<PaydayStore | null>(null);
  const [today, setToday] = React.useState<string | null>(null);
  const [editingPayday, setEditingPayday] = React.useState(false);
  const [editingPlan, setEditingPlan] = React.useState(false);
  const [saveFailed, setSaveFailed] = React.useState(false);

  React.useEffect(() => {
    if (userId === null) return;
    setStore(loadStore(userId));
    setToday(kstToday());
  }, [userId]);

  if (userId === null || store === null || today === null) return null;

  const persist = (next: PaydayStore) => {
    setSaveFailed(!saveStore(userId, next));
    setStore(next);
  };
  const clearAll = () => {
    if (typeof window !== "undefined" && !window.confirm("이 기기에 저장된 월급날 배분을 모두 지울까요?")) return;
    clearStore(userId);
    setStore({ v: 1, payday: null, cycles: [] });
  };

  const rows: TradeRowLike[] | null = tradesData
    ? ((tradesData.trades ?? tradesData.transactions ?? []) as TradeRowLike[])
    : null;

  const frame =
    variant === "card"
      ? {
          className: "p-6",
          style: {
            background: "rgba(255,255,255,0.02)",
            border: LINE,
            borderRadius: "var(--pq-radius-card)",
          } as React.CSSProperties,
        }
      : { className: "pt-2", style: undefined };

  const title = (
    <div className="text-[13px] font-semibold" style={{ color: "var(--pq-bronze)" }}>
      월급날 배분
    </div>
  );

  // ── no payday yet ──
  if (store.payday === null || editingPayday) {
    return (
      <section {...frame} aria-label="월급날 배분" data-testid="payday-plan-card">
        {title}
        <h3 className="mt-3 text-[19px] font-semibold leading-snug" style={{ color: IVORY }}>
          월급을 어떻게 나눌지
          <br />
          적어 두세요
        </h3>
        <p className="mt-2 text-[13.5px] leading-relaxed" style={{ color: DIM }}>
          투자 몫은 그 달 실제 체결과 나란히 보여 드려요.
        </p>
        <PaydayPicker
          initial={store.payday}
          cta={store.payday === null ? "시작하기" : "바꾸기"}
          onSave={(day) => {
            persist({ ...store, payday: day });
            setEditingPayday(false);
          }}
          onCancel={store.payday !== null ? () => setEditingPayday(false) : undefined}
        />
        <StorageLine detail />
      </section>
    );
  }

  const cycle = cycleFor(today, store.payday);
  const prev = previousCycle(cycle.start, store.payday);
  const current = findCycle(store, cycle.start);
  const last = findCycle(store, prev.start);
  const earlier = store.cycles.filter((c) => c.start < prev.start).slice(-5).reverse();
  const lastNeedsReview =
    last !== undefined &&
    REVIEWED_PARTS.some((k) => last.parts[k] !== null && !(last.review ?? {})[k]);

  const savePlan = (income: number | null, parts: Record<PartKey, number | null>) => {
    persist(
      upsertCycle(store, {
        start: cycle.start,
        income,
        parts,
        review: current?.review ?? {},
        savedAt: new Date().toISOString(),
      }),
    );
    setEditingPlan(false);
  };

  return (
    <section {...frame} aria-label="월급날 배분" data-testid="payday-plan-card">
      <div className="flex items-center justify-between gap-3">
        {title}
        <button
          type="button"
          onClick={() => setEditingPayday(true)}
          className="flex items-center gap-0.5 text-[12.5px] tabular-nums hover:opacity-80"
          style={{ color: DIM }}
          aria-label="월급날 바꾸기"
        >
          매월 {store.payday === 31 ? "말일" : `${store.payday}일`}
          <ChevronRight size={14} aria-hidden />
        </button>
      </div>

      {saveFailed && (
        <p className="mt-2 text-[12px]" role="alert" style={{ color: "var(--pq-bronze)" }}>
          이 브라우저가 저장을 막고 있어요(사생활 보호 모드 등). 화면을 닫으면 적은 내용이 사라질 수 있어요.
        </p>
      )}

      {last && lastNeedsReview && (
        <ReviewBlock plan={last} onSave={(review) => persist(upsertCycle(store, { ...last, review }))} />
      )}

      {!current || editingPlan ? (
        <PlanForm
          cycle={cycle}
          initial={editingPlan ? current : undefined}
          previous={last ?? store.cycles[store.cycles.length - 1]}
          onSave={savePlan}
          onCancel={editingPlan ? () => setEditingPlan(false) : undefined}
        />
      ) : (
        <div className="mt-4" data-testid="payday-plan-current">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] tabular-nums" style={{ color: DIM }}>
              {shortDate(cycle.start)} – {lastDayBefore(cycle.end)}
            </span>
            <QuietButton onClick={() => setEditingPlan(true)}>고치기</QuietButton>
          </div>

          {/* The headline figure: what came in, or what was split. */}
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className="text-[30px] font-semibold leading-none tracking-[-0.01em] tabular-nums"
              style={{ color: IVORY }}
              title={won(current.income ?? partsTotal(current.parts))}
            >
              {man(current.income ?? partsTotal(current.parts))}
            </span>
            <span className="text-[13px]" style={{ color: DIM }}>
              {current.income !== null ? "들어온 돈" : "나눈 돈"}
            </span>
          </div>

          <div className="mt-4">
            <SplitBar income={current.income} parts={current.parts} />
            <SplitLegend income={current.income} parts={current.parts} />
          </div>

          {current.parts.invest !== null && (
            <InvestCompare plan={current} rows={rows} end={cycle.end} fx={fx} />
          )}
        </div>
      )}

      {/* look-back: last and earlier cycles, as the user left them */}
      {(last || earlier.length > 0) && (
        <details className="mt-6 pt-4" style={{ borderTop: LINE }}>
          <summary className="cursor-pointer select-none text-[13px]" style={{ color: DIM }}>
            지난 주기
          </summary>
          <ul className="mt-3 space-y-4">
            {[...(last ? [last] : []), ...earlier].map((plan) => {
              // A stored start is a payday, so the cycle it opens ends at the
              // next payday (if the payday was changed since, at the next one
              // under the current setting — close enough here).
              const end = cycleFor(plan.start, store.payday ?? 1).end;
              const flow = rows ? cycleFlow(rows, plan.start, end, fx) : null;
              const put = flow && !flow.truncated ? flow.netKrw : null;
              return (
                <li key={plan.start}>
                  <div className="flex items-baseline justify-between gap-3 text-[13px] tabular-nums">
                    <span style={{ color: IVORY }}>{shortDate(plan.start)}부터</span>
                    <span style={{ color: DIM }}>
                      {plan.parts.invest !== null && `투자 몫 ${man(plan.parts.invest)}`}
                      {put !== null && put !== undefined && ` · 넣은 돈 ${man(Math.max(0, put))}`}
                    </span>
                  </div>
                  <div className="mt-2">
                    <SplitBar income={plan.income} parts={plan.parts} />
                  </div>
                  {REVIEWED_PARTS.some((k) => plan.review?.[k]) && (
                    <div className="mt-1.5 text-[12px]" style={{ color: DIM }}>
                      {REVIEWED_PARTS.filter((k) => plan.review?.[k])
                        .map((k) => `${PART_LABEL[k]} ${REVIEW_LABEL[plan.review![k]!]}`)
                        .join(" · ")}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </details>
      )}

      <StorageLine onClear={clearAll} />
    </section>
  );
}

export default PaydayPlanCard;
