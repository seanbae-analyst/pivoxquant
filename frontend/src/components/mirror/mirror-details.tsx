"use client";

/**
 * MirrorDetails — 「자세히」: a collapsed area under the mirror.
 *
 * 2026-09-12 — /profile was decomposed (founder decision 2026-09-10). Of its
 * persona blocks, only the weekly evolution adds something this page lacks: a
 * time axis. The observed-persona card and the six-dimension grid were
 * dropped, not moved — both redrew the 9 axes that the radar and gap chips
 * above already show, and the observed bucket label is already in the
 * headline sentence.
 *
 * Collapsed by default. PersonaEvolution mounts only when opened.
 *
 * Legal: PersonaEvolution renders labels through PERSONA_LABELS, which
 * collapses all 8 engine codes into the 3 disclosed buckets
 * (성장형 / 균형형 / 수익형). No italic.
 */
import * as React from "react";
import { ChevronDown } from "lucide-react";

import { PersonaEvolution } from "@/components/dashboard/persona-evolution";

export function MirrorDetails() {
  const [open, setOpen] = React.useState(false);

  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-[4px] px-4 py-3 text-left"
        style={{ border: "1px solid var(--pq-ivory-line)" }}
      >
        <span>
          <span
            className="block text-[10.5px] uppercase tracking-[0.2em]"
            style={{ color: "var(--pq-bronze)" }}
          >
            자세히 · Details
          </span>
          <span
            className="mt-0.5 block text-[11px]"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
          >
            관찰된 흐름을 주 단위로 보기
          </span>
        </span>
        <ChevronDown
          className="h-3.5 w-3.5 shrink-0 transition-transform duration-200"
          style={{
            color: "var(--pq-bronze)",
            transform: open ? "rotate(180deg)" : undefined,
          }}
          aria-hidden
        />
      </button>

      {open && (
        <div
          className="mt-2 rounded-[4px] p-4"
          style={{ border: "1px solid var(--pq-ivory-line)" }}
        >
          <PersonaEvolution bare />
        </div>
      )}
    </section>
  );
}

export default MirrorDetails;
