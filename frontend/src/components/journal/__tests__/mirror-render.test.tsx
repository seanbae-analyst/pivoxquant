/**
 * mirror-render.test.tsx — DOM render coverage for the 6 behavioural mirrors.
 *
 * The existing per-mirror suites test the pure `compute*View` view-models
 * exhaustively, but NEVER mount the components — so the JSX state machine
 * (error → null, isLoading → skeleton, no-data → empty, else → loaded) and the
 * view-model → DOM wiring were entirely unverified (2026-06-02 audit gap; the
 * old carry-over "~16/18 real-data render tests missing").
 *
 * This drives each mirror's own SWR hook through all four states and asserts:
 *   - error renders nothing (a mirror failure never breaks the journal feed),
 *   - loading / empty / loaded all mount without throwing,
 *   - the loaded DOM never leaks a raw "NaN" / "undefined" / "null" — the
 *     degenerate-number guard the audit flagged (.toFixed on undefined, etc.).
 *
 * Hooks + locale are mocked so the test exercises the components' branches
 * directly. `useT` is a passthrough (renders i18n keys), so assertions target
 * data-derived output and the no-leak guard, not copy (copy is guarded by the
 * i18n banned-term tests elsewhere).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";

const hooks = vi.hoisted(() => ({
  useHoldingMirror: vi.fn(),
  useConcentrationMirror: vi.fn(),
  useProfitLossMirror: vi.fn(),
  useTurnoverMirror: vi.fn(),
  useAveragingDownMirror: vi.fn(),
  useFrictionOutcome: vi.fn(),
}));
vi.mock("@/lib/hooks", () => hooks);
vi.mock("@/lib/locale", () => ({
  useT: () => (k: string) => k,
  useLocale: () => ({ locale: "ko" }),
}));

import { HoldingMirror } from "@/components/journal/holding-mirror";
import { ConcentrationMirror } from "@/components/journal/concentration-mirror";
import { ProfitLossMirror } from "@/components/journal/profit-loss-mirror";
import { TurnoverMirror } from "@/components/journal/turnover-mirror";
import { AveragingDownMirror } from "@/components/journal/averaging-down-mirror";
import { FrictionOutcomeMirror } from "@/components/journal/friction-outcome-mirror";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const LOADED: Record<string, unknown> = {
  holding: {
    ok: true,
    period: "최근 90일",
    sufficient_data: true,
    one_sided: false,
    total_closed_pairs: 14,
    winners: { count: 6, median_hold_days: 8, mean_hold_days: 9, examples: [] },
    losers: { count: 8, median_hold_days: 31, mean_hold_days: 33, examples: [] },
  },
  concentration: {
    ok: true,
    sufficient_data: true,
    ticker_count: 3,
    max_weight_pct: 67.3,
    largest_ticker: "삼성전자",
    cost_basis_note: "평균매입가 기준 (시장가 아님)",
  },
  profitLoss: {
    ok: true,
    period: "all",
    sufficient_data: true,
    one_sided: false,
    total_closed_pairs: 14,
    take_profit: { count: 6, median_hold_days: 8, mean_hold_days: 9, median_gain_pct: 6.2, mean_gain_pct: 7.1 },
    stop_loss: { count: 8, median_hold_days: 31, mean_hold_days: 33, median_loss_pct: -9.4, mean_loss_pct: -11.2 },
  },
  turnover: {
    ok: true,
    period: "all",
    period_days: null,
    sufficient_data: true,
    trade_count: 12,
    buy_count: 7,
    sell_count: 5,
    by_currency: [
      { currency: "KRW", gross_value: 3_000_000, trade_count: 6 },
      { currency: "USD", gross_value: 4_000, trade_count: 6 },
    ],
    median_hold_days: 10,
    mean_hold_days: 14,
  },
  averagingDown: {
    ok: true,
    period: "all",
    period_days: null,
    sufficient_data: true,
    follow_on_count: 6,
    below_avg_count: 4,
    above_avg_count: 1,
    flat_count: 1,
    by_ticker: [
      { ticker: "AAPL", name: "Apple Inc.", follow_on: 4, below_avg: 3, above_avg: 1 },
      { ticker: "005930", name: "삼성전자", follow_on: 2, below_avg: 1, above_avg: 0 },
    ],
  },
  // Shaped from the live GET /api/behavior/friction-outcome capture
  // (2026-09-02), with `comparable` flipped true so the loaded branch renders
  // the distribution block — the refusal path is covered in the view-model
  // suite (friction-outcome-mirror.test.ts).
  frictionOutcome: {
    ok: true,
    period: "all",
    window_days: null,
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
    caveats: {
      not_randomised: true,
      attribution_window_days: 7,
      cooldown_seconds_currently: 0,
    },
    insufficient: false,
  },
};

const MIRRORS = [
  { name: "HoldingMirror", Comp: HoldingMirror, hook: hooks.useHoldingMirror, key: "holding" },
  { name: "ConcentrationMirror", Comp: ConcentrationMirror, hook: hooks.useConcentrationMirror, key: "concentration" },
  { name: "ProfitLossMirror", Comp: ProfitLossMirror, hook: hooks.useProfitLossMirror, key: "profitLoss" },
  { name: "TurnoverMirror", Comp: TurnoverMirror, hook: hooks.useTurnoverMirror, key: "turnover" },
  { name: "FrictionOutcomeMirror", Comp: FrictionOutcomeMirror, hook: hooks.useFrictionOutcome, key: "frictionOutcome" },
  { name: "AveragingDownMirror", Comp: AveragingDownMirror, hook: hooks.useAveragingDownMirror, key: "averagingDown" },
] as const;

describe.each(MIRRORS)("$name render states", ({ Comp, hook, key }) => {
  it("renders nothing on a hard error (never breaks the feed)", () => {
    hook.mockReturnValue({ data: undefined, isLoading: false, error: new Error("5xx") });
    const { container } = render(<Comp />);
    expect(container.firstChild).toBeNull();
  });

  it("mounts the loading state without throwing", () => {
    hook.mockReturnValue({ data: undefined, isLoading: true, error: undefined });
    const { container } = render(<Comp />);
    expect(container.firstChild).not.toBeNull();
  });

  it("mounts the empty state on null data without throwing", () => {
    hook.mockReturnValue({ data: null, isLoading: false, error: undefined });
    const { container } = render(<Comp />);
    expect(container.firstChild).not.toBeNull();
  });

  it("renders loaded data with no NaN/undefined/null leaking to the DOM", () => {
    hook.mockReturnValue({ data: LOADED[key], isLoading: false, error: undefined });
    const { container } = render(<Comp />);
    expect(container.firstChild).not.toBeNull();
    expect(container.textContent ?? "").not.toMatch(/NaN|undefined|null/);
  });
});
