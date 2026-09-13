"use client";

/**
 * Import Inbox — parsed-but-unapproved fills waiting for a "why".
 *
 * docs/product/IMPORT_INBOX_DESIGN.md. A row here is NOT a record: the
 * backend parked it in `pending_trades` after the user uploaded a CSV/XLSX
 * export or pasted fill-notification text. It reaches `trade_history` /
 * `positions` (and therefore the mirrors) only when the user attaches a
 * one-line thesis and approves. Reject discards it.
 *
 *   - Copy is observational: what was received, when, at what price. No
 *     추천/조언, no BUY/SELL labels on screen (매수/매도 · Buy/Sell).
 *   - `pre_trade_reflection_id` is surfaced as a plain fact: "멈춤 기록 있음"
 *     vs "멈춤 없이" — never a score or a judgement.
 *   - `needs_ticker` rows get the same debounced /api/search autocomplete the
 *     add-position modal uses; confirming PATCHes the row.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT. Same framed-card shell
 * as the behaviour mirrors in this folder (holding-mirror.tsx).
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { useT, useLocale } from "@/lib/locale";
import { usePendingImports } from "@/lib/hooks";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { displayName } from "@/lib/format";
import { fadeUp } from "@/lib/motion";
import {
  RuledKicker,
  EditorialHead,
  FieldLabel,
  Caption,
  HairlineSoft,
} from "@/components/ui/editorial";
import type { PendingTradeDTO, ImportApproveResponse } from "@/lib/types";

export const THESIS_MIN = 3;
export const THESIS_MAX = 500;

/* ────────────────────────────────────────────────────────────────────────
 * Pure helpers — kept exported for the unit tests.
 * ────────────────────────────────────────────────────────────────────── */

