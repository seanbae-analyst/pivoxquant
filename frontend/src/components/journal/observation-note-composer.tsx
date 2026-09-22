"use client";

/**
 * <ObservationNoteComposer /> — 관찰 노트 작성 박스.
 *
 * docs/design/observation-notes_2026-09-22.md §5. The one place a user can
 * write something down WITHOUT a trade attached. It is deliberately the
 * *front* of the loop, never a shortcut past it: there is no "주문" affordance
 * here, and /pre-trade only ever READS notes back (§5 진입점).
 *
 * Tone rules that apply to every string in this file (자본시장법 §17,
 * CLAUDE.md §중요 원칙): observational only. None of the directive
 * vocabulary that section bans, no trade-action literals, no score and no
 * label. We describe what the user is recording; we never tell them what to
 * do with it.
 *
 * Caps mirror the backend service exactly so a rejected POST is rare and the
 * user is told before they type past the limit — but the server stays the
 * authority: a 400 (`OBS_NOTE_BAD_INPUT`) is rendered verbatim from its own
 * localized message rather than re-worded here.
 *
 * Nothing on this surface reads a quote. `/api/search` (via <TickerSearch />)
 * resolves names, not prices, and stays live while
 * MARKET_DATA_DISPLAY_ENABLED is off.
 */

import * as React from "react";
import { mutate as globalMutate } from "swr";
import { API } from "@/lib/endpoints";
import { createObservationNote } from "@/lib/hooks";
import { displayName } from "@/lib/format";
import { FieldLabel, Caption } from "@/components/ui/editorial";
import { TickerSearch } from "@/components/shared/ticker-search";
import type { TickerSearchResult } from "@/components/shared/ticker-search";
import type {
  ObservationNote,
  ObservationNoteSource,
  ObservationNoteTicker,
} from "@/lib/types";

/* ────────────────────────────────────────────────────────────────────────
 * Caps — 1:1 with services/observation_notes/service.py.
 * ────────────────────────────────────────────────────────────────────── */

/** Same constant as friction.py MAX_TEXT_CHARS. */
export const OBS_NOTE_MAX_CHARS = 5000;
export const OBS_NOTE_MAX_TICKERS = 5;
export const OBS_NOTE_MAX_TAGS = 10;
export const OBS_NOTE_MAX_TAG_CHARS = 40;

