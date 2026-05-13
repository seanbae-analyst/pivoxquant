"use client";

/**
 * <SignalsTimelineGrid /> — chronological signal stream grouped by day.
 *
 * Source: design-mockups/signals-v2/SPEC.md §4.
 * Renders a vertical list of <SignalCard /> rows with day-rule headings.
 *
 * Handles isLoading skeleton, empty state, and live-region a11y.
 */

import * as React from "react";
import type { SignalEntry } from "@/lib/types";
import { SignalCard } from "./signal-card";

interface Props {
  entries: SignalEntry[];
  isLoading?: boolean;
  resolveName: (ticker: string) => string;
}

function dayKey(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "unknown";
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  } catch {
    return "unknown";
  }
}

function dayHeading(iso: string | null | undefined): { weekday: string; meta: string } {
  // CEO directive 2026-05-13: 한국어 요일/날짜 표기.
  if (!iso) return { weekday: "이전", meta: "날짜 정보 없음" };
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return { weekday: "이전", meta: "날짜 정보 없음" };
    const weekday = d.toLocaleDateString("ko-KR", { weekday: "long" }); // "월요일"
    const meta = d.toLocaleDateString("ko-KR", {
      month: "long",
      day: "numeric",
    }); // "5월 13일"
    return { weekday, meta };
  } catch {
    return { weekday: "이전", meta: "날짜 정보 없음" };
  }
}

// CEO directive 2026-05-13: 동일 시간대 내에서 한국 종목 우선.
function isKr(s: SignalEntry): boolean {
  if (s.is_korean === true) return true;
  if (s.currency === "KRW") return true;
  const t = (s.ticker ?? "").toUpperCase();
  return t.endsWith(".KS") || t.endsWith(".KQ") || t.endsWith(".KRX");
}

export function SignalsTimelineGrid({ entries, isLoading, resolveName }: Props) {
  const grouped = React.useMemo(() => {
    // CEO 2026-05-13: 동일 day-bucket 내에서 KR 종목 우선. 일 단위
    // 그룹핑은 시간 desc로 유지 (chronological stream 보존).
    const sorted = [...entries].sort((a, b) => {
      const av = a.observed_at ? new Date(a.observed_at).getTime() : 0;
      const bv = b.observed_at ? new Date(b.observed_at).getTime() : 0;
      if (av !== bv) return bv - av;
      const aKr = isKr(a);
      const bKr = isKr(b);
      if (aKr !== bKr) return aKr ? -1 : 1;
      return 0;
    });
    const out: Array<{ key: string; heading: ReturnType<typeof dayHeading>; rows: SignalEntry[] }> = [];
    let last = "";
    for (const s of sorted) {
      const k = dayKey(s.observed_at);
      if (k !== last) {
        out.push({ key: k, heading: dayHeading(s.observed_at), rows: [] });
        last = k;
      }
      out[out.length - 1].rows.push(s);
    }
    return out;
  }, [entries]);

  if (isLoading && entries.length === 0) {
    return (
      <section style={{ marginBottom: 56 }} aria-busy="true">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
            marginBottom: 8,
          }}
        >
          스트림 · 불러오는 중
        </div>
        <div
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            color: "rgba(245,240,232,0.55)",
            padding: "48px 0",
            textAlign: "center",
          }}
        >
          관측을 읽고 있습니다…
        </div>
      </section>
    );
  }

  if (entries.length === 0) {
    return (
      <section style={{ marginBottom: 56 }}>
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze, #B8956A)",
            marginBottom: 8,
          }}
        >
          스트림 · 비어 있음
        </div>
        <div
          style={{
            border: "1px dashed var(--pq-hairline-2, rgba(245,240,232,0.14))",
            borderRadius: "var(--pq-radius-card, 4px)",
            padding: "48px 24px",
            textAlign: "center",
          }}
        >
          <div
            className="font-display"
            style={{
              fontSize: "var(--pq-text-quote)",
              // CEO bug "폰트 겹친다" — heading 1.05 → 1.3 for KR descenders.
              lineHeight: 1.3,
              color: "var(--pq-ivory, #F5F0E8)",
              marginBottom: 8,
            }}
          >
            조건에 맞는 관측이 없습니다.
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.55)",
            }}
          >
            강도 범위를 넓히거나 기간을 늘려 다시 확인해 보세요.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section style={{ marginBottom: 56 }} aria-live="polite" aria-relevant="additions">
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze, #B8956A)",
          marginBottom: 8,
        }}
      >
        스트림 · 관측 {entries.length}건
      </div>
      <h2
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3vw, 40px)",
          // CEO bug "폰트 겹친다": Playfair heading + KR mixed glyph
          // 줄간격 확보.
          lineHeight: 1.2,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 22px 0",
        }}
      >
        오늘의 관측.
      </h2>

      {grouped.map((group) => (
        <div key={group.key}>
          {/* day rule */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "auto auto 1fr",
              gap: 16,
              alignItems: "baseline",
              padding: "20px 0 8px",
              borderTop: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
              marginTop: 8,
            }}
          >
            <h3
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-quote)",
                // CEO bug "폰트 겹친다" — KR 요일명("화요일")이 baseline-
                // hugging Playfair에 들어가면 디센더 충돌. 1.3 lock-in.
                lineHeight: 1.3,
                letterSpacing: "-0.01em",
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
              }}
            >
              {group.heading.weekday}
            </h3>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              {group.heading.meta} · 관측 {group.rows.length}건
            </span>
            <span aria-hidden style={{ display: "block", height: 1 }} />
          </div>

          {/* rows */}
          <div>
            {group.rows.map((s, idx) => (
              <SignalCard
                key={`${s.ticker}-${s.id ?? idx}-${s.observed_at ?? ""}`}
                entry={s}
                resolveName={resolveName}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
