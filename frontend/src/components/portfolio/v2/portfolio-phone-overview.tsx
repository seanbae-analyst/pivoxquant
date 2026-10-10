"use client";

/**
 * <PortfolioPhoneOverview /> — the 현황 page of the phone /portfolio.
 *
 * 2026-10-10 (CEO "포트폴리오 … 너무 웹사이트 같음 앱처럼"). This page used to
 * be the desktop hero squeezed down: a serif paragraph ("7종목 관측 · 취득금액
 * USD … · 현금 비중 71.6%.") over a KPI deck, then the seed-capital settings
 * form inline in a bordered card, with the sector donut in a boxed card on a
 * page of its own. A web page's editorial blocks, stacked.
 *
 * Now it is grouped list sections, the way a finance app shows an account:
 *
 *   요약       보유 종목 · 현금 비중 · 올해 실현 손익 (+ 오늘 / 평가 손익 /
 *              마지막 관측 when the vendor gate is on)
 *   자산 흐름  the equity curve (gate on only — passed in, unchanged)
 *   섹터 구성  one stacked bar + legend list (SectorDonutBlock variant="plain")
 *   시드 자본  one row with the current amounts → a bottom sheet holding the
 *              same CapitalCardV2 form (variant="sheet")
 *
 * Numbers come from the hero's own helpers (pnlContext / splitPnlLines /
 * realizedPnlLines), so USD and KRW stay separate exactly as on desktop and
 * the gate-off page shows no figure that needs a vendor price. The cost-basis
 * clarifier is the same i18n string the hero uses.
 *
 * Legal: observational labels only (the 추가 / 정리 vocabulary elsewhere on
 * this screen); no trade-verb labels, nothing that tells the reader what to do.
 * DisclaimerBanner is mounted by (dashboard)/layout.tsx — not here.
 */

import * as React from "react";
import { ChevronRight } from "lucide-react";

import { Caption } from "@/components/ui/editorial";
import { Sheet } from "@/components/ui/sheet";
import { CapitalCardV2 } from "@/components/settings/v2/capital-card-v2";
import { useAuth } from "@/lib/auth";
import { fmtMoneyPlain } from "@/lib/format";
import { useLocale } from "@/lib/locale";
import {
  pnlContext,
  realizedPnlLines,
  relativeTime,
  signColor,
  splitPnlLines,
  type PnlLine,
  type PortfolioHeroV2Props,
} from "./portfolio-hero-v2";

interface PortfolioPhoneOverviewProps {
  /** The same props object the desktop hero receives. */
  hero: PortfolioHeroV2Props;
  /** Equity curve (null with the vendor gate off). */
  curve: React.ReactNode;
  /** Sector composition, already in its phone variant. */
  sectors: React.ReactNode;
  /** FX attribution + foot signature — the end of the page. */
  footer?: React.ReactNode;
}

