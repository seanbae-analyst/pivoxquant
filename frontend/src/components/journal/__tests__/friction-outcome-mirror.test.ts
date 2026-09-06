import { describe, it, expect } from "vitest";
import {
  buildFrictionOutcomeView,
} from "@/components/journal/friction-outcome-mirror";
import type { FrictionOutcomeResponse } from "@/lib/types";

/**
 * The first fixture below is a VERBATIM capture of a live response:
 *
 *   GET /api/behavior/friction-outcome   (2026-09-02, local backend, user 1)
 *
 * Recording the real shape matters more than a hand-written one here. The
 * route was added the same day and this is the payload the component will
 * actually receive — including the case that matters most, where the service
 * itself refuses the comparison (`comparable: false` because `with_friction`
 * has n=0, under `min_group_n` 5) while `without_friction` DOES carry real
 * percentages. A view that leaked those numbers anyway would look perfectly
 * fine in a hand-written "empty" fixture and be wrong in production.
 */
const LIVE_CAPTURE: FrictionOutcomeResponse = {
  ok: true,
  period: "all",
  window_days: null,
  disclaimer:
    "본 정보는 지난 거래의 회고적 사실 관찰이며 미래 예측이나 거래 권유가 아닙니다.",
  stopped: { started: 5, proceeded: 2, cancelled: 0, open: 3 },
  cancelled_followthrough: {
    cancelled: 0,
    bought_later_anyway: 0,
    never_bought: 0,
    median_days_until_bought: null,
  },
  realised: {
    with_friction: { n: 0, median_pct: null, mean_pct: null },
    without_friction: { n: 3, median_pct: -3.64, mean_pct: -1.15 },
    comparable: false,
    min_group_n: 5,
  },
  caveats: {
    not_randomised: true,
    attribution_window_days: 7,
    cooldown_seconds_currently: 0,
  },
  insufficient: false,
};

function withComparison(): FrictionOutcomeResponse {
  return {
    ...LIVE_CAPTURE,
    stopped: { started: 22, proceeded: 14, cancelled: 6, open: 2 },
    cancelled_followthrough: {
      cancelled: 6,
      bought_later_anyway: 2,
      never_bought: 4,
      median_days_until_bought: 3,
    },
    realised: {
      with_friction: { n: 8, median_pct: 2.4, mean_pct: 1.9 },
      without_friction: { n: 11, median_pct: -3.64, mean_pct: -1.15 },
      comparable: true,
      min_group_n: 5,
    },
  };
}

describe("buildFrictionOutcomeView", () => {
  it("maps the live backend capture without losing a field", () => {
    const v = buildFrictionOutcomeView(LIVE_CAPTURE)!;
    expect(v.hasData).toBe(true);
    expect(v.started).toBe(5);
    expect(v.proceeded).toBe(2);
    expect(v.open).toBe(3);
    expect(v.cancelled).toBe(0);
    expect(v.minGroupN).toBe(5);
    expect(v.attributionWindowDays).toBe(7);
  });

  it("honours the service's refusal to compare", () => {
    // This is the whole point of `comparable`. `without_friction` carries
    // real numbers (n=3, median -3.64) — surfacing them while the other
    // group is empty would show a one-sided figure as if it were a finding.
    const v = buildFrictionOutcomeView(LIVE_CAPTURE)!;
    expect(v.showDistributions).toBe(false);
    expect(v.withoutFriction.n).toBe(3);
    expect(v.withoutFriction.median).toBe(-3.64);
  });

  it("only shows distributions when the service says comparable", () => {
    const v = buildFrictionOutcomeView(withComparison())!;
    expect(v.showDistributions).toBe(true);
    expect(v.withFriction).toEqual({ n: 8, median: 2.4 });
    expect(v.withoutFriction).toEqual({ n: 11, median: -3.64 });
  });

  it("never infers comparability from the counts alone", () => {
    // Both groups clear min_group_n, but the service still said no. The view
    // must not second-guess it — the refusal can have causes the payload does
    // not expose.
    const data = withComparison();
    data.realised.comparable = false;
    expect(buildFrictionOutcomeView(data)!.showDistributions).toBe(false);
  });

  it("splits cancellations into stuck vs merely delayed", () => {
    const v = buildFrictionOutcomeView(withComparison())!;
    expect(v.cancelled).toBe(6);
    expect(v.neverBought).toBe(4);
    expect(v.boughtLater).toBe(2);
    expect(v.medianDaysUntilBought).toBe(3);
    // The split is a count, not a ranking — nothing in the view says which
    // outcome was better, because the data cannot say.
    expect(Object.keys(v)).not.toContain("verdict");
    expect(Object.keys(v)).not.toContain("score");
    expect(Object.keys(v)).not.toContain("improved");
  });

  it("treats an empty window as no-data, not as zero findings", () => {
    const v = buildFrictionOutcomeView({
      ...LIVE_CAPTURE,
      stopped: { started: 0, proceeded: 0, cancelled: 0, open: 0 },
      insufficient: true,
    })!;
    expect(v.hasData).toBe(false);
  });

  it("returns null for a missing or not-ok payload", () => {
    expect(buildFrictionOutcomeView(null)).toBeNull();
    expect(
      buildFrictionOutcomeView({ ...LIVE_CAPTURE, ok: false }),
    ).toBeNull();
  });
});
