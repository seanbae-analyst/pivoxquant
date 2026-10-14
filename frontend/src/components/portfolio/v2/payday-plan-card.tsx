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
 * Posture (legal-kr-fintech review 2026-10-14 · docs/design/payday-allocation_2026-10-14.md):
 *  - four fixed parts, amounts only — no free-text labels;
 *  - no ratio, template or default amount — the numbers are the user's;
 *  - the comparison is a fact after the fact ("몫보다 많음"), never a
 *    directive, never shown before a trade;
 *  - none of the regulated trade verbs in copy — "산 금액 · 판 금액 · 넣은 돈".
 * Bronze, not carmine, for "몫보다 많음": information, not an alarm. No italic.
 * The USD/KRW rate is credited by the page footer (FxAttribution).
 */
import * as React from "react";

import { useAuth } from "@/lib/auth";
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

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const LINE = "1px solid var(--pq-ivory-line)";
const REVIEWED_PARTS = ["living", "saving", "other"] as const;

/* ── small pieces ──────────────────────────────────────────────────────── */

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[12.5px]" style={{ color: "var(--pq-bronze)" }}>
      {children}
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-2 text-[11.5px] leading-relaxed" style={{ color: DIM }}>
      {children}
    </p>
  );
}

function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`px-4 py-2 text-[13px] font-semibold disabled:opacity-50 ${props.className ?? ""}`}
      style={{
        borderRadius: "var(--pq-radius-cta)",
        backgroundColor: "var(--pq-bronze)",
        color: "var(--pq-ink)",
        ...props.style,
      }}
    />
  );
}

function TextButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`text-[12.5px] underline underline-offset-2 ${props.className ?? ""}`}
      style={{ color: "var(--pq-bronze)", ...props.style }}
    />
  );
}

