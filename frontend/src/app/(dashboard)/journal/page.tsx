"use client";

/**
 * /journal — Decision Journal (Pre-Trade reflection feed).
 *
 * "User as CFO": a reverse-chronological feed of the user's OWN pre-trade
 * reflections — the rationale + 7-question devil's-advocate snapshot they
 * wrote before adding/trimming a position, plus whether they proceeded or
 * cancelled. The point is self-review: "look back at how I decided."
 *
 * Read-only. The backend never executed a trade — each row is a "user
 * finished thinking" record (services/pre_trade/friction.py). This page is
 * INFORMATIONAL, not a recommendation and not a trade-execution log.
 *
 * Compliance posture (자본시장법 §6 / §101):
 *   - intended_side BUY/SELL is NEVER surfaced raw. Rendered through
 *     `@/lib/pre-trade` sideLabel as "Long Entry · 진입" / "Position Exit · 정리".
 *   - No 추천/조언 language. DisclaimerBanner mounted at the page head.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT (no italic headings).
 * KR colour convention: proceeded = neutral ivory, cancelled = dimmed.
 * Carmine/indigo reserved for price direction, not used for status here.
 */

import {
  useState,
  useCallback,
  useMemo,
  useSyncExternalStore,
} from "react";
import Link from "next/link";
import { Briefcase, NotebookPen, ChevronDown } from "lucide-react";
import { useLocale, useT } from "@/lib/locale";
import { usePreTradeJournal, useObservationNotes } from "@/lib/hooks";
import { displayName, normalizeTicker, parseIsoUtc } from "@/lib/format";
import { sideLabel } from "@/lib/pre-trade";
import { relativeTime } from "@/lib/relative-time";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  RuledKicker,
  Caption,
  EditorialHead,
  FootSignature,
} from "@/components/ui/editorial";
import { HoldingMirror } from "@/components/journal/holding-mirror";
import { ConcentrationMirror } from "@/components/journal/concentration-mirror";
import { ProfitLossMirror } from "@/components/journal/profit-loss-mirror";
import { TurnoverMirror } from "@/components/journal/turnover-mirror";
import { AveragingDownMirror } from "@/components/journal/averaging-down-mirror";
import { FrictionOutcomeMirror } from "@/components/journal/friction-outcome-mirror";
import { StorageProofToggle } from "@/components/journal/storage-proof-toggle";
import { WeeklyPulseSection } from "@/components/journal/weekly-pulse-section";
import { ImportInbox } from "@/components/journal/import-inbox";
import { ObservationNoteComposer } from "@/components/journal/observation-note-composer";
import { ObservationNoteCard } from "@/components/journal/observation-note-card";
import {
  entryTimestamp,
  filterTimeline,
  mergeTimeline,
  recentNoteSummary,
  type TimelineFilter,
} from "./timeline";
import type { PreTradeReflection } from "@/lib/types";

/* ────────────────────────────────────────────────────────────────────────
 * Helpers
 * ────────────────────────────────────────────────────────────────────── */

/**
 * Re-exported from `./timeline`, where it now lives so the merge can read it
 * without importing this page (six mirrors + weekly pulse + import inbox).
 * `__tests__/journal-helpers.test.ts` imports it from here.
 */
export { entryTimestamp };

/** Absolute KST-rendered date for the inline metadata row. */
export function absoluteDate(iso: string | null): string {
  const d = parseIsoUtc(iso);
  if (!d) return "";
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    // Pin to KST so the date doesn't roll back/forward a day for viewers in
    // other timezones (2026-05-26 F#4 fix). parseIsoUtc (lib/format) reads
    // naive backend timestamps as UTC before zone conversion.
    timeZone: "Asia/Seoul",
  });
}

export type StatusKind = "proceeded" | "cancelled" | "pending";

export function statusKind(r: PreTradeReflection): StatusKind {
  if (r.status === "proceeded") return "proceeded";
  if (r.status === "cancelled") return "cancelled";
  return "pending"; // pending | ready
}

// STATUS_COPY is now resolved via useT inside StatusChip

/* ────────────────────────────────────────────────────────────────────────
 * Timeline filter — 전체 · 멈춤 기록 · 관찰 노트
 *
 * The chip choice is a per-device preference, so it is remembered in
 * localStorage. It is read through useSyncExternalStore rather than a
 * useState + mount effect: the server render has no localStorage, and this
 * is exactly the "read a client-only external store" case React added the
 * hook for (same pattern as the persona hint cache in
 * components/pre-trade/pre-trade-friction-core.tsx). Every storage access is
 * wrapped — Safari private mode throws on read as well as write.
 * ────────────────────────────────────────────────────────────────────── */

