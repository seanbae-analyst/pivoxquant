"use client";

/**
 * /pre-trade/door — 웹 문 (2026-10-15, docs/design/doorway-pause_2026-10-15.md).
 *
 * The same question the phone automation asks when a broker app opens —
 * "뭘 하러 왔어요?" — answered in the browser. An Android MacroDroid macro opens
 * this page when the broker app launches (`?app=kiwoom`); back returns to the
 * broker app. On any device it is also the place to try the door and to
 * delete past answers (the settings copy points here for that).
 *
 *   그냥 보기   → saved at once
 *   살 게 있음  → one optional line (종목 + 이유), then saved
 *   팔 게 있음  → same
 *
 * Opened by the automation (`&launch=1`, the settings guide's door address)
 * the page first records the open itself — the app-open signal, 2026-10-26 —
 * so going back without answering still counts as an open; the answer then
 * lands on that same row (services/doorway pairing). A visit from settings or
 * a link (no `launch`) records nothing until an answer.
 *
 * The answer goes to POST /api/doorway/checks (session). The reply line is the
 * server's ("기록했어요 · 오늘 N번째 열림" — a count, nothing else). When the
 * user said 살 게 있음 and the line named a stock, one link offers 「멈춤」 for
 * that ticker; the line itself is never put in a URL.
 *
 * Legal: no guidance of ours, no score, no direction word. The disclaimer is
 * mounted by (dashboard)/layout.tsx (record variant). No italic.
 */
import * as React from "react";
import Link from "next/link";
import useSWRInfinite from "swr/infinite";

import { ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { createDoorwayCheck, deleteDoorwayCheck, fetcher } from "@/lib/hooks";
import type { DoorwayCheck, DoorwayChecksResponse, DoorwayCreateResponse, DoorwayIntent } from "@/lib/types";
import { INTENT_LABEL, kstStamp } from "@/components/mirror/doorway-panel";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
const MAX_LINE = 200;
/** One read of past answers (the server allows up to 100). */
const DOOR_PAGE_SIZE = 20;

/**
 * Past answers, page by page on the server's id cursor (`next_before` →
 * `?before=`, routes/doorway.py). 2026-10-21: the page read one `?limit=20`
 * and dropped `next_before`, so only the newest 20 could be deleted here —
 * against the privacy policy's "하나씩 지울 수 있습니다". `mutate()` re-reads
 * every loaded page. Same pattern as /journal/research.
 */
function useDoorwayPages() {
  const swr = useSWRInfinite<DoorwayChecksResponse>(
    (_index, prev: DoorwayChecksResponse | null) => {
      if (prev && !prev.next_before) return null;
      const before = prev ? `&before=${prev.next_before}` : "";
      return `${API.doorway.checks}?limit=${DOOR_PAGE_SIZE}${before}`;
    },
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 10_000 },
  );
  const pages = swr.data ?? [];
  const last = pages[pages.length - 1];
  return {
    checks: pages.flatMap((p) => p.checks ?? []),
    hasMore: Boolean(last && last.next_before),
    loadingMore: swr.size > pages.length,
    loadMore: () => void swr.setSize(swr.size + 1),
    mutate: swr.mutate,
  };
}

/** Opened by the app-launch automation — not by hand. */
function readLaunch(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("launch") === "1";
  } catch {
    return false;
  }
}

function readApp(): string | undefined {
  try {
    const a = new URLSearchParams(window.location.search).get("app");
    return a && /^[a-z0-9_-]{1,20}$/.test(a) ? a : undefined;
  } catch {
    return undefined;
  }
}

/** What the done state shows. A 2xx is not the same as a usable payload —
 *  demo mode answers every write with a bare `{ok: true}` — so the screen
 *  keeps a plain line and drops the 멈춤 link instead of crashing. */
function doneView(res: Partial<DoorwayCreateResponse> | null | undefined): {
  message: string;
  pauseTicker: string | null;
} {
  const check = res?.check;
  return {
    message: res?.message || "기록했어요",
    pauseTicker: check && check.intent === "buy" && check.ticker ? check.ticker : null,
  };
}