/** "11월 25일" → display end of a [start, end) cycle as its last day. */
function lastDayBefore(end: string): string {
  const d = new Date(`${end}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return shortDate(d.toISOString().slice(0, 10));
}

function AmountInput({
  id,
  label,
  value,
  onChange,
  optional = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  optional?: boolean;
}) {
  return (
    <label htmlFor={id} className="flex items-center justify-between gap-3 py-2" style={{ borderBottom: LINE }}>
      <span className="text-[13.5px]" style={{ color: "var(--pq-ivory)" }}>
        {label}
        {optional && (
          <span className="ml-1.5 text-[11.5px]" style={{ color: DIM }}>
            선택
          </span>
        )}
      </span>
      <span className="flex items-center gap-1">
        <input
          id={id}
          aria-label={optional ? `${label} (선택)` : label}
          inputMode="numeric"
          autoComplete="off"
          value={value}
          placeholder="0"
          onChange={(e) => {
            const n = parseAmount(e.target.value);
            onChange(n === null ? "" : n.toLocaleString("ko-KR"));
          }}
          className="w-36 bg-transparent px-2 py-1 text-right text-[14px] tabular-nums outline-none"
          style={{ color: "var(--pq-ivory)", border: LINE, borderRadius: "var(--pq-radius-cta)" }}
        />
        <span className="text-[12.5px]" style={{ color: DIM }}>
          원
        </span>
      </span>
    </label>
  );
}

/* ── payday picker ─────────────────────────────────────────────────────── */

function PaydayPicker({
  initial,
  onSave,
  onCancel,
}: {
  initial: number | null;
  onSave: (day: number) => void;
  onCancel?: () => void;
}) {
  const [day, setDay] = React.useState<number>(initial ?? 25);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3">
      <label htmlFor="payday-day" className="text-[13.5px]" style={{ color: "var(--pq-ivory)" }}>
        매월
      </label>
      <select
        id="payday-day"
        value={day}
        onChange={(e) => setDay(Number(e.target.value))}
        className="bg-transparent px-2 py-1 text-[14px] tabular-nums"
        style={{ color: "var(--pq-ivory)", border: LINE, borderRadius: "var(--pq-radius-cta)" }}
      >
        {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
          <option key={d} value={d} style={{ background: "var(--pq-ink)" }}>
            {d === 31 ? "말일" : `${d}일`}
          </option>
        ))}
      </select>
      <PrimaryButton onClick={() => onSave(day)}>월급날로 정하기</PrimaryButton>
      {onCancel && <TextButton onClick={onCancel}>그대로 두기</TextButton>}
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
  const left = unassigned({ income, parts });
  const canSave = PART_KEYS.some((k) => (parts[k] ?? 0) > 0);

  return (
    <div className="mt-3" data-testid="payday-plan-form">
      <p className="text-[13px] leading-relaxed" style={{ color: DIM }}>
        {shortDate(cycle.start)} ~ {lastDayBefore(cycle.end)} 주기를 어떻게 나눌지 적어 두세요. 여기
        적는 금액은 내가 정한 숫자예요 — 서비스는 비율이나 금액을 권하지 않아요.
      </p>
      {previous && !initial && (
        <TextButton className="mt-2" onClick={() => setDraft(draftFrom(previous))}>
          지난 배분 그대로 가져오기
        </TextButton>
      )}
      <div className="mt-2" style={{ borderTop: LINE }}>
        <AmountInput
          id="payday-income"
          label="이번에 들어온 돈"
          optional
          value={draft.income}
          onChange={(v) => setDraft((d) => ({ ...d, income: v }))}
        />
        {PART_KEYS.map((k) => (
          <AmountInput
            key={k}
            id={`payday-part-${k}`}
            label={PART_LABEL[k]}
            value={draft.parts[k]}
            onChange={(v) => setDraft((d) => ({ ...d, parts: { ...d.parts, [k]: v } }))}
          />
        ))}
      </div>
      {left !== null && (
        <p className="mt-2 text-[12.5px] tabular-nums" style={{ color: left < 0 ? "var(--pq-bronze)" : DIM }} data-testid="payday-unassigned">
          {left >= 0 ? `아직 정하지 않은 돈 ${won(left)}` : `들어온 돈보다 ${won(-left)} 더 나눴어요`}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <PrimaryButton disabled={!canSave} onClick={() => onSave(income, parts)}>
          이 배분 저장
        </PrimaryButton>
        {onCancel && <TextButton onClick={onCancel}>취소</TextButton>}
      </div>
    </div>
  );
}

/* ── comparison ────────────────────────────────────────────────────────── */

function InvestComparison({
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
  const target = plan.parts.invest;
  if (rows === null) {
    return <Note>체결 기록을 불러오는 중이에요.</Note>;
  }
  const flow = cycleFlow(rows, plan.start, end, fx);
  const hasUsd = flow.USD.in > 0 || flow.USD.out > 0;
  const over = target !== null && flow.netKrw !== null && flow.netKrw > target;
  return (
    <div className="mt-3 py-3" style={{ borderTop: LINE, borderBottom: LINE }} data-testid="payday-invest-compare">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13.5px]" style={{ color: "var(--pq-ivory)" }}>
          투자 몫 {target !== null ? won(target) : "—"}
        </span>
        {over && (
          <span
            className="shrink-0 rounded-full px-2 py-0.5 text-[11px]"
            style={{ color: "var(--pq-bronze)", border: "1px solid var(--pq-bronze)" }}
          >
            몫보다 많음
          </span>
        )}
      </div>
      <p className="mt-1 text-[13px] tabular-nums" style={{ color: "var(--pq-ivory)" }}>
        이번 주기 체결로 넣은 돈{" "}
        {flow.netKrw === null ? "— (환율을 불러오지 못했어요)" : `약 ${won(flow.netKrw)}`}
      </p>
      {/* Each "label amount" pair stays on one line at phone width. */}
      <p className="mt-1 text-[12px] tabular-nums" style={{ color: DIM }}>
        <span className="whitespace-nowrap">원화 산 금액 {won(flow.KRW.in)}</span>
        {" · "}
        <span className="whitespace-nowrap">판 금액 {won(flow.KRW.out)}</span>
        {hasUsd && (
          <>
            {" · "}
            <span className="whitespace-nowrap">
              달러 산 금액 ${flow.USD.in.toLocaleString("en-US", { maximumFractionDigits: 2 })}
            </span>
            {" · "}
            <span className="whitespace-nowrap">
              판 금액 ${flow.USD.out.toLocaleString("en-US", { maximumFractionDigits: 2 })}
            </span>
          </>
        )}
      </p>
      <Note>
        넣은 돈 = 산 금액 − 판 금액. 이 서비스에 기록된 체결만 더한 대략값이에요
        {hasUsd ? " (달러는 오늘 환율로 환산)" : ""}. 은행·카드 내역과 가져오기 대기 중인 체결은 들어가지
        않아요.
        {flow.truncated ? ` 최근 ${TRADE_FETCH_LIMIT}건까지만 셌어요.` : ""}
      </Note>
    </div>
  );
}

/* ── last cycle look-back ──────────────────────────────────────────────── */

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
    <div className="mt-4" data-testid="payday-review">
      <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
        지난 주기 돌아보기 · {shortDate(plan.start)}부터
      </div>
      <Note>투자는 체결 기록으로 자동으로 보여 드려요. 나머지는 내가 기억하는 대로 골라 주세요.</Note>
      <ul className="mt-1">
        {parts.map((k) => (
          <li key={k} className="flex flex-wrap items-center justify-between gap-2 py-2" style={{ borderBottom: LINE }}>
            <span className="text-[13px]" style={{ color: "var(--pq-ivory)" }}>
              {PART_LABEL[k]} {won(plan.parts[k] ?? 0)}
            </span>
            <span className="flex gap-1.5" role="group" aria-label={`${PART_LABEL[k]} 돌아보기`}>
              {(Object.keys(REVIEW_LABEL) as PartReview[]).map((r) => {
                const on = review[k] === r;
                return (
                  <button
                    key={r}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setReview((cur) => ({ ...cur, [k]: r }))}
                    className="rounded-full px-2.5 py-0.5 text-[12px]"
                    style={{
                      color: on ? "var(--pq-ink)" : DIM,
                      background: on ? "var(--pq-bronze)" : "transparent",
                      border: on ? "1px solid var(--pq-bronze)" : LINE,
                    }}
                  >
                    {REVIEW_LABEL[r]}
                  </button>
                );
              })}
            </span>
          </li>
        ))}
      </ul>
      <PrimaryButton className="mt-3" disabled={Object.keys(review).length === 0} onClick={() => onSave(review)}>
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
      : { className: "", style: undefined };

  const storageNote = (
    <Note>
      금액은 이 기기(브라우저)에만 저장되고 서버로 보내지 않아요. 그래서 다른 기기에서는 보이지 않고,
      브라우저 데이터를 지우면 함께 지워져요.
    </Note>
  );

  // ── no payday yet ──
  if (store.payday === null || editingPayday) {
    return (
      <section {...frame} aria-label="월급날 배분" data-testid="payday-plan-card">
        <Kicker>월급날 배분</Kicker>
        <p className="mt-2 text-[13.5px] leading-relaxed" style={{ color: "var(--pq-ivory)" }}>
          월급날마다 생활비·저축·투자·기타로 어떻게 나눌지 적어 두면, 투자 몫은 그 주기에 체결로 넣은 돈과
          나란히 보여 드려요.
        </p>
        <PaydayPicker
          initial={store.payday}
          onSave={(day) => {
            persist({ ...store, payday: day });
            setEditingPayday(false);
          }}
          onCancel={store.payday !== null ? () => setEditingPayday(false) : undefined}
        />
        {storageNote}
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
      <div className="flex items-baseline justify-between gap-3">
        <Kicker>월급날 배분</Kicker>
        <TextButton className="text-[11.5px]" onClick={() => setEditingPayday(true)}>
          매월 {store.payday === 31 ? "말일" : `${store.payday}일`} · 바꾸기
        </TextButton>
      </div>

      {saveFailed && (
        <p className="mt-2 text-[12px]" role="alert" style={{ color: "var(--pq-bronze)" }}>
          이 브라우저가 저장을 막고 있어요(사생활 보호 모드 등). 화면을 닫으면 적은 내용이 사라질 수 있어요.
        </p>
      )}

      {/* last cycle: the investment part is automatic, the rest is self-report */}
      {last && (
        <div className="mt-3">
          {lastNeedsReview ? (
            <ReviewBlock
              plan={last}
              onSave={(review) => persist(upsertCycle(store, { ...last, review }))}
            />
          ) : null}
        </div>
      )}

      {/* this cycle */}
      {!current || editingPlan ? (
        <PlanForm
          cycle={cycle}
          initial={editingPlan ? current : undefined}
          previous={last ?? store.cycles[store.cycles.length - 1]}
          onSave={savePlan}
          onCancel={editingPlan ? () => setEditingPlan(false) : undefined}
        />
      ) : (
        <div className="mt-3" data-testid="payday-plan-current">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[12.5px]" style={{ color: DIM }}>
              이번 주기 {shortDate(cycle.start)} ~ {lastDayBefore(cycle.end)}
            </span>
            <TextButton onClick={() => setEditingPlan(true)}>고치기</TextButton>
          </div>
          <ul className="mt-2" style={{ borderTop: LINE }}>
            {current.income !== null && (
              <li className="flex justify-between py-1.5 text-[13px] tabular-nums" style={{ borderBottom: LINE }}>
                <span style={{ color: DIM }}>들어온 돈</span>
                <span style={{ color: "var(--pq-ivory)" }}>{won(current.income)}</span>
              </li>
            )}
            {PART_KEYS.filter((k) => current.parts[k] !== null).map((k) => (
              <li key={k} className="flex justify-between py-1.5 text-[13px] tabular-nums" style={{ borderBottom: LINE }}>
                <span style={{ color: DIM }}>{PART_LABEL[k]}</span>
                <span style={{ color: "var(--pq-ivory)" }}>{won(current.parts[k] ?? 0)}</span>
              </li>
            ))}
          </ul>
          {current.income !== null && (
            <p className="mt-2 text-[12.5px] tabular-nums" style={{ color: DIM }}>
              {(unassigned(current) ?? 0) >= 0
                ? `아직 정하지 않은 돈 ${won(unassigned(current) ?? 0)}`
                : `들어온 돈보다 ${won(-(unassigned(current) ?? 0))} 더 나눴어요`}
            </p>
          )}
          {current.parts.invest !== null && (
            <InvestComparison plan={current} rows={rows} end={cycle.end} fx={fx} />
          )}
        </div>
      )}

      {/* look-back: last and earlier cycles, as the user left them */}
      {(last || earlier.length > 0) && (
        <details className="mt-4">
          <summary className="cursor-pointer text-[12.5px]" style={{ color: DIM }}>
            지난 주기 보기
          </summary>
          <ul className="mt-2" style={{ borderTop: LINE }}>
            {[...(last ? [last] : []), ...earlier].map(
              (plan) => {
                // A stored start is a payday, so the cycle it opens ends at
                // the next payday (if the payday was changed since, at the
                // next one under the current setting — close enough here).
                const end = cycleFor(plan.start, store.payday ?? 1).end;
                const flow = rows ? cycleFlow(rows, plan.start, end, fx) : null;
                return (
                  <li key={plan.start} className="py-2 text-[12.5px] tabular-nums" style={{ borderBottom: LINE }}>
                    <div style={{ color: "var(--pq-ivory)" }}>
                      {shortDate(plan.start)}부터 · 나눈 돈 {won(partsTotal(plan.parts))}
                    </div>
                    <div className="mt-0.5" style={{ color: DIM }}>
                      {plan.parts.invest !== null && `투자 몫 ${won(plan.parts.invest)}`}
                      {flow && flow.netKrw !== null && !flow.truncated && ` · 체결로 넣은 돈 약 ${won(flow.netKrw)}`}
                      {REVIEWED_PARTS.filter((k) => plan.review?.[k]).map(
                        (k) => ` · ${PART_LABEL[k]} ${REVIEW_LABEL[plan.review![k]!]}`,
                      )}
                    </div>
                  </li>
                );
              },
            )}
          </ul>
        </details>
      )}

      {storageNote}
      <TextButton
        className="mt-1 text-[11.5px]"
        onClick={() => {
          if (typeof window !== "undefined" && !window.confirm("이 기기에 저장된 월급날 배분을 모두 지울까요?")) return;
          clearStore(userId);
          setStore({ v: 1, payday: null, cycles: [] });
        }}
      >
        이 기기에서 지우기
      </TextButton>
    </section>
  );
}

export default PaydayPlanCard;