const FILTER_STORAGE_KEY = "pq:journal:timeline-filter";
const FILTER_VALUES: readonly TimelineFilter[] = ["all", "reflection", "note"];

const filterListeners = new Set<() => void>();
/** Set by a click; preferred over storage so a blocked write still applies. */
let filterOverride: TimelineFilter | null = null;

function subscribeFilter(onChange: () => void): () => void {
  filterListeners.add(onChange);
  return () => {
    filterListeners.delete(onChange);
  };
}

function getFilterSnapshot(): TimelineFilter {
  if (filterOverride) return filterOverride;
  try {
    const raw = window.localStorage.getItem(FILTER_STORAGE_KEY);
    const found = FILTER_VALUES.find((v) => v === raw);
    if (found) return found;
  } catch {
    /* storage unavailable — fall through to the default */
  }
  return "all";
}

/** SSR + first paint: always 전체, so hydration matches the server HTML. */
function getServerFilterSnapshot(): TimelineFilter {
  return "all";
}

function setTimelineFilter(next: TimelineFilter): void {
  filterOverride = next;
  try {
    window.localStorage.setItem(FILTER_STORAGE_KEY, next);
  } catch {
    /* storage unavailable — the in-memory override still holds this session */
  }
  filterListeners.forEach((fn) => fn());
}

/* ────────────────────────────────────────────────────────────────────────
 * Status chip — neutral tone (no carmine), cancelled dimmed.
 * ────────────────────────────────────────────────────────────────────── */

function StatusChip({ kind }: { kind: StatusKind }) {
  const t = useT();
  const dimmed = kind === "cancelled";
  const koLabel =
    kind === "proceeded"
      ? t("journal.page.statusProceeded")
      : kind === "cancelled"
        ? t("journal.page.statusCancelled")
        : t("journal.page.statusPending");
  const enLabel =
    kind === "proceeded"
      ? t("journal.page.statusProceededEn")
      : kind === "cancelled"
        ? t("journal.page.statusCancelledEn")
        : t("journal.page.statusPendingEn");
  return (
    <span
      className="font-mono text-pq-caption uppercase"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "2px 8px",
        borderRadius: 2,
        letterSpacing: "0.16em",
        border: "0.5px solid var(--pq-ivory-line)",
        background: "var(--pq-ivory-line-faint)",
        color: dimmed ? "var(--pq-ivory-faint)" : "rgba(245,240,232,0.82)",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 5,
          height: 5,
          borderRadius: "50%",
          background:
            kind === "proceeded"
              ? "var(--pq-bronze)"
              : kind === "cancelled"
                ? "rgba(245,240,232,0.3)"
                : "rgba(245,240,232,0.55)",
        }}
      />
      {koLabel}
      <span style={{ opacity: 0.5 }}>· {enLabel}</span>
    </span>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Observed context — "그때 무엇을 보고 있었나" one-liner
 * ────────────────────────────────────────────────────────────────────── */