function errorText(e: unknown): string {
  if (e instanceof ApiError && e.message) return e.message;
  return "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

function ChoiceButton({
  label,
  onClick,
  disabled,
  primary = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full px-4 py-3.5 text-left text-[16px] disabled:opacity-60"
      style={{
        borderRadius: "var(--pq-radius-cta)",
        border: `1px solid ${primary ? "var(--pq-bronze)" : "var(--pq-ivory-line)"}`,
        color: primary ? "var(--pq-bronze)" : "var(--pq-ivory)",
        background: "rgba(255,255,255,0.02)",
      }}
    >
      {label}
    </button>
  );
}

function RecentChecks({ pages }: { pages: ReturnType<typeof useDoorwayPages> }) {
  const { checks, mutate, hasMore, loadingMore, loadMore } = pages;
  const [busy, setBusy] = React.useState<number | null>(null);
  if (checks.length === 0) return null;

  const remove = async (c: DoorwayCheck) => {
    setBusy(c.id);
    try {
      await deleteDoorwayCheck(c.id);
      await mutate();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="mt-10" aria-label="최근 문 앞 기록" data-testid="door-recent">
      <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
        최근 문 앞 기록
      </div>
      <ul className="mt-2" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
        {checks.map((c) => (
          <li
            key={c.id}
            className="flex items-start justify-between gap-3 py-2.5"
            style={{ borderBottom: "1px solid var(--pq-ivory-line)" }}
          >
            <div className="min-w-0">
              <div className="text-[12px] tabular-nums" style={{ color: DIM }}>
                {kstStamp(c.created_at)} · {INTENT_LABEL[c.intent] ?? c.intent}
              </div>
              {(c.note || c.name) && (
                <p className="mt-0.5 break-words text-[13.5px]" style={{ color: "var(--pq-ivory)" }}>
                  {c.note || c.name}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => remove(c)}
              disabled={busy === c.id}
              className="shrink-0 text-[12px] underline underline-offset-2 disabled:opacity-60"
              style={{ color: DIM }}
              aria-label={`${kstStamp(c.created_at)} 기록 지우기`}
            >
              지우기
            </button>
          </li>
        ))}
      </ul>
      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loadingMore}
          className="mt-3 text-[12.5px] underline underline-offset-2 disabled:opacity-60"
          style={{ color: "var(--pq-bronze)" }}
          data-testid="door-more"
        >
          {loadingMore ? "불러오는 중…" : "이전 기록 더 보기"}
        </button>
      )}
    </section>
  );
}