/** Characters the backend refuses inside a tag. */
const TAG_BANNED_CHARS = /["\\]/;

export const OBS_NOTE_PLACEHOLDER =
  "지금 보고 있는 흐름을 그대로 적어 두세요. 나중에 이 종목을 멈춤 화면에서 만나면 이 글이 다시 보입니다.";

export interface ObservationNoteComposerProps {
  /** Tickers pre-filled into the chip row (e.g. the /portfolio row you opened). */
  defaultTickers?: string[];
  /** Which surface this note is being written from — beta instrumentation. */
  source: ObservationNoteSource;
  /** Called with the server-committed note after a successful POST. */
  onCreated?: (note: ObservationNote) => void;
  /** Tighter spacing for modal/inline hosts (the /portfolio entry point). */
  compact?: boolean;
}

/* ────────────────────────────────────────────────────────────────────────
 * Pure helpers — exported for the unit tests.
 * ────────────────────────────────────────────────────────────────────── */

/** Trim + upper-case a ticker the way the backend normalizer will. */
export function normalizeNoteTicker(raw: string): string {
  return raw.trim().toUpperCase();
}

/**
 * The identity two chips share when they are the same note ticker.
 *
 * `services/observation_notes/service.py::normalize_ticker` appends `.KS` /
 * `.KQ` to a bare 6-digit KR code, so `005930` and `005930.KS` land on ONE
 * row server-side. Comparing the raw strings would let the user add both and
 * then watch the saved note come back with a single ticker. We dedupe on the
 * suffix-stripped form and still SEND the ticker exactly as search handed it
 * over, suffix included, so the server never has to guess the exchange.
 */
export function noteTickerKey(raw: string): string {
  return normalizeNoteTicker(raw).replace(/\.(KS|KQ)$/, "");
}

/**
 * Why a tag was rejected, or null when it is acceptable. Returned as a code
 * so the copy lives in one place below.
 */
export function tagRejection(
  raw: string,
  existing: readonly string[],
): "empty" | "too_long" | "bad_chars" | "duplicate" | "too_many" | null {
  const tag = raw.trim();
  if (!tag) return "empty";
  if (tag.length > OBS_NOTE_MAX_TAG_CHARS) return "too_long";
  // The backend rejects these two outright (400 OBS_NOTE_BAD_INPUT), so the
  // chip never forms rather than the POST failing after the user has typed.
  if (TAG_BANNED_CHARS.test(tag)) return "bad_chars";
  if (existing.includes(tag)) return "duplicate";
  if (existing.length >= OBS_NOTE_MAX_TAGS) return "too_many";
  return null;
}

export function ObservationNoteComposer({
  defaultTickers,
  source,
  onCreated,
  compact = false,
}: ObservationNoteComposerProps) {
  const [body, setBody] = React.useState("");
  const [tickers, setTickers] = React.useState<ObservationNoteTicker[]>(() => {
    const seen = new Set<string>();
    const out: ObservationNoteTicker[] = [];
    for (const raw of defaultTickers ?? []) {
      const ticker = normalizeNoteTicker(raw);
      if (!ticker) continue;
      const key = noteTickerKey(ticker);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ ticker, name: "" });
      if (out.length >= OBS_NOTE_MAX_TICKERS) break;
    }
    return out;
  });
  const [tickerQuery, setTickerQuery] = React.useState("");
  const [tags, setTags] = React.useState<string[]>([]);
  const [tagDraft, setTagDraft] = React.useState("");
  const [notice, setNotice] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  // Code points, not UTF-16 units — `Array.from` splits surrogate pairs the
  // way Python's `len()` counts them, so an emoji costs the user 1 here and 1
  // on the server instead of 1 here and 2 there.
  const bodyLength = Array.from(body.trim()).length;
  const overLimit = bodyLength > OBS_NOTE_MAX_CHARS;
  const canSubmit = bodyLength > 0 && !overLimit && !submitting;

  function addTicker(result: TickerSearchResult) {
    const ticker = normalizeNoteTicker(result.ticker);
    setTickerQuery("");
    setNotice(null);
    if (!ticker) return;
    const key = noteTickerKey(ticker);
    if (tickers.some((t) => noteTickerKey(t.ticker) === key)) return;
    if (tickers.length >= OBS_NOTE_MAX_TICKERS) {
      setNotice(`종목은 ${OBS_NOTE_MAX_TICKERS}개까지 담을 수 있습니다.`);
      return;
    }
    setTickers((prev) => [...prev, { ticker, name: result.name ?? "" }]);
  }

  function removeTicker(ticker: string) {
    setTickers((prev) => prev.filter((t) => t.ticker !== ticker));
    setNotice(null);
  }

  function commitTag() {
    // 쉼표는 구분자다. keydown 이 아닌 경로(IME 조합 종료, 붙여넣기, blur,
    // 자동화된 insertText)로 "거래량," 이 통째로 들어오면 쉼표를 떼고 커밋한다 —
    // 2026-09-22 브라우저 E2E 에서 태그가 "거래량," 으로 저장된 사례.
    const draft = tagDraft.replace(/,/g, " ").trim();
    if (draft !== tagDraft) setTagDraft(draft);
    const reason = tagRejection(draft, tags);
    if (reason === "empty") return;
    if (reason === "too_long") {
      setNotice(`태그는 ${OBS_NOTE_MAX_TAG_CHARS}자까지 적을 수 있습니다.`);
      return;
    }
    if (reason === "bad_chars") {
      setNotice("태그에 큰따옴표와 역슬래시는 쓸 수 없습니다.");
      return;
    }
    if (reason === "too_many") {
      setNotice(`태그는 ${OBS_NOTE_MAX_TAGS}개까지 담을 수 있습니다.`);
      return;
    }
    if (reason === "duplicate") {
      setTagDraft("");
      return;
    }
    setTags((prev) => [...prev, draft]);
    setTagDraft("");
    setNotice(null);
  }

  function onTagKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commitTag();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await createObservationNote({
        body: body.trim(),
        tickers: tickers.map((t) => t.ticker),
        tags,
        source,
      });
      setBody("");
      setTags([]);
      setTagDraft("");
      setTickerQuery("");
      setTickers([]);
      setNotice(null);
      // Refresh every cached observation-notes feed (the unfiltered journal
      // list and any ticker/tag-filtered variant) without knowing their keys.
      void globalMutate(
        (key) =>
          typeof key === "string" && key.startsWith(API.observationNotes.list),
      );
      onCreated?.(res.note);
    } catch (err) {
      // The backend already localizes (error_kr / error); apiFetch picks the
      // right one for the active locale and puts it on the error message.
      setError(
        err instanceof Error && err.message
          ? err.message
          : "노트를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="관찰 노트 작성"
      className={`rounded-[2px] border border-[var(--pq-ivory-line)] ${
        compact ? "p-4" : "p-5 sm:p-6"
      }`}
    >
      <FieldLabel tone="bronze">관찰 노트</FieldLabel>
      {!compact && (
        <Caption className="mt-2">
          거래하지 않아도 남길 수 있는 기록입니다. 지금 본 것만 적어 두세요.
        </Caption>
      )}

      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={OBS_NOTE_PLACEHOLDER}
        aria-label="관찰 노트 본문"
        rows={compact ? 3 : 5}
        className="mt-3 w-full resize-y rounded-[2px] border border-[var(--pq-ivory-line)] bg-transparent p-3 font-serif text-pq-body-sm leading-relaxed text-[var(--pq-ivory)] outline-none focus:border-[var(--pq-bronze)]"
      />

      <div className="mt-1 flex items-baseline justify-between gap-3">
        <span
          className="font-mono tracking-[0.06em]"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: overLimit ? "var(--pq-negative)" : "var(--pq-ivory-faint)",
          }}
        >
          {bodyLength} / {OBS_NOTE_MAX_CHARS}
        </span>
        {overLimit && (
          <span
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "var(--pq-negative)",
            }}
          >
            {OBS_NOTE_MAX_CHARS}자를 넘으면 기록할 수 없습니다.
          </span>
        )}
      </div>

      {/* 종목 — 0~5개. 비워 두면 시장 전반에 대한 기록이 됩니다. */}
      <div className="mt-4">
        <FieldLabel tone="muted">
          종목 · 선택 ({tickers.length}/{OBS_NOTE_MAX_TICKERS})
        </FieldLabel>
        {tickers.length > 0 && (
          <ul className="mt-2 flex list-none flex-wrap gap-2 p-0">
            {tickers.map((t) => (
              <li key={t.ticker}>
                <button
                  type="button"
                  onClick={() => removeTicker(t.ticker)}
                  aria-label={`${t.ticker} 빼기`}
                  className="inline-flex items-center gap-2 rounded-[2px] border border-[rgba(var(--pq-bronze-rgb),0.35)] px-2 py-1 text-[var(--pq-bronze)]"
                  style={{ fontSize: "var(--pq-text-eyebrow)" }}
                >
                  <span className="font-mono">
                    {displayName(t.ticker, t.name)}
                  </span>
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {tickers.length < OBS_NOTE_MAX_TICKERS && (
          <div className="mt-2">
            <TickerSearch
              value={tickerQuery}
              onChange={setTickerQuery}
              onPick={addTicker}
              ariaLabel="종목 검색"
              placeholder="종목명 또는 티커"
              showPickedName={false}
              inputClassName="w-full rounded-[2px] border border-[var(--pq-ivory-line)] bg-transparent px-3 py-2 font-mono text-pq-body-sm text-[var(--pq-ivory)] outline-none focus:border-[var(--pq-bronze)]"
            />
          </div>
        )}
      </div>

      {/* 태그 — 0~10개, 각 40자까지. Enter 또는 쉼표로 추가. */}
      <div className="mt-4">
        <FieldLabel tone="muted">
          태그 · 선택 ({tags.length}/{OBS_NOTE_MAX_TAGS})
        </FieldLabel>
        {tags.length > 0 && (
          <ul className="mt-2 flex list-none flex-wrap gap-2 p-0">
            {tags.map((tag) => (
              <li key={tag}>
                <button
                  type="button"
                  onClick={() => setTags((prev) => prev.filter((x) => x !== tag))}
                  aria-label={`${tag} 태그 빼기`}
                  className="inline-flex items-center gap-2 rounded-[2px] border border-[var(--pq-ivory-line)] px-2 py-1 text-[var(--pq-ivory-dim)]"
                  style={{ fontSize: "var(--pq-text-eyebrow)" }}
                >
                  <span className="font-mono">{tag}</span>
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <input
          value={tagDraft}
          onChange={(e) => setTagDraft(e.target.value)}
          onKeyDown={onTagKeyDown}
          onBlur={() => tagDraft.trim() && commitTag()}
          aria-label="태그 입력"
          placeholder="Enter 또는 쉼표로 추가"
          autoComplete="off"
          className="mt-2 w-full rounded-[2px] border border-[var(--pq-ivory-line)] bg-transparent px-3 py-2 font-mono text-pq-body-sm text-[var(--pq-ivory)] outline-none focus:border-[var(--pq-bronze)]"
        />
      </div>

      {notice && (
        <p
          role="status"
          className="mt-3 font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-ivory-dim)",
          }}
        >
          {notice}
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="mt-3 font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-negative)",
          }}
        >
          {error}
        </p>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          aria-disabled={!canSubmit}
          className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:cursor-not-allowed disabled:opacity-30"
        >
          {submitting ? "기록하는 중" : "기록"}
        </button>
        <Caption>기록은 본인만 볼 수 있습니다.</Caption>
      </div>
    </form>
  );
}

export default ObservationNoteComposer;