/** "₩71,200" / "$189.20" — currency symbol + locale grouping. */
export function fmtPrice(price: number, currency: "KRW" | "USD"): string {
  if (!Number.isFinite(price)) return "—";
  if (currency === "USD") {
    return `$${price.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  return `₩${Math.round(price).toLocaleString("ko-KR")}`;
}

/** Whole shares stay integers; fractional (US) shares keep up to 4 decimals. */
export function fmtShares(shares: number): string {
  if (!Number.isFinite(shares)) return "—";
  return Number.isInteger(shares)
    ? shares.toLocaleString("ko-KR")
    : shares.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

/** KST-pinned "2026. 9. 13. 09:31" — naive backend stamps are read as UTC. */
export function fmtTradedAt(iso: string | null | undefined, locale: "ko" | "en"): string {
  if (!iso) return "";
  const needsUtc = !iso.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(needsUtc ? iso + "Z" : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(locale === "en" ? "en-US" : "ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  });
}

export function thesisOk(thesis: string): boolean {
  const n = thesis.trim().length;
  return n >= THESIS_MIN && n <= THESIS_MAX;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message || fallback;
  if (err instanceof Error) return err.message || fallback;
  return fallback;
}

/* ────────────────────────────────────────────────────────────────────────
 * Ticker resolver — debounced /api/search via API.market.search. Mirrors the
 * autocomplete in portfolio/v2/add-position-modal-v2.tsx; `apiFetch` exposes
 * `signal`, so stale keystrokes are pre-empted without a raw fetch.
 * ────────────────────────────────────────────────────────────────────── */

interface Suggestion {
  ticker: string;
  name: string;
  exchange?: string;
  is_korean?: boolean;
}

function TickerResolver({
  initialQuery,
  onConfirm,
  busy,
  t,
}: {
  initialQuery: string;
  onConfirm: (ticker: string) => void;
  busy: boolean;
  t: (k: string) => string;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [picked, setPicked] = useState<Suggestion | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (picked || q.length < 1) {
      setSuggestions([]);
      setLoading(false);
      abortRef.current?.abort();
      return;
    }
    setLoading(true);
    const ctrl = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ctrl;
    const timer = window.setTimeout(async () => {
      try {
        const body = await apiFetch<{ results?: Suggestion[] }>(
          API.market.search(q),
          { signal: ctrl.signal },
        );
        setSuggestions((body.results ?? []).slice(0, 6));
      } catch (err) {
        if ((err as { name?: string })?.name === "AbortError") return;
        setSuggestions([]);
      } finally {
        if (abortRef.current === ctrl) setLoading(false);
      }
    }, 300);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [query, picked]);

  return (
    <div className="mt-3" style={{ position: "relative" }}>
      <FieldLabel tone="bronze">{t("journal.import.needsTicker")}</FieldLabel>
      <div className="mt-2 flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPicked(null);
          }}
          placeholder={t("journal.import.tickerPlaceholder")}
          autoComplete="off"
          aria-label={t("journal.import.tickerPlaceholder")}
          className="w-full bg-transparent border border-[rgba(245,240,232,0.15)] rounded-[2px] px-3 py-2 text-pq-body-sm outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)] font-mono"
        />
        {loading && (
          <span
            className="font-mono uppercase"
            aria-label="Searching"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.14em",
              color: "var(--pq-ivory-faint)",
            }}
          >
            …
          </span>
        )}
        <button
          type="button"
          disabled={!picked || busy}
          aria-disabled={!picked || busy}
          onClick={() => picked && onConfirm(picked.ticker.trim().toUpperCase())}
          className="pq-ink-btn-ghost whitespace-nowrap px-3 text-pq-eyebrow uppercase tracking-[0.16em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {t("journal.import.tickerConfirm")}
        </button>
      </div>

      {picked && (
        <span
          className="font-serif"
          style={{
            display: "block",
            marginTop: 6,
            fontSize: "var(--pq-text-body-sm)",
            color: "var(--pq-bronze)",
          }}
        >
          {displayName(picked.ticker, picked.name)}
        </span>
      )}

      {!picked && query.trim().length > 0 && suggestions.length > 0 && (
        <div
          role="listbox"
          aria-label={t("journal.import.tickerSearchLabel")}
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: "100%",
            zIndex: 20,
            marginTop: 4,
            maxHeight: 224,
            overflowY: "auto",
            background: "var(--pq-ink, #050505)",
            border: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.16))",
            borderRadius: "var(--pq-radius-card, 4px)",
            boxShadow: "0 18px 44px -20px rgba(0,0,0,0.7)",
          }}
        >
          {suggestions.map((s) => (
            <button
              key={s.ticker}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => {
                setPicked(s);
                setQuery(s.ticker.trim().toUpperCase());
                setSuggestions([]);
              }}
              className="hover:bg-[var(--pq-card-veil-strong)]"
              style={{
                display: "flex",
                width: "100%",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <span
                className="font-mono"
                style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory)" }}
              >
                {s.ticker}
              </span>
              <span
                className="font-serif truncate"
                style={{ fontSize: "var(--pq-text-body-sm)", color: "var(--pq-ivory-dim)" }}
              >
                {s.name}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * One pending row — facts line, pause fact, ticker resolver, thesis, actions.
 * Shared by the /journal inbox card and the /journal/import result list.
 * ────────────────────────────────────────────────────────────────────── */

export function PendingTradeRow({
  row,
  onChanged,
}: {
  row: PendingTradeDTO;
  /** Called after approve / reject / PATCH succeeded — parent refetches or drops the row. */
  onChanged: (next: PendingTradeDTO | null) => void;
}) {
  const t = useT();
  const { locale } = useLocale();
  const [thesis, setThesis] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | "patch" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canApprove = thesisOk(thesis) && !row.needs_ticker && busy === null;
  const sideLabel = row.action === "SELL" ? t("journal.import.sell") : t("journal.import.buy");
  const nameLabel = row.ticker ? displayName(row.ticker, row.name) : row.name;

  async function approve() {
    if (!canApprove) return;
    setBusy("approve");
    setError(null);
    try {
      await apiFetch<ImportApproveResponse>(API.imports.approve(row.id), {
        method: "POST",
        body: JSON.stringify({ thesis: thesis.trim() }),
      });
      onChanged(null);
    } catch (err) {
      setError(errorMessage(err, t("journal.page.loadFailure")));
    } finally {
      setBusy(null);
    }
  }

  async function reject() {
    if (busy) return;
    setBusy("reject");
    setError(null);
    try {
      await apiFetch<{ ok: boolean }>(API.imports.reject(row.id), { method: "POST" });
      onChanged(null);
    } catch (err) {
      setError(errorMessage(err, t("journal.page.loadFailure")));
    } finally {
      setBusy(null);
    }
  }

  async function confirmTicker(ticker: string) {
    if (busy) return;
    setBusy("patch");
    setError(null);
    try {
      const res = await apiFetch<{ pending: PendingTradeDTO }>(
        API.imports.pendingItem(row.id),
        { method: "PATCH", body: JSON.stringify({ ticker }) },
      );
      onChanged(res.pending);
    } catch (err) {
      setError(errorMessage(err, t("journal.page.loadFailure")));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="py-4" data-testid="pending-trade-row">
      {/* Facts line: name (+ticker) · side · shares · price · time */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span
          className="font-serif"
          style={{ fontSize: "var(--pq-text-body)", color: "var(--pq-ivory)" }}
        >
          {nameLabel}
        </span>
        {row.ticker && row.ticker !== nameLabel && (
          <span
            className="font-mono"
            style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-dim)" }}
          >
            {row.ticker}
          </span>
        )}
        <FieldLabel tone="bronze">{sideLabel}</FieldLabel>
        {row.status === "duplicate" && (
          <FieldLabel tone="muted">{t("journal.import.duplicate")}</FieldLabel>
        )}
      </div>
      <div
        className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono"
        style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-mid)" }}
      >
        <span>
          {fmtShares(row.shares)}
          {t("journal.import.sharesUnit")}
        </span>
        <span>{fmtPrice(row.price, row.currency)}</span>
        <span>{fmtTradedAt(row.traded_at, locale)}</span>
      </div>
      <Caption className="mt-1">
        {row.pre_trade_reflection_id != null
          ? t("journal.import.reflectionMatched")
          : t("journal.import.reflectionNone")}
      </Caption>

      {row.needs_ticker && (
        <TickerResolver
          initialQuery={row.name}
          onConfirm={confirmTicker}
          busy={busy !== null}
          t={t}
        />
      )}

      {/* Thesis — the one line that turns a received fill into a record. */}
      <div className="mt-3">
        <label htmlFor={`import-thesis-${row.id}`}>
          <FieldLabel tone="bronze">{t("journal.import.thesisLabel")}</FieldLabel>
        </label>
        <textarea
          id={`import-thesis-${row.id}`}
          value={thesis}
          onChange={(e) => setThesis(e.target.value.slice(0, THESIS_MAX))}
          rows={2}
          maxLength={THESIS_MAX}
          placeholder={t("journal.import.thesisPlaceholder")}
          className="mt-2 w-full bg-transparent border border-[rgba(245,240,232,0.15)] rounded-[2px] p-3 text-pq-body-sm leading-relaxed outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)] font-serif"
          style={{ resize: "vertical" }}
        />
        <div
          className="mt-1 font-mono tracking-[0.06em]"
          style={{ fontSize: "var(--pq-text-mono-sm)", color: "var(--pq-ivory-faint)" }}
        >
          {t("journal.import.thesisCount").replace("{n}", String(thesis.trim().length))}
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={approve}
          disabled={!canApprove}
          aria-disabled={!canApprove}
          className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {busy === "approve" ? t("journal.import.working") : t("journal.import.approve")}
        </button>
        <button
          type="button"
          onClick={reject}
          disabled={busy !== null}
          aria-disabled={busy !== null}
          className="pq-ink-btn-ghost px-4 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {busy === "reject" ? t("journal.import.working") : t("journal.import.reject")}
        </button>
      </div>

      {error && (
        <Caption className="mt-2">
          <span style={{ color: "var(--pq-error)" }}>{error}</span>
        </Caption>
      )}
    </div>
  );
}

/** Plain list of rows separated by hairlines — reused by the import page. */
export function PendingTradeList({
  rows,
  onChanged,
}: {
  rows: PendingTradeDTO[];
  onChanged: (id: number, next: PendingTradeDTO | null) => void;
}) {
  return (
    <ul className="mt-2 list-none p-0">
      {rows.map((row, i) => (
        <li key={row.id}>
          {i > 0 && <HairlineSoft />}
          <PendingTradeRow row={row} onChanged={(next) => onChanged(row.id, next)} />
        </li>
      ))}
    </ul>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Public card — mounted at the top of /journal.
 * ────────────────────────────────────────────────────────────────────── */

export function ImportInbox() {
  const t = useT();
  useLocale();
  const { pending, isLoading, error, mutate } = usePendingImports();

  // Hard failure → render nothing rather than a broken card (mirror rule).
  if (error) return null;
  if (isLoading) return null;

  if (pending.length === 0) {
    return (
      <div className="mb-8 flex items-baseline justify-between gap-3">
        <Caption>{t("journal.import.emptyLine")}</Caption>
        <Link
          href="/journal/import"
          className="font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
        >
          {t("journal.import.importLink")}
        </Link>
      </div>
    );
  }

  return (
    <motion.section
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="mb-8 rounded-[2px] border p-5 sm:p-6"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
      aria-label={t("journal.import.kicker")}
    >
      <div className="flex items-baseline justify-between gap-3">
        <RuledKicker>{t("journal.import.kicker")}</RuledKicker>
        <Link
          href="/journal/import"
          className="font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
        >
          {t("journal.import.importLink")}
        </Link>
      </div>
      <EditorialHead as="h2" size={22} tone="ivory" className="mt-3">
        {t("journal.import.title").replace("{n}", String(pending.length))}
      </EditorialHead>
      <Caption className="mt-2 max-w-lg">{t("journal.import.desc")}</Caption>

      <PendingTradeList rows={pending} onChanged={() => void mutate()} />
    </motion.section>
  );
}