export default function DoorPage() {
  const [app, setApp] = React.useState<string | undefined>(undefined);
  React.useEffect(() => setApp(readApp()), []);

  const [intent, setIntent] = React.useState<DoorwayIntent | null>(null);
  const [line, setLine] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState<ReturnType<typeof doneView> | null>(null);
  const pages = useDoorwayPages();
  const refreshList = pages.mutate;

  // The app-open signal, once per page load (the ref also survives the dev
  // double effect). Its failure is silent — the answer still saves on its own.
  const openSent = React.useRef<Promise<unknown> | null>(null);
  React.useEffect(() => {
    if (openSent.current || !readLaunch()) return;
    openSent.current = createDoorwayCheck({ intent: "open", app: readApp() }).catch(() => undefined);
  }, []);

  const save = async (which: DoorwayIntent, note?: string) => {
    setBusy(true);
    setError(null);
    try {
      // The answer must reach the server after its open, or it would be a second row.
      if (openSent.current) await openSent.current;
      const res = await createDoorwayCheck({ intent: which, note: note?.trim() || undefined, app });
      setDone(doneView(res));
      await refreshList();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setIntent(null);
    setLine("");
    setDone(null);
    setError(null);
  };

  return (
    <div className="mx-auto max-w-md px-0 py-4 md:py-10" data-testid="door-page">
      {done ? (
        <section aria-live="polite" data-testid="door-done">
          <p className="text-[1.35rem] leading-snug" style={{ color: "var(--pq-ivory)" }}>
            {done.message}
          </p>
          <p className="mt-2 text-[13px] leading-relaxed" style={{ color: DIM }}>
            증권 앱에서 왔다면 뒤로 가기를 누르면 돌아갑니다.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            {done.pauseTicker && (
              <Link
                href={`/pre-trade?ticker=${encodeURIComponent(done.pauseTicker)}`}
                className="px-4 py-2 text-[13px] font-semibold"
                style={{
                  borderRadius: "var(--pq-radius-cta)",
                  backgroundColor: "var(--pq-bronze)",
                  color: "var(--pq-ink)",
                }}
                data-testid="door-pause-link"
              >
                멈춤에서 일곱 질문 보기
              </Link>
            )}
            <button
              type="button"
              onClick={reset}
              className="text-[12.5px] underline underline-offset-2"
              style={{ color: "var(--pq-bronze)" }}
            >
              다시 답하기
            </button>
          </div>
        </section>
      ) : (
        <section aria-label="뭘 하러 왔어요?">
          <h1 className="text-[1.6rem] leading-snug" style={{ color: "var(--pq-ivory)" }}>
            뭘 하러 왔어요?
          </h1>
          <p className="mt-2 text-[13px] leading-relaxed" style={{ color: DIM }}>
            답은 거울의 &lsquo;문 앞&rsquo;에 쌓이고, 그 뒤 체결과 나란히 보여요. 남은 기록은
            답하지 않은 열림까지 아래에서 하나씩 지울 수 있어요.
          </p>

          {intent === null ? (
            <div className="mt-6 space-y-2.5">
              <ChoiceButton label="그냥 보기" onClick={() => save("look")} disabled={busy} />
              <ChoiceButton label="살 게 있음" onClick={() => setIntent("buy")} disabled={busy} primary />
              <ChoiceButton label="팔 게 있음" onClick={() => setIntent("sell")} disabled={busy} primary />
            </div>
          ) : (
            <form
              className="mt-6"
              onSubmit={(e) => {
                e.preventDefault();
                void save(intent, line);
              }}
            >
              <label className="block">
                <span className="text-[13px]" style={{ color: "var(--pq-ivory)" }}>
                  {INTENT_LABEL[intent]} — 어떤 종목, 왜? 한 줄
                </span>
                <input
                  type="text"
                  value={line}
                  onChange={(e) => setLine(e.target.value.slice(0, MAX_LINE))}
                  maxLength={MAX_LINE}
                  autoFocus
                  placeholder="예: 삼성전자 실적 발표 전에"
                  className="mt-2 block w-full rounded-[var(--pq-radius-cta)] border bg-transparent px-3 py-3 text-[16px]"
                  style={{ borderColor: "var(--pq-ivory-line)", color: "var(--pq-ivory)" }}
                  data-testid="door-line"
                />
              </label>
              <div className="mt-4 flex items-center gap-4">
                <button
                  type="submit"
                  disabled={busy}
                  className="px-4 py-2.5 text-[14px] font-semibold disabled:opacity-60"
                  style={{
                    borderRadius: "var(--pq-radius-cta)",
                    backgroundColor: "var(--pq-bronze)",
                    color: "var(--pq-ink)",
                  }}
                >
                  {busy ? "남기는 중…" : "남기기"}
                </button>
                <button
                  type="button"
                  onClick={() => setIntent(null)}
                  className="text-[12.5px] underline underline-offset-2"
                  style={{ color: DIM }}
                >
                  다시 고르기
                </button>
              </div>
            </form>
          )}

          {error && (
            <p className="mt-3 text-[12.5px]" role="alert" style={{ color: DIM }}>
              {error}
            </p>
          )}
        </section>
      )}

      <RecentChecks pages={pages} />
    </div>
  );
}
