/**
 * MirrorRadarPanel — the 「선언 vs 관찰」 block of /mirror: title, legend, the
 * 9-axis SelfObservedRadar and its one-line key.
 *
 * Lifted out of mirror/page.tsx (2026-10-09) so the desktop column and the
 * phone story card render the same block — same props, same copy. Shape
 * only: the radar prints the observed % per measured axis and "—" for an
 * unmeasured one; nothing is scored. No italic.
 */
import * as React from "react";

import type { MirrorHomeResponse } from "@/lib/types";
import { SelfObservedRadar } from "@/components/mirror/self-observed-radar";

function LegendDot({ colorVar, label }: { colorVar: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: `var(${colorVar})` }}
      />
      {label}
    </span>
  );
}

/** Per-axis "measured?" flags in radar order, or undefined for an older
 *  backend that does not send `observed_axes` (= every axis measured). */
function measuredAxes(radar: MirrorHomeResponse["radar"]): boolean[] | undefined {
  const observedAxes = radar.observed_axes;
  return observedAxes ? radar.keys.map((k) => observedAxes.includes(k)) : undefined;
}

export function MirrorRadarPanel({
  data,
  bordered = true,
}: {
  data: MirrorHomeResponse;
  /** The desktop column frames it; the phone card is already a frame. */
  bordered?: boolean;
}) {
  return (
    <section
      className={bordered ? "rounded-[4px] p-4" : undefined}
      style={bordered ? { border: "1px solid var(--pq-ivory-line)" } : undefined}
      data-testid="mirror-radar-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
          선언 vs 관찰
        </div>
        <div
          className="flex items-center gap-3 text-[10.5px]"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
        >
          <LegendDot colorVar="--pq-bronze" label="선언(설문)" />
          <LegendDot colorVar="--pq-ivory" label="관찰(30일)" />
        </div>
      </div>

      <div className="mt-2 flex justify-center">
        <SelfObservedRadar
          className="w-full max-w-[460px]"
          labels={data.radar.labels}
          declared={data.radar.declared}
          observed={data.radar.observed}
          measured={measuredAxes(data.radar)}
        />
      </div>

      <p className="mt-1 text-center text-[10.5px]" style={{ color: "var(--pq-bronze)" }}>
        각 축의 % = 최근 30일 관찰값 · — = 아직 잴 기록이 부족 · 브론즈=선언, 아이보리=관찰
      </p>
    </section>
  );
}
