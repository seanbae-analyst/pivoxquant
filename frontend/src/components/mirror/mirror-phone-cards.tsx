"use client";

/**
 * <MirrorPhoneCards /> — /mirror on a phone (<768px, incl. the installed PWA)
 * as a row of full-width story cards you swipe between.
 *
 * CEO 2026-10-09 ("앱처럼"). The desktop column reads top to bottom:
 * headline sentence → gap chips + drift → radar → one nudge. On a phone each
 * of those becomes its own card, in the same order the page already tells it:
 *
 *   1. 오늘의 거울  — the one sentence (leadSentence), nothing else
 *   2. 선언 vs 관찰 — the radar block, identical to desktop (MirrorRadarPanel)
 *   3. 간극        — every gap row the backend sent + the drift descriptor.
 *                    Dropped when there is neither: an empty card would only
 *                    repeat card 1's "아직 쌓이지 않았어요".
 *   4. 한 가지만    — OneThingNudge → 「멈춤」
 *
 * Same data object, same components and copy as desktop — only the
 * arrangement differs. The pager is the shared PhonePager in "dots" mode
 * (no tab strip; the dots are the tablist), so a card reads like a story.
 *
 * Legal: no scores, grades or type labels; the gap is direction + %p only,
 * exactly what the desktop chips print. Observational copy, no advice. The
 * disclaimer is mounted once by (dashboard)/layout.tsx, not here. No italic.
 */
import * as React from "react";

import type { MirrorGapDimension, MirrorHomeResponse } from "@/lib/types";
import { PhonePager, type PhonePage } from "@/components/portfolio/v2/phone-pager";
import {
  DriftChip,
  MirrorLead,
  directionWord,
  gapMagnitude,
} from "@/components/mirror/mirror-headline";
import { MirrorRadarPanel } from "@/components/mirror/mirror-radar-panel";
import { OneThingNudge } from "@/components/mirror/one-thing-nudge";

const DIM = "rgba(var(--pq-ivory-rgb), 0.55)";

/** Full-height frame of one story card; scrolls with its page if taller.
 *  Each card carries its own title, and the dots under the track say where
 *  in the row it sits, so the frame adds no heading of its own. `wide`
 *  trims the side padding so the radar's axis labels get the width. */
function StoryCard({ wide = false, children }: { wide?: boolean; children: React.ReactNode }) {
  return (
    <div
      className={`flex min-h-full flex-col rounded-[4px] pb-6 pt-5 ${wide ? "px-3" : "px-5"}`}
      style={{ border: "1px solid var(--pq-ivory-line)" }}
    >
      {children}
    </div>
  );
}

function SwipeHint() {
  return (
    <p className="pt-8 text-[12px]" style={{ color: DIM }} aria-hidden>
      옆으로 넘기면 선언과 관찰을 나란히 볼 수 있어요 →
    </p>
  );
}

function GapRow({ dim }: { dim: MirrorGapDimension }) {
  return (
    <li
      className="flex items-baseline justify-between gap-3 py-3"
      style={{ borderBottom: "1px solid var(--pq-ivory-line)" }}
    >
      <span className="text-[14px]" style={{ color: "var(--pq-ivory)" }}>
        {dim.label}
      </span>
      <span className="flex shrink-0 items-baseline gap-2 text-[12.5px]" style={{ color: DIM }}>
        선언보다 {directionWord(dim)}
        <span style={{ color: "var(--pq-bronze)", fontFamily: "var(--pq-font-mono)" }}>
          {gapMagnitude(dim)}
        </span>
      </span>
    </li>
  );
}

function GapCard({ data }: { data: MirrorHomeResponse }) {
  return (
    <section aria-label="간극">
      <div
        className="text-[10.5px] uppercase tracking-[0.25em]"
        style={{ color: "var(--pq-bronze)" }}
      >
        간극
      </div>
      <h2
        className="mt-3 text-[1.25rem] leading-[1.4]"
        style={{ fontFamily: "var(--pq-font-display)", color: "var(--pq-ivory)" }}
      >
        선언 대비 최근 30일
      </h2>

      {data.gap.length > 0 && (
        <ul className="mt-4" style={{ borderTop: "1px solid var(--pq-ivory-line)" }}>
          {data.gap.map((dim) => (
            <GapRow key={dim.key} dim={dim} />
          ))}
        </ul>
      )}

      <DriftChip data={data} className="mt-5" />

      <p className="mt-5 text-[11.5px] leading-relaxed" style={{ color: DIM }}>
        ↑↓ = 최근 30일이 선언보다 높게·낮게 관찰된 방향 · %p = 선언에서 벗어난 정도
      </p>
    </section>
  );
}

/** Whether the 간극 card has anything of its own to show. */
export function hasGapCard(data: MirrorHomeResponse): boolean {
  return data.gap.length > 0 || Boolean(data.drift.available && data.drift.descriptor);
}

type CardSpec = { id: string; label: string; wide?: boolean; body: React.ReactNode };

function cardSpecs(data: MirrorHomeResponse): CardSpec[] {
  const cards: CardSpec[] = [
    {
      id: "today",
      label: "오늘의 거울",
      body: (
        <>
          {/* The sentence sits in the optical middle; the hint at the foot. */}
          <div className="my-auto pt-8">
            <MirrorLead data={data} className="mt-4 text-[1.7rem] leading-[1.45]" />
          </div>
          <SwipeHint />
        </>
      ),
    },
    {
      id: "radar",
      label: "선언 vs 관찰",
      wide: true,
      body: (
        <div className="my-auto">
          <MirrorRadarPanel data={data} bordered={false} />
        </div>
      ),
    },
  ];
  if (hasGapCard(data)) {
    cards.push({ id: "gap", label: "간극", body: <GapCard data={data} /> });
  }
  cards.push({
    id: "one-thing",
    label: "한 가지만",
    body: (
      <div className="my-auto">
        <OneThingNudge data={data} />
      </div>
    ),
  });
  return cards;
}

export function MirrorPhoneCards({
  data,
  header,
}: {
  data: MirrorHomeResponse;
  /** Shown above the cards (e.g. a revalidation error line). */
  header?: React.ReactNode;
}) {
  const pages: PhonePage[] = cardSpecs(data).map((c) => ({
    id: c.id,
    label: c.label,
    content: <StoryCard wide={c.wide}>{c.body}</StoryCard>,
  }));
  return <PhonePager label="거울 카드" pages={pages} header={header} nav="dots" />;
}

export default MirrorPhoneCards;
