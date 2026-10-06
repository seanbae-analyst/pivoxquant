"use client";

/**
 * <FilingFactsModalV2 /> — 보유 종목 하나의 공시 숫자 (종목 상세).
 *
 * GET API.portfolio.filings(id) → 정기공시 재무제표(미국 SEC EDGAR · 한국 DART)를
 * 그대로 계산한 숫자와, 유저 본인의 평단으로 나눈 PER. 시세를 한 번도 읽지
 * 않으므로 MARKET_DATA_DISPLAY 플래그와 무관하게 열린다.
 *
 * 숫자만 보여준다 — 점수·등급·색으로 된 판정 없음 (DECISIONS.md 점수화 폐기).
 * 흑자/적자도 같은 중립색이다. 해석은 유저 몫.
 *
 * Shell copied from <ObservationNoteModalV2 /> so /portfolio has one modal language.
 */

import * as React from "react";
import useSWR from "swr";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { displayTicker, fmtPct } from "@/lib/format";
import { API } from "@/lib/endpoints";

interface Quarter {
  end: string;
  revenue: number | null;
  net_income: number | null;
}

export interface FilingFacts {
  source: "SEC EDGAR" | "DART";
  entity_name: string;
  currency: "USD" | "KRW";
  as_of: string | null;
  quarters: Quarter[];
  revenue_ttm: number | null;
  net_income_ttm: number | null;
  net_income_streak: { kind: "profit" | "loss"; quarters: number } | null;
  net_income_per_share_ttm: number | null;
  cash: { as_of: string; value: number; includes_short_term: boolean } | null;
  operating_cf_ttm: number | null;
  cash_months_at_ttm_burn: number | null;
  liabilities_to_equity: { as_of: string; value: number } | null;
  shares_change_1y: { from: string; to: string; pct: number } | null;
}

export type FilingsResponse =
  | {
      ticker: string;
      available: true;
      avg_cost: number;
      pe_at_cost: number | null;
      facts: FilingFacts;
    }
  | {
      ticker: string;
      available: false;
      reason: "unsupported_market" | "source_unconfigured" | "no_filings";
    };

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.error || r.statusText || `HTTP ${r.status}`);
  }
  return r.json();
};

const UNAVAILABLE: Record<string, string> = {
  unsupported_market: "미국·한국 상장 종목만 공시 숫자를 볼 수 있습니다.",
  source_unconfigured: "한국 공시(DART) 연결이 아직 설정되지 않았습니다.",
  no_filings: "이 종목의 정기공시 재무 숫자를 찾지 못했습니다.",
};

/** 큰 금액을 읽을 수 있게 — USD: $1.23B / $45.6M, KRW: 1.2조 원 / 345억 원. */
export function fmtAmount(v: number | null | undefined, currency: "USD" | "KRW"): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (currency === "KRW") {
    if (a >= 1e12) return `${sign}${(a / 1e12).toFixed(1)}조 원`;
    if (a >= 1e8) return `${sign}${Math.round(a / 1e8).toLocaleString("ko-KR")}억 원`;
    return `${sign}${Math.round(a).toLocaleString("ko-KR")}원`;
  }
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  return `${sign}$${Math.round(a).toLocaleString("en-US")}`;
}

