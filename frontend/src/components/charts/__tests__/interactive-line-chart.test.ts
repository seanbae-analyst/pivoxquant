import { describe, it, expect } from "vitest";
import {
  computeMarkerGeom,
  type ChartMarker,
  type InteractivePoint,
} from "@/components/charts/interactive-line-chart";

// Unit coverage for the observation-marker snapping logic that powers the
// detail chart's signal ticks. Previously an inline useMemo with no tests.

const pts: InteractivePoint[] = [
  { date: "2026-05-01", value: 100 },
  { date: "2026-05-02", value: 110 },
  { date: "2026-05-03", value: 105 },
  { date: "2026-05-04", value: 120 },
];
// Pretend pixel coords parallel to the points (one per index).
const xs = [0, 10, 20, 30];
const ys = [40, 30, 35, 20];

describe("computeMarkerGeom", () => {
  it("snaps a marker to the nearest charted point by date", () => {
    const markers: ChartMarker[] = [{ date: "2026-05-03", tone: "positive" }];
    const out = computeMarkerGeom(markers, pts, xs, ys);
    expect(out).toHaveLength(1);
    expect(out[0].x).toBe(20); // index 2
    expect(out[0].y).toBe(35);
  });

  it("snaps to the closest point when the date is between samples", () => {
    // 12:00 on the 3rd is closer to the 3rd than the 4th.
    const out = computeMarkerGeom(
      [{ date: "2026-05-03T12:00:00", tone: "neutral" }],
      pts,
      xs,
      ys,
    );
    expect(out[0].x).toBe(20);
  });

  it("drops markers further than windowDays from any point", () => {
    const out = computeMarkerGeom(
      [{ date: "2026-04-01", tone: "negative" }], // ~30 days before
      pts,
      xs,
      ys,
    );
    expect(out).toHaveLength(0);
  });

  it("keeps a marker within the default 5-day window", () => {
    const out = computeMarkerGeom(
      [{ date: "2026-05-06", tone: "positive" }], // 2 days after last point
      pts,
      xs,
      ys,
    );
    expect(out).toHaveLength(1);
    expect(out[0].x).toBe(30); // snapped to last point
  });

  it("respects a custom windowDays", () => {
    const near = computeMarkerGeom(
      [{ date: "2026-05-10", tone: "neutral" }], // 6 days after last
      pts,
      xs,
      ys,
      { windowDays: 7 },
    );
    expect(near).toHaveLength(1);
  });

  it("maps tone → KR-convention price-direction colour", () => {
    const out = computeMarkerGeom(
      [
        { date: "2026-05-01", tone: "positive" },
        { date: "2026-05-02", tone: "negative" },
        { date: "2026-05-03", tone: "neutral" },
      ],
      pts,
      xs,
      ys,
    );
    expect(out[0].color).toContain("--up"); // rise = carmine
    expect(out[1].color).toContain("--down"); // fall = indigo
    expect(out[2].color).toContain("245,240,232"); // neutral ivory
  });

  it("uses label when present, else falls back to tone", () => {
    const out = computeMarkerGeom(
      [
        { date: "2026-05-01", tone: "positive", label: "긍정 · 0.91" },
        { date: "2026-05-02", tone: "negative" },
      ],
      pts,
      xs,
      ys,
    );
    expect(out[0].label).toBe("긍정 · 0.91");
    expect(out[1].label).toBe("negative");
  });

  it("skips markers with an unparseable date", () => {
    const out = computeMarkerGeom(
      [
        { date: "not-a-date", tone: "positive" },
        { date: "2026-05-02", tone: "neutral" },
      ],
      pts,
      xs,
      ys,
    );
    expect(out).toHaveLength(1);
    expect(out[0].x).toBe(10);
  });

  it("returns [] in compact mode", () => {
    expect(
      computeMarkerGeom([{ date: "2026-05-02", tone: "positive" }], pts, xs, ys, {
        compact: true,
      }),
    ).toEqual([]);
  });

  it("returns [] with fewer than 2 points or no markers", () => {
    expect(computeMarkerGeom([{ date: "2026-05-02", tone: "positive" }], [pts[0]], [0], [0])).toEqual([]);
    expect(computeMarkerGeom([], pts, xs, ys)).toEqual([]);
    expect(computeMarkerGeom(undefined, pts, xs, ys)).toEqual([]);
  });
});
