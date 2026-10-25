"use client";

/**
 * DoorwayPanel — 「문 앞」 on /mirror (2026-10-15).
 *
 * The user's own phone automation asks "뭘 하러 왔어요?" each time a broker
 * app opens (그냥 보기 / 살 게 있음 / 팔 게 있음 + 한 줄) and posts the answer
 * with the personal import token. GET /api/doorway/summary matches those opens
 * to the user's own fills (services/doorway/service.py) and this card reads the
 * counts back: how often the app was opened and why, which opens ended in a
 * fill, which "살 게 있음" ended without one and whether that stock was bought
 * within 30 days anyway — the trades that did not happen.
 *
 * Why here: 「멈춤」 works only when the user remembers to come to us before
 * buying. The door is where the impulse starts; this is the mirror of it.
 *
 * States:
 *  - never set up (`first_check_at` null) → one quiet invite line to the
 *    settings guide (`invite`, desktop column only — the phone row of story
 *    cards does not add a card for it)
 *  - set up, nothing in the window → one line asking to check the automation
 *  - otherwise the counts
 *
 * Legal / product posture: counts only — no score, grade, streak, verdict or
 * "줄이세요". Outcome words are facts ("말한 대로 체결", "체결 없음"). The
 * caveats the backend sends (not random, window rule) are shown, not hidden.
 * No market data. No italic. The disclaimer is mounted by (dashboard)/layout.
 */
import * as React from "react";
import Link from "next/link";

import { useDoorwaySummary } from "@/lib/hooks";
import { parseIsoUtc } from "@/lib/format";
import type {
  DoorwayIntent,
  DoorwayOutcome,
  DoorwayRecent,
  DoorwaySummaryResponse,
} from "@/lib/types";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";
export const DOORWAY_SETTINGS_HREF = "/settings?s=doorway";

export const INTENT_LABEL: Record<DoorwayIntent, string> = {
  look: "그냥 보기",
  buy: "살 게 있음",
  sell: "팔 게 있음",
};

export const OUTCOME_LABEL: Record<DoorwayOutcome, string> = {
  traded: "체결 있음",
  as_said: "말한 대로 체결",
  other: "다른 체결",
  none: "체결 없음",
};

const INTENT_ORDER: DoorwayIntent[] = ["look", "buy", "sell"];