export function PortfolioPhoneOverview({ hero, curve, sectors, footer }: PortfolioPhoneOverviewProps) {
  const { locale, t } = useLocale();
  const { user } = useAuth();
  const [capitalOpen, setCapitalOpen] = React.useState(false);
  const {
    marketDataDisplay = true,
    loading,
    positionCount,
    cashPct,
    lastReconciledAt,
  } = hero;
  const ctx = pnlContext(hero);
  const isEmptyBook = !loading && positionCount === 0;
  const hasCash = !loading && typeof cashPct === "number" && Number.isFinite(cashPct);

  // Same "only when there is a figure" rule as the hero's KPI deck.
  const showPnl =
    !isEmptyBook &&
    (marketDataDisplay
      ? hero.todayPnl != null || hero.unrealized != null || hero.realizedYtd != null
      : hero.realizedYtd != null || hero.realizedUsd != null || hero.realizedKrw != null);

  const capUsd = Number(user?.available_capital ?? 0) || 0;
  const capKrw = Number(user?.available_capital_krw ?? 0) || 0;
  const capitalParts = [
    capUsd > 0 ? fmtMoneyPlain(capUsd, "USD", 0) : null,
    capKrw > 0 ? fmtMoneyPlain(capKrw, "KRW", 0) : null,
  ].filter(Boolean) as string[];

  return (
    <div className="flex flex-col gap-7" data-testid="portfolio-phone-overview">
      <section aria-labelledby="pf-ov-summary">
        <SectionLabel id="pf-ov-summary">요약</SectionLabel>
        <dl className="-mx-4 border-y border-[var(--pq-ivory-line)]">
          <Row label="보유 종목" value={loading ? "—" : `${positionCount ?? "—"}종목`} first />
          {hasCash && !isEmptyBook ? (
            <Row label="현금 비중" value={`${(cashPct as number).toFixed(1)}%`} />
          ) : null}
          {showPnl && marketDataDisplay ? (
            <>
              <Row
                label="오늘"
                value={<Lines lines={splitPnlLines(hero.todayPnlUsd, hero.todayPnlKrw, hero.todayPnl, ctx)} fallback={hero.todayPnl} />}
                sub={
                  hero.todayPnlPct != null && Number.isFinite(hero.todayPnlPct)
                    ? `${hero.todayPnlPct >= 0 ? "+" : ""}${hero.todayPnlPct.toFixed(2)}%`
                    : undefined
                }
              />
              <Row
                label="평가 손익"
                value={<Lines lines={splitPnlLines(hero.unrealizedUsd, hero.unrealizedKrw, hero.unrealized, ctx)} fallback={hero.unrealized} />}
              />
            </>
          ) : null}
          {showPnl ? (
            <Row
              label="올해 실현 손익"
              value={<Lines lines={realizedPnlLines(hero.realizedUsd, hero.realizedKrw, hero.realizedYtd, ctx)} fallback={hero.realizedYtd} />}
            />
          ) : null}
          {marketDataDisplay && !isEmptyBook ? (
            <Row
              label="마지막 관측"
              value={loading ? "—" : relativeTime(lastReconciledAt, locale, t("dashboard.portfolio.hero.never"))}
            />
          ) : null}
        </dl>
        {!marketDataDisplay && !isEmptyBook ? (
          <div data-testid="portfolio-cost-basis-note" className="mt-2">
            <Caption>{t("journal.concentrationMirror.costBasisNote")}</Caption>
          </div>
        ) : null}
      </section>

      {curve ? (
        <section aria-labelledby="pf-ov-curve">
          <SectionLabel id="pf-ov-curve">자산 흐름</SectionLabel>
          {curve}
        </section>
      ) : null}

      <section aria-labelledby="pf-ov-sectors">
        <SectionLabel id="pf-ov-sectors">섹터 구성</SectionLabel>
        {sectors}
      </section>

      <section aria-labelledby="pf-ov-capital">
        <SectionLabel id="pf-ov-capital">시드 자본</SectionLabel>
        <div className="-mx-4 border-y border-[var(--pq-ivory-line)]">
          <button
            type="button"
            onClick={() => setCapitalOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={capitalOpen}
            className="flex min-h-[56px] w-full items-center gap-3 px-4 py-3 text-left transition-colors active:bg-[var(--pq-ivory-line-faint)] [-webkit-tap-highlight-color:transparent]"
            data-testid="portfolio-capital-open"
          >
            <span className="flex-1 text-pq-body text-[var(--pq-ivory)]">투자 가능 자본</span>
            <span className="text-right font-mono text-pq-body-sm tabular-nums text-[var(--pq-ivory-mid)]">
              {capitalParts.length > 0
                ? capitalParts.map((c) => (
                    <span key={c} className="block whitespace-nowrap">
                      {c}
                    </span>
                  ))
                : "설정 안 됨"}
            </span>
            <ChevronRight aria-hidden className="h-4 w-4 shrink-0 text-[var(--pq-ivory-dim)]" />
          </button>
        </div>
        <p className="mt-2 text-pq-caption leading-[1.5] text-[var(--pq-ivory-dim)]">
          현금 비중과 기록 뒤 남는 금액을 계산하는 기준입니다.
        </p>
      </section>

      <Sheet
        open={capitalOpen}
        onClose={() => setCapitalOpen(false)}
        ariaLabelledBy="pf-capital-sheet-title"
        testId="portfolio-capital-sheet"
      >
        <div id="pf-capital-sheet-title" className="pb-3 pt-1 font-serif text-pq-h4 text-[var(--pq-ivory)]">
          시드 자본
        </div>
        <section aria-label="시드 자본">
          <CapitalCardV2 variant="sheet" onSaved={() => setCapitalOpen(false)} />
        </section>
      </Sheet>

      {footer}
    </div>
  );
}

function SectionLabel({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="mb-2 text-pq-body-sm font-medium text-[var(--pq-ivory-mid)]">
      {children}
    </h2>
  );
}

function Row({
  label,
  value,
  sub,
  first = false,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  first?: boolean;
}) {
  return (
    <div
      className={`flex min-h-[52px] items-center justify-between gap-4 px-4 py-3 ${
        first ? "" : "border-t border-[var(--pq-ivory-line)]"
      }`}
    >
      <dt className="text-pq-body text-[var(--pq-ivory-strong)]">{label}</dt>
      <dd className="text-right font-mono text-pq-body tabular-nums text-[var(--pq-ivory)]">
        {value}
        {sub ? <div className="mt-0.5 text-pq-caption text-[var(--pq-ivory-dim)]">{sub}</div> : null}
      </dd>
    </div>
  );
}

/** P&L lines, one per currency — the fallback line takes its sign colour. */
function Lines({ lines, fallback }: { lines: PnlLine[]; fallback: number | undefined }) {
  return (
    <>
      {lines.map((l) => (
        <div key={l.key} style={{ color: l.color ?? signColor(fallback) }}>
          {l.text}
        </div>
      ))}
    </>
  );
}

export default PortfolioPhoneOverview;