function ObservedContextLine({
  ctx,
}: {
  ctx: NonNullable<PreTradeReflection["observed_context"]>;
}) {
  const parts: string[] = [];
  if (ctx.signal) {
    parts.push(
      typeof ctx.score === "number"
        ? `${ctx.signal} ${Math.round(ctx.score)}`
        : ctx.signal,
    );
  }
  if (typeof ctx.vix === "number") parts.push(`VIX ${ctx.vix}`);
  if (typeof ctx.change_1h_pct === "number") {
    parts.push(`1H ${ctx.change_1h_pct > 0 ? "+" : ""}${ctx.change_1h_pct}%`);
  }
  if (parts.length === 0) return null;
  return (
    <p
      className="mt-2 font-mono text-pq-caption text-[var(--pq-ivory-faint)]"
      data-testid="observed-context"
    >
      <span className="uppercase tracking-[0.14em] text-[var(--pq-bronze-light)]">
        진입 시점 관측 · At entry
      </span>
      <span className="mx-2 opacity-40">—</span>
      {parts.join(" · ")}
    </p>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Journal entry card
 * ────────────────────────────────────────────────────────────────────── */

function JournalEntry({ r }: { r: PreTradeReflection }) {
  const { locale } = useLocale();
  const t = useT();
  const [open, setOpen] = useState(false);

  const ts = entryTimestamp(r);
  const name = displayName(r.intended_ticker, r.intended_name);
  const bareTicker = normalizeTicker(r.intended_ticker);
  // Only show the ticker sub when the resolved name is NOT just the bare code.
  const showTickerSub =
    bareTicker.length > 0 && name.toUpperCase() !== bareTicker.toUpperCase();

  const sideText = r.intended_side ? sideLabel(r.intended_side) : null;
  const kind = statusKind(r);
  const hasDevilsAdvocate =
    typeof r.devil_advocate_seen === "string" &&
    r.devil_advocate_seen.trim().length > 0;

  const dimmed = kind === "cancelled";

  return (
    <article
      className="rounded-[2px] border p-4 sm:p-5 transition-colors"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
        opacity: dimmed ? 0.72 : 1,
      }}
    >
      {/* Header: name + ticker sub + status */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <EditorialHead as="h3" size={26} style={{ wordBreak: "keep-all" }}>
            {name}
          </EditorialHead>
          {showTickerSub && (
            <span className="font-mono text-pq-caption uppercase tracking-[0.14em] text-[var(--pq-ivory-faint)]">
              {bareTicker}
            </span>
          )}
        </div>
        <StatusChip kind={kind} />
      </div>

      {/* Meta row: intent + shares + time */}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {sideText && (
          <span className="font-mono text-pq-caption uppercase tracking-[0.14em] text-[var(--pq-bronze-light)]">
            {sideText}
          </span>
        )}
        {typeof r.intended_shares === "number" && r.intended_shares > 0 && (
          <span className="font-mono text-pq-caption text-[var(--pq-ivory-dim)]">
            {r.intended_shares.toLocaleString()}
            <span className="ml-1 opacity-60">
              {t("journal.page.sharesUnit")}
            </span>
          </span>
        )}
        {ts && (
          <span className="font-mono text-pq-caption text-[var(--pq-ivory-faint)]">
            {relativeTime(ts, locale, { verbose: true })}
            <span className="mx-1.5 opacity-40">·</span>
            <span className="opacity-70">{absoluteDate(ts)}</span>
          </span>
        )}
      </div>

      {/* Rationale */}
      {r.rationale.trim().length > 0 && (
        <p
          className="mt-3 font-serif text-pq-deck"
          style={{
            lineHeight: 1.6,
            color: "var(--pq-ivory-strong)",
            wordBreak: "keep-all",
          }}
        >
          {r.rationale}
        </p>
      )}

      {/* Observed context — what the desk was showing at the moment the
          reflection was opened (record-as-spine Phase 2). Factual record
          only: the POSITIVE/NEGATIVE/NEUTRAL label is the legal observation
          surface; no directive fields ever reach this object (§17). */}
      {r.observed_context && <ObservedContextLine ctx={r.observed_context} />}

      {/* Auto-extended cooldown note (volatility context) */}
      {r.auto_extended_reason && (
        <p className="mt-2 font-mono text-pq-caption text-[var(--pq-ivory-faint)]">
          {r.auto_extended_reason}
        </p>
      )}

      {/* 7-question reflection — collapsible */}
      {hasDevilsAdvocate && (
        <div
          className="mt-3 border-t pt-3"
          style={{ borderColor: "var(--pq-ivory-line-soft)" }}
        >
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex w-full items-center gap-2 text-left"
            aria-expanded={open}
          >
            <span className="font-mono text-pq-caption uppercase tracking-[0.18em] text-[var(--pq-bronze-light)]">
              {t("journal.page.devilsAdvocateToggle")}
            </span>
            <ChevronDown
              className="h-3.5 w-3.5 shrink-0 text-[var(--pq-ivory-faint)] transition-transform duration-200"
              style={{ transform: open ? "rotate(180deg)" : undefined }}
            />
          </button>
          {open && (
            <p
              className="mt-2 font-serif text-pq-lead"
              style={{
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                color: "rgba(245,240,232,0.7)",
                wordBreak: "keep-all",
              }}
            >
              {r.devil_advocate_seen}
            </p>
          )}
        </div>
      )}

      {/* "Show, don't tell" — let the user witness their own words as the
          ciphertext stored at rest, rather than asserting privacy in copy. */}
      {r.rationale.trim().length > 0 && (
        <StorageProofToggle reflectionId={r.id} />
      )}
    </article>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * States
 * ────────────────────────────────────────────────────────────────────── */

function LoadingState() {
  return (
    <div className="space-y-4" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-32 animate-pulse rounded-[2px] border"
          style={{
            borderColor: "var(--pq-ivory-line)",
            background: "var(--pq-card-veil)",
          }}
        />
      ))}
    </div>
  );
}