/** "10.15 09:05" in KST; naive backend stamps are UTC. */
export function kstStamp(iso: string | null): string {
  const d = parseIsoUtc(iso);
  if (!d) return "";
  const parts = new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("month")}.${get("day")} ${get("hour")}:${get("minute")}`;
}

/** The fact sentences under the bars — one per answer that occurred. */
export function doorwayFacts(s: DoorwaySummaryResponse): string[] {
  const out: string[] = [];
  if (s.look.n > 0) {
    out.push(`그냥 보기 ${s.look.n}번 중 ${s.look.traded}번은 ${s.follow_minutes}분 안에 체결이 있었어요.`);
  }
  for (const key of ["buy", "sell"] as const) {
    const c = s.said[key];
    if (c.n > 0) {
      out.push(
        `${INTENT_LABEL[key]} ${c.n}번 — 말한 대로 체결 ${c.as_said} · 다른 체결 ${c.other} · 체결 없음 ${c.none}`,
      );
    }
  }
  const nh = s.not_happened;
  if (nh.n > 0) {
    const open = nh.open > 0 ? ` · 아직 ${s.later_days}일이 안 됨 ${nh.open}` : "";
    out.push(
      `종목을 적고 체결 없이 끝난 ${nh.n}번 중 ${s.later_days}일 안에 그 종목 체결 ${nh.later} · 체결 없음 ${nh.never}${open}`,
    );
  }
  if (s.fills.total > 0) {
    out.push(`이 기간 체결 ${s.fills.total}건 중 ${s.fills.through_door}건이 문을 거쳤어요.`);
  }
  return out;
}

/**
 * One fact line with its short count pieces kept whole — at phone width
 * "체결 / 없음 6" split across lines (2026-10-15 browser check). Pieces
 * between " — " / " · " up to 14 characters do not wrap inside; longer
 * pieces wrap as usual. The text is unchanged.
 */
export function FactLine({ text }: { text: string }) {
  const parts = text.split(/( — | · )/);
  return (
    <>
      {parts.map((p, i) =>
        p === " — " || p === " · " || p.length > 14 ? (
          <React.Fragment key={i}>{p}</React.Fragment>
        ) : (
          <span key={i} className="whitespace-nowrap">
            {p}
          </span>
        ),
      )}
    </>
  );
}

function IntentBars({ s }: { s: DoorwaySummaryResponse }) {
  const top = Math.max(1, ...INTENT_ORDER.map((k) => s.intents[k] ?? 0));
  return (
    <ul className="mt-4 space-y-2" data-testid="doorway-intents">
      {INTENT_ORDER.map((k) => {
        const n = s.intents[k] ?? 0;
        return (
          <li key={k} className="flex items-center gap-3">
            <span className="w-[72px] shrink-0 text-[12.5px]" style={{ color: DIM }}>
              {INTENT_LABEL[k]}
            </span>
            <span className="relative h-2 flex-1 rounded-full" style={{ background: "rgba(var(--pq-ivory-rgb), 0.06)" }}>
              <span
                className="absolute inset-y-0 left-0 rounded-full"
                style={{ width: `${(n / top) * 100}%`, background: "var(--pq-bronze)" }}
              />
            </span>
            <span className="w-8 shrink-0 text-right text-[13px] tabular-nums" style={{ color: "var(--pq-ivory)" }}>
              {n}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** 24 thin bars, one per KST hour — when the door was opened. */
function HourStrip({ hours }: { hours: number[] }) {
  if (!Array.isArray(hours) || hours.length !== 24 || hours.every((n) => !n)) return null;
  const top = Math.max(1, ...hours);
  return (
    <figure className="mt-5" data-testid="doorway-hours">
      <div className="flex h-10 items-end gap-[2px]" aria-hidden>
        {hours.map((n, h) => (
          <div
            key={h}
            className="flex-1 rounded-t-[2px]"
            style={{
              height: n > 0 ? `${Math.max(8, (n / top) * 100)}%` : 0,
              background: "var(--pq-bronze)",
              opacity: 0.75,
            }}
            title={`${h}시 · ${n}번`}
          />
        ))}
      </div>
      <div
        className="mt-1 flex justify-between text-[12px] tabular-nums"
        style={{ color: DIM, borderTop: "1px solid var(--pq-ivory-line)", paddingTop: 2 }}
        aria-hidden
      >
        <span>0시</span>
        <span>6시</span>
        <span>12시</span>
        <span>18시</span>
        <span>24시</span>
      </div>
      <figcaption className="mt-1 text-[12px]" style={{ color: DIM }}>
        언제 열었나 · 한국 시간
        <span className="sr-only">
          {hours.map((n, h) => (n > 0 ? `${h}시 ${n}번. ` : "")).join("")}
        </span>
      </figcaption>
    </figure>
  );
}

function RecentRow({ r }: { r: DoorwayRecent }) {
  const what = r.note || r.name;
  return (
    <li className="py-2.5" style={{ borderBottom: "1px solid var(--pq-ivory-line)" }} data-testid="doorway-recent">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[12px] tabular-nums" style={{ color: DIM }}>
          {kstStamp(r.at)} · {INTENT_LABEL[r.intent] ?? r.intent}
        </span>
        <span
          className="shrink-0 rounded-full px-2 py-0.5 text-[12px]"
          style={{
            color: r.outcome === "none" ? DIM : "var(--pq-bronze)",
            border: `1px solid ${r.outcome === "none" ? "var(--pq-ivory-line)" : "var(--pq-bronze)"}`,
          }}
        >
          {OUTCOME_LABEL[r.outcome] ?? r.outcome}
        </span>
      </div>
      {what && (
        <p className="mt-0.5 text-[13.5px] leading-snug" style={{ color: "var(--pq-ivory)" }}>
          {what}
        </p>
      )}
    </li>
  );
}

function Frame({
  bordered,
  children,
  testId = "doorway-panel",
}: {
  bordered: boolean;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section
      className={bordered ? "rounded-[var(--pq-radius-card)] p-4" : undefined}
      style={bordered ? { border: "1px solid var(--pq-ivory-line)" } : undefined}
      aria-label="문 앞"
      data-testid={testId}
    >
      {children}
    </section>
  );
}

export function DoorwayPanelView({
  data,
  bordered = true,
  invite = false,
}: {
  data: DoorwaySummaryResponse;
  bordered?: boolean;
  /** Show the one-line invite when the user never set the door up. */
  invite?: boolean;
}) {
  if (!data.first_check_at) {
    if (!invite) return null;
    return (
      <Frame bordered={bordered} testId="doorway-invite">
        <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
          문 앞의 한 줄
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed" style={{ color: DIM }}>
          증권 앱을 열 때 폰이 &ldquo;뭘 하러 왔어요?&rdquo;를 한 번 묻게 할 수 있어요. 답은 여기
          쌓이고, 그 뒤 체결과 나란히 보여드려요.
        </p>
        <Link
          href={DOORWAY_SETTINGS_HREF}
          className="mt-2 inline-block text-[12.5px] underline underline-offset-2"
          style={{ color: "var(--pq-bronze)" }}
        >
          설정 안내 보기 →
        </Link>
      </Frame>
    );
  }

  const facts = doorwayFacts(data);
  return (
    <Frame bordered={bordered}>
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
          문 앞
        </div>
        <span className="text-[12px]" style={{ color: DIM }}>
          최근 {data.window_days}일
        </span>
      </div>

      {data.total === 0 ? (
        <>
          <p className="mt-2 text-[13px] leading-relaxed" style={{ color: DIM }}>
            최근 {data.window_days}일 동안 문 앞 기록이 없어요. 폰의 자동화가 꺼져 있지 않은지
            확인해 보세요.
          </p>
          <Link
            href={DOORWAY_SETTINGS_HREF}
            className="mt-2 inline-block text-[12.5px] underline underline-offset-2"
            style={{ color: "var(--pq-bronze)" }}
          >
            설정 확인 →
          </Link>
        </>
      ) : (
        <>
          <p className="mt-2 text-[1.35rem] leading-snug tabular-nums" style={{ color: "var(--pq-ivory)" }}>
            증권 앱을 {data.total}번 열었어요
          </p>

          <IntentBars s={data} />

          {facts.length > 0 && (
            <ul className="mt-4 space-y-1.5" data-testid="doorway-facts">
              {facts.map((f) => (
                <li key={f} className="text-[13px] leading-relaxed" style={{ color: DIM }}>
                  <FactLine text={f} />
                </li>
              ))}
            </ul>
          )}

          <HourStrip hours={data.by_hour_kst} />

          {data.recent.length > 0 && (
            <ul className="mt-4" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
              {data.recent.slice(0, 5).map((r, i) => (
                <RecentRow key={r.id ?? `${r.at}-${i}`} r={r} />
              ))}
            </ul>
          )}

          {data.caveats.length > 0 && (
            <details className="mt-3">
              <summary className="pq-hit cursor-pointer text-[12px]" style={{ color: DIM }}>
                이렇게 셉니다
              </summary>
              <ul className="mt-1.5 space-y-1">
                {data.caveats.map((c) => (
                  <li key={c} className="text-[12px] leading-relaxed" style={{ color: DIM }}>
                    {c}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </Frame>
  );
}

/** Fetching wrapper — renders nothing while loading or on error. */
export function DoorwayPanel({ bordered = true, invite = false }: { bordered?: boolean; invite?: boolean }) {
  const { data } = useDoorwaySummary(30);
  if (!data) return null;
  return <DoorwayPanelView data={data} bordered={bordered} invite={invite} />;
}

export default DoorwayPanel;