function fmtPrice(v: number, currency: "USD" | "KRW"): string {
  return currency === "KRW"
    ? `${Math.round(v).toLocaleString("ko-KR")}원`
    : `$${v.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

const quarterLabel = (end: string) => end.slice(0, 7);

export interface FilingFactsModalV2Props {
  open: boolean;
  positionId: number | string | null;
  symbol: string | null;
  name?: string | null;
  onClose: () => void;
}

export function FilingFactsModalV2({
  open,
  positionId,
  symbol,
  name,
  onClose,
}: FilingFactsModalV2Props) {
  if (!open || !symbol || positionId === null) return null;
  // 열렸을 때만 마운트 — 닫힌 모달은 SWR·키 리스너를 하나도 돌리지 않는다.
  return (
    <FilingFactsDialog positionId={positionId} symbol={symbol} name={name} onClose={onClose} />
  );
}

function FilingFactsDialog({
  positionId,
  symbol,
  name,
  onClose,
}: {
  positionId: number | string;
  symbol: string;
  name?: string | null;
  onClose: () => void;
}) {
  const headlineId = "filing-facts-v2-headline";
  const trapRef = useFocusTrap<HTMLDivElement>(true);
  const { data, error, isLoading } = useSWR<FilingsResponse>(
    API.portfolio.filings(positionId),
    fetcher,
    { revalidateOnFocus: false },
  );

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={headlineId}
      className="pq-modal-v2"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(5,5,5,0.78)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "10vh 16px calc(24px + env(safe-area-inset-bottom, 0px))",
        overflowY: "auto",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={trapRef}
        style={{
          width: "100%",
          maxWidth: 560,
          background: "rgba(184,149,106,0.025)",
          border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          borderRadius: "var(--pq-radius-card, 4px)",
          padding: "32px 24px",
          color: "var(--pq-ivory)",
        }}
      >
        <div style={{ marginBottom: 20 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Filings · 공시 숫자
          </div>
          <h2
            id={headlineId}
            className="font-display"
            style={{
              fontSize: "var(--pq-text-h3)",
              lineHeight: 1.15,
              fontWeight: 500,
              letterSpacing: "-0.015em",
              margin: 0,
            }}
          >
            {displayTicker(symbol, name ?? "")}
          </h2>
        </div>

        {isLoading && <Muted>공시를 불러오는 중…</Muted>}
        {error && <Muted>공시 숫자를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.</Muted>}
        {data && !data.available && <Muted>{UNAVAILABLE[data.reason] ?? UNAVAILABLE.no_filings}</Muted>}
        {data && data.available && (
          <FactsBody
            facts={data.facts}
            avgCost={data.avg_cost}
            peAtCost={data.pe_at_cost}
          />
        )}

        <div style={{ marginTop: 20, textAlign: "right" }}>
          <button
            type="button"
            onClick={onClose}
            className="font-mono uppercase"
            style={{
              background: "transparent",
              border: "1px solid var(--pq-ivory-line)",
              borderRadius: "var(--pq-radius-cta, 2px)",
              color: "var(--pq-ivory-dim)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              padding: "8px 14px",
              cursor: "pointer",
            }}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ color: "var(--pq-ivory-dim)", fontSize: "var(--pq-text-body)", margin: 0 }}>
      {children}
    </p>
  );
}

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 16,
        padding: "10px 0",
        borderBottom: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
      }}
    >
      <div style={{ color: "var(--pq-ivory-dim)", fontSize: "var(--pq-text-body)" }}>
        {label}
        {note && (
          <div style={{ fontSize: "var(--pq-text-eyebrow)", marginTop: 2, opacity: 0.8 }}>
            {note}
          </div>
        )}
      </div>
      <div
        style={{
          textAlign: "right",
          fontVariantNumeric: "tabular-nums",
          color: "var(--pq-ivory-strong)",
          fontSize: "var(--pq-text-body)",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </div>
    </div>
  );
}

export function FactsBody({
  facts: f,
  avgCost,
  peAtCost,
}: {
  facts: FilingFacts;
  avgCost: number;
  peAtCost: number | null;
}) {
  const cur = f.currency;
  const loss = f.net_income_ttm !== null && f.net_income_ttm <= 0;

  const pe = peAtCost !== null
    ? `${peAtCost.toFixed(1)}배`
    : loss
      ? "해당 없음 · 최근 4분기 적자"
      : "계산 불가";

  const streak = f.net_income_streak
    ? `${f.net_income_streak.quarters}분기 연속 ${f.net_income_streak.kind === "profit" ? "흑자" : "적자"}`
    : "—";

  const cashLabel = f.cash?.includes_short_term ? "현금 + 단기투자" : "현금성자산";

  return (
    <div>
      <Row
        label={`내 평단(${fmtPrice(avgCost, cur)}) 기준 PER`}
        value={pe}
        note="평단 ÷ 최근 4분기 주당순이익"
      />
      <Row label="최근 4분기 매출" value={fmtAmount(f.revenue_ttm, cur)} />
      <Row
        label="최근 4분기 순이익"
        value={fmtAmount(f.net_income_ttm, cur)}
        note={streak}
      />
      {f.cash && (
        <Row
          label={cashLabel}
          value={fmtAmount(f.cash.value, cur)}
          note={`${f.cash.as_of} 기준`}
        />
      )}
      {f.cash_months_at_ttm_burn !== null && (
        <Row
          label="최근 4분기 속도로 나눈 현금"
          value={`약 ${Math.round(f.cash_months_at_ttm_burn)}개월분`}
          note={`영업현금흐름 ${fmtAmount(f.operating_cf_ttm, cur)} · 현금 외 자산·추가 조달 미반영`}
        />
      )}
      {f.liabilities_to_equity && (
        <Row
          label="부채 ÷ 자본"
          value={`${Math.round(f.liabilities_to_equity.value * 100)}%`}
          note={`${f.liabilities_to_equity.as_of} 기준`}
        />
      )}
      {f.shares_change_1y && (
        <Row
          label="주식 수 1년 변화"
          value={fmtPct(f.shares_change_1y.pct * 100)}
          note="보통주 분기 가중평균 · 주식 종류 전환도 포함될 수 있음"
        />
      )}

      {f.quarters.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              color: "var(--pq-ivory-dim)",
              marginBottom: 8,
            }}
          >
            분기별 · 매출 / 순이익
          </div>
          {/* 375px 에서 표가 넘치지 않게 가로 스크롤은 표 안에서만. */}
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "var(--pq-text-eyebrow)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              <thead>
                <tr style={{ color: "var(--pq-ivory-dim)" }}>
                  <th style={{ textAlign: "left", padding: "6px 4px", fontWeight: 400 }}>분기 말</th>
                  <th style={{ textAlign: "right", padding: "6px 4px", fontWeight: 400 }}>매출</th>
                  <th style={{ textAlign: "right", padding: "6px 4px", fontWeight: 400 }}>순이익</th>
                </tr>
              </thead>
              <tbody>
                {f.quarters.map((q) => (
                  <tr key={q.end} style={{ color: "var(--pq-ivory-strong)" }}>
                    <td style={{ padding: "6px 4px" }}>{quarterLabel(q.end)}</td>
                    <td style={{ padding: "6px 4px", textAlign: "right" }}>{fmtAmount(q.revenue, cur)}</td>
                    <td style={{ padding: "6px 4px", textAlign: "right" }}>{fmtAmount(q.net_income, cur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p
        style={{
          marginTop: 16,
          marginBottom: 0,
          color: "var(--pq-ivory-dim)",
          fontSize: "var(--pq-text-eyebrow)",
          lineHeight: 1.6,
        }}
      >
        출처: {f.source === "DART" ? "금융감독원 전자공시(DART)" : "미국 SEC EDGAR"} 정기공시
        {f.as_of ? ` · 최근 분기 ${f.as_of}` : ""}. 시세는 쓰지 않았고, 공시 숫자를 산수로만 정리했습니다.
        공시 원문과 다를 수 있으니 중요한 숫자는 원문으로 확인하세요.
      </p>
    </div>
  );
}

export default FilingFactsModalV2;
