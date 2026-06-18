/**
 * OneThingNudge — a single observational line that hands off to 「멈춤」
 * (pre-trade friction). The behavioural loop's entry: 멈춤 → 기록 → 거울.
 *
 * Legal: observational, never directive. It does not tell the user to buy,
 * sell, or do anything with a security — only to pause and reflect before
 * their own next decision. No italic.
 */
import * as React from "react";
import Link from "next/link";
import type { MirrorHomeResponse } from "@/lib/types";

function nudgeText(d: MirrorHomeResponse): string {
  if (d.stage === "new") {
    return "첫 주문을 「멈춤」을 거쳐 기록해보세요 — 거울이 채워지기 시작해요.";
  }
  const top = d.gap[0];
  if (top && top.key === "turnover" && top.direction === "up") {
    return "최근 매매 회전율이 선언보다 높게 관찰돼요. 다음 주문 전 「멈춤」에서 한 박자 두실 수 있어요.";
  }
  if (top) {
    return `최근 ${top.label}이(가) 선언과 가장 다르게 관찰돼요. 다음 결정은 「멈춤」에서 천천히 봐도 괜찮아요.`;
  }
  return "다음 주문은 「멈춤」을 거쳐 기록해보세요.";
}

export function OneThingNudge({ data }: { data: MirrorHomeResponse }) {
  return (
    <section className="pl-3" style={{ borderLeft: "2px solid var(--pq-bronze)" }}>
      <div
        className="text-[10.5px] uppercase tracking-[0.2em]"
        style={{ color: "var(--pq-bronze)" }}
      >
        한 가지만
      </div>
      <p
        className="mt-1.5 text-[13.5px] leading-relaxed"
        style={{ color: "var(--pq-ivory)" }}
      >
        {nudgeText(data)}
      </p>
      <Link
        href="/pre-trade"
        className="mt-2 inline-block text-[12.5px] underline underline-offset-2"
        style={{ color: "var(--pq-bronze)" }}
      >
        멈춤으로 가기 →
      </Link>
    </section>
  );
}
