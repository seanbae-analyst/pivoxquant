/**
 * TwinWeekCard — last week's AI-twin paper return vs the user's realised return.
 *
 * Descriptive only ("트윈이 X%p 앞섰어요"), never prospective or advisory — the
 * twin trades paper only and the read path attaches the standard disclaimer.
 * Returns use the KR price-direction convention (carmine up / indigo down) via
 * lib/format.ts, the single source of truth. No italic.
 */
import * as React from "react";
import { fmtPct, pctColor } from "@/lib/format";
import type { MirrorTwinWeek } from "@/lib/types";

function diffSentence(diff: number | null): string | null {
  if (diff === null) return null;
  const mag = fmtPct(Math.abs(diff));
  if (Math.abs(diff) < 0.005) return "이번 주는 트윈과 거의 같았어요.";
  return diff > 0
    ? `트윈이 ${mag} 앞섰어요.`
    : `당신이 ${mag} 앞섰어요.`;
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <div className="text-[10px]" style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}>
        {label}
      </div>
      <div
        className="text-[21px] tabular-nums"
        style={{
          fontFamily: "var(--pq-font-mono)",
          color: value === null ? "rgba(var(--pq-ivory-rgb), 0.55)" : pctColor(value),
        }}
      >
        {value === null ? "—" : fmtPct(value)}
      </div>
    </div>
  );
}

export function TwinWeekCard({ twin }: { twin: MirrorTwinWeek | null }) {
  return (
    <section
      className="rounded-[4px] p-4"
      style={{ border: "1px solid var(--pq-ivory-line)" }}
    >
      <div
        className="text-[10.5px] uppercase tracking-[0.2em]"
        style={{ color: "var(--pq-bronze)" }}
      >
        나의 트윈 · 지난주
      </div>

      {twin === null ? (
        <p
          className="mt-3 text-[13px] leading-relaxed"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
        >
          주간 비교가 아직 없어요. 트윈의 페이퍼 기록이 한 주 쌓이면 여기 표시됩니다.
        </p>
      ) : (
        <>
          <div className="mt-3 flex items-end gap-6">
            <Stat label="나" value={twin.user_return_pct} />
            <span
              className="pb-1 text-[18px]"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.35)" }}
            >
              ·
            </span>
            <Stat label="트윈 (페이퍼)" value={twin.twin_return_pct} />
            {twin.diff_pct !== null && (
              <div className="ml-auto text-right">
                <div
                  className="text-[10px]"
                  style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
                >
                  차이
                </div>
                <div
                  className="text-[17px] tabular-nums"
                  style={{ fontFamily: "var(--pq-font-mono)", color: "var(--pq-bronze)" }}
                >
                  {fmtPct(Math.abs(twin.diff_pct))}
                </div>
              </div>
            )}
          </div>

          {diffSentence(twin.diff_pct) && (
            <p
              className="mt-3 text-[12.5px] leading-relaxed"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
            >
              {diffSentence(twin.diff_pct)}
            </p>
          )}
        </>
      )}
    </section>
  );
}
