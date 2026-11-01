/**
 * OneThingNudge — a single observational line that hands off to 「멈춤」
 * (pre-trade friction). The behavioural loop's entry: 멈춤 → 기록 → 거울.
 * Before any observation it hands off to the fills that start one.
 *
 * Legal: observational, never directive. It does not tell the user to buy,
 * sell, or do anything with a security — only to pause and reflect before
 * their own next decision. No italic.
 */
import * as React from "react";
import Link from "next/link";
import { josa } from "@/lib/josa";
import type { MirrorHomeResponse } from "@/lib/types";

function nudgeText(d: MirrorHomeResponse): string {
  if (d.stage === "new") {
    const fills = d.total_fills ?? 0;
    return fills > 0
      ? `체결 ${fills}건이 기록돼 있어요. 최근 30일 체결이 5건을 넘기면 이 화면의 관찰이 시작되고, 습관 탭에서는 쌓인 만큼 볼 수 있어요.`
      : "체결 내역을 넣으면 거울이 채워지기 시작해요.";
  }
  const top = d.gap[0];
  if (top && top.key === "turnover" && top.direction === "up") {
    return "최근 매매 회전율이 선언보다 높게 관찰돼요. 다음 주문 전 「멈춤」에서 한 박자 두실 수 있어요.";
  }
  if (top) {
    return `최근 ${josa(top.label, "이/가")} 선언과 가장 다르게 관찰돼요. 다음 결정은 「멈춤」에서 천천히 봐도 괜찮아요.`;
  }
  return "다음 주문은 「멈춤」을 거쳐 기록해보세요.";
}

/** Where the line leads. A new user has no fills to reflect yet, so the first
 *  hand-off is the import; 멈춤 is for the next order. */
function nudgeLink(d: MirrorHomeResponse): { href: string; label: string } {
  if (d.stage === "new") {
    return (d.total_fills ?? 0) > 0
      ? { href: "/journal#habits", label: "습관 보기 →" }
      : { href: "/journal/import", label: "체결 가져오기 →" };
  }
  return { href: "/pre-trade", label: "멈춤으로 가기 →" };
}

export function OneThingNudge({ data }: { data: MirrorHomeResponse }) {
  const link = nudgeLink(data);
  return (
    <section className="pl-3" style={{ borderLeft: "2px solid var(--pq-bronze)" }}>
      <div
        className="text-[12px] font-medium tracking-[0.01em]"
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
        href={link.href}
        className="pq-hit mt-2 inline-block text-[12.5px] underline underline-offset-2"
        style={{ color: "var(--pq-bronze)" }}
      >
        {link.label}
      </Link>
    </section>
  );
}