function LoadFailure({ onRetry }: { onRetry: () => void }) {
  const t = useT();
  return (
    <div
      className="rounded-[2px] border p-6 text-center"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <p className="font-serif text-pq-mono-sm text-[rgba(245,240,232,0.7)]">
        {t("journal.page.loadFailure")}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-[2px] border px-4 py-2 font-mono text-pq-caption uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{ borderColor: "var(--pq-ivory-line)" }}
      >
        {t("journal.page.retry")}
      </button>
    </div>
  );
}

function EmptyState() {
  const t = useT();
  return (
    <div
      className="rounded-[2px] border px-6 py-12 text-center"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <NotebookPen
        className="mx-auto h-7 w-7 text-[var(--pq-bronze-light)]"
        aria-hidden="true"
      />
      <p
        className="mx-auto mt-4 max-w-md font-serif text-pq-h6"
        style={{
          lineHeight: 1.6,
          color: "var(--pq-ivory-soft)",
          wordBreak: "keep-all",
        }}
      >
        {t("journal.page.emptyTitle")}
      </p>
      <Caption className="mx-auto mt-2 max-w-md">
        {t("journal.page.emptyDesc")}
      </Caption>
      <Link
        href="/portfolio"
        className="mt-6 inline-flex items-center gap-2 rounded-[2px] border px-5 py-2.5 font-mono text-pq-caption uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{ borderColor: "var(--pq-ivory-line)" }}
      >
        <Briefcase className="h-3.5 w-3.5" aria-hidden="true" />
        {t("journal.page.gotoPortfolio")}
      </Link>
    </div>
  );
}

/** Shown when the feed has rows but the active chip hides all of them. */
function FilterEmptyState({ filter }: { filter: TimelineFilter }) {
  return (
    <div
      className="rounded-[2px] border px-6 py-10 text-center"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <Caption>
        {filter === "note"
          ? "아직 관찰 노트가 없습니다. 위에서 지금 본 것을 적어 두세요."
          : "이 기간에 남긴 멈춤 기록이 없습니다."}
      </Caption>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Filter chips + this-week count
 * ────────────────────────────────────────────────────────────────────── */

const FILTER_LABELS: Record<TimelineFilter, string> = {
  all: "전체",
  reflection: "멈춤 기록",
  note: "관찰 노트",
};

function FilterChips({
  value,
  onChange,
}: {
  value: TimelineFilter;
  onChange: (next: TimelineFilter) => void;
}) {
  return (
    <div
      role="group"
      aria-label="기록 종류"
      className="flex flex-wrap items-center gap-2"
    >
      {FILTER_VALUES.map((v) => {
        const active = v === value;
        return (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            aria-pressed={active}
            className="rounded-[2px] border px-3 py-1.5 font-mono text-pq-caption uppercase tracking-[0.16em] transition-colors"
            style={{
              borderColor: active
                ? "var(--pq-bronze)"
                : "var(--pq-ivory-line)",
              background: active
                ? "var(--pq-card-veil-strong)"
                : "transparent",
              color: active
                ? "var(--pq-bronze-light)"
                : "var(--pq-ivory-dim)",
            }}
          >
            {FILTER_LABELS[v]}
          </button>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Page
 * ────────────────────────────────────────────────────────────────────── */

function JournalContent() {
  const t = useT();
  const { reflections, isLoading, error, mutate } = usePreTradeJournal();
  // Observation notes share the feed (docs/design/
  // observation-notes_2026-09-22.md §5). A notes failure is NOT fatal to the
  // page: the 멈춤 기록 still render, the same way a single mirror failing
  // never takes the journal down.
  const {
    notes,
    isLoading: notesLoading,
    mutate: mutateNotes,
  } = useObservationNotes(50);

  const retry = useCallback(() => {
    void mutate();
    void mutateNotes();
  }, [mutate, mutateNotes]);

  const filter = useSyncExternalStore(
    subscribeFilter,
    getFilterSnapshot,
    getServerFilterSnapshot,
  );

  const entries = useMemo(
    () => mergeTimeline(reflections, notes),
    [reflections, notes],
  );
  const visible = useMemo(
    () => filterTimeline(entries, filter),
    [entries, filter],
  );
  // Trailing 7 days, recomputed whenever the loaded notes change — the clock
  // is read inside recentNoteSummary (see its comment on why 이번 주 means
  // the last 7 days rather than the ISO week).
  const weekly = useMemo(() => recentNoteSummary(notes), [notes]);

  const feedLoading = isLoading || notesLoading;

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      {/* Header */}
      <header className="mb-6">
        <RuledKicker>{t("journal.page.kicker")}</RuledKicker>
        <EditorialHead as="h1" size={32} className="mt-3">
          {t("journal.page.heading")}
        </EditorialHead>
        <Caption className="mt-2 max-w-lg">
          {t("journal.page.headingDesc")}
        </Caption>
        <Link
          href="/journal/import"
          className="mt-3 inline-flex items-center gap-2 font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
        >
          {t("journal.import.importLink")}
        </Link>
      </header>

      {/* Import Inbox — received fills waiting for a "why". A row is not a
          record until the user approves it with a thesis; nothing here feeds
          the mirrors below (docs/product/IMPORT_INBOX_DESIGN.md). */}
      <ErrorBoundary fallback={null}>
        <ImportInbox />
      </ErrorBoundary>

      {/* Legal disclaimer mounted once at the bottom by (dashboard)/layout.tsx
          — no page-level banner here (CEO 2026-05-24: disclaimer only at the
          bottom, every page). */}

      {/* Behavior-mirror section — the disposition + concentration mirrors,
          each with its OWN SWR + loading/error boundary so any single mirror
          failure can never take down the journal feed (or its siblings) below.
          A SINGLE shared behavior-mirror disclaimer is mounted once at the
          section foot (legal-confirmed wording), so a screen with N mirrors
          shows one legal banner — not one per mirror. The disclaimer renders
          unconditionally, independent of each mirror's data/empty/error state,
          and covers any future mirror added to this section (e.g. FOMO). */}
      <section className="mb-8" aria-label={t("journal.page.kicker")}>
        <div className="mb-8">
          <HoldingMirror />
        </div>

        <div className="mb-8">
          <ConcentrationMirror />
        </div>

        <div className="mb-8">
          <ProfitLossMirror />
        </div>

        <div className="mb-8">
          <TurnoverMirror />
        </div>

        <div className="mb-8">
          <AveragingDownMirror />
        </div>

        {/* Friction outcome sits LAST in the section on purpose. The five
            mirrors above read TradeHistory — what you did. This one reads
            PreTradeReflection alongside it, so it is the only one that can
            speak about the trade that did not happen, and it reads best after
            the reader has seen what the executed record looks like.
            (2026-09-02 — until then the module had no UI at all.) */}
        <div className="mb-6">
          <FrictionOutcomeMirror />
        </div>

      </section>

      {/* Composer — the one place a record starts without a trade attached.
          It sits ABOVE the chips on purpose: writing comes before reading
          back (docs/design/observation-notes_2026-09-22.md §5 진입점). */}
      <div className="mb-6">
        <ErrorBoundary fallback={null}>
          <ObservationNoteComposer
            source="journal"
            onCreated={() => {
              void mutateNotes();
            }}
          />
        </ErrorBoundary>
      </div>

      {/* Chips + this-week count. Counts only — no score, no label (§4-2). */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <FilterChips value={filter} onChange={setTimelineFilter} />
        <p
          className="font-mono text-pq-caption text-[var(--pq-ivory-faint)]"
          data-testid="journal-weekly-note-count"
        >
          이번 주 관찰 노트 {weekly.notes}개
          <span className="mx-1.5 opacity-40">·</span>
          종목 {weekly.tickers}개
        </p>
      </div>

      {/* Feed — 멈춤 기록 + 관찰 노트 in one reverse-chronological record. */}
      {feedLoading ? (
        <LoadingState />
      ) : error && entries.length === 0 ? (
        <LoadFailure onRetry={retry} />
      ) : entries.length === 0 ? (
        <EmptyState />
      ) : visible.length === 0 ? (
        <FilterEmptyState filter={filter} />
      ) : (
        <div className="space-y-4">
          {visible.map((entry) =>
            entry.kind === "reflection" ? (
              <JournalEntry key={entry.id} r={entry.reflection} />
            ) : (
              <div
                key={entry.id}
                className="rounded-[2px] border px-4 sm:px-5"
                style={{
                  borderColor: "var(--pq-ivory-line)",
                  background: "var(--pq-card-veil)",
                }}
              >
                <ObservationNoteCard
                  note={entry.note}
                  onDeleted={() => {
                    void mutateNotes();
                  }}
                />
              </div>
            ),
          )}
        </div>
      )}

      {/* Weekly pulse — the user's own self-report, so it lives with the
          record. Moved from /profile 2026-09-12; behaviour unchanged. */}
      <div className="mt-12">
        <WeeklyPulseSection />
      </div>

      <FootSignature />
    </div>
  );
}

export default function JournalPage() {
  return (
    <ErrorBoundary>
      <JournalContent />
    </ErrorBoundary>
  );
}
