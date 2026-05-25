import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Regression: /profile V2 rendered "Peer benchmark" twice — once inside
// PersonaV2Card (Block 2) and once via PeerBenchmarkBlockV2 (Block 5, the
// canonical SPEC §1 surface). The `showPeerBenchmark` prop lets V2 suppress
// the card's inner block while V1 (rollback insurance) keeps it. This test
// pins both branches so the double-render can't silently return.
//
// We mock usePersonaDetail (so the card renders past its loading/error
// guards) and PeerBenchmarkBlock (to a sentinel, so the assertion is
// independent of that block's own data hook).
vi.mock("@/lib/cfo/hooks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/cfo/hooks")>();
  return { ...actual, usePersonaDetail: vi.fn() };
});

vi.mock("@/components/shared/peer-benchmark-block", () => ({
  PeerBenchmarkBlock: () => (
    <div data-testid="inner-peer-benchmark">inner peer benchmark</div>
  ),
}));

import {
  usePersonaDetail,
  type PersonaDetailResponse,
  type PersonaFeatureKey,
} from "@/lib/cfo/hooks";
import { PersonaV2Card } from "@/components/dashboard/persona-v2-card";

const mockedHook = vi.mocked(usePersonaDetail);

const FEATURE_KEYS: PersonaFeatureKey[] = [
  "holding_period",
  "turnover",
  "sector_diversity",
  "ticker_diversity",
  "hold_variance",
  "loss_cut_discipline",
  "declared_risk",
  "conviction_stability",
  "feedback_engagement",
];

function mkDetail(): PersonaDetailResponse {
  const features = Object.fromEntries(
    FEATURE_KEYS.map((k) => [k, 0.5]),
  ) as Record<PersonaFeatureKey, number>;
  const present = Object.fromEntries(
    FEATURE_KEYS.map((k) => [k, 1]),
  ) as Record<PersonaFeatureKey, 0 | 1>;
  return {
    persona: "balanced",
    label: "Balanced",
    tagline: "Steady hand",
    confidence: 72,
    window_days: 90,
    data_sparse: false,
    trade_count: 24,
    features,
    present,
    ranking: [],
    breakdown: [
      {
        feature: "holding_period",
        label: "보유 기간",
        value: 0.6,
        centroid: 0.55,
        closeness: 0.95,
        weight: 1.0,
      },
    ],
    declared_persona: null,
    last_computed_at: "2026-05-25T00:00:00Z",
  };
}

function mockData(data: PersonaDetailResponse) {
  mockedHook.mockReturnValue({
    data,
    isLoading: false,
    error: undefined,
  } as unknown as ReturnType<typeof usePersonaDetail>);
}

describe("PersonaV2Card — showPeerBenchmark prop (double-render regression)", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  it("renders the inner peer benchmark by default (V1 legacy behaviour)", () => {
    mockData(mkDetail());
    render(<PersonaV2Card />);
    expect(screen.getByTestId("inner-peer-benchmark")).toBeInTheDocument();
  });

  it("renders the inner peer benchmark when showPeerBenchmark=true", () => {
    mockData(mkDetail());
    render(<PersonaV2Card showPeerBenchmark={true} />);
    expect(screen.getByTestId("inner-peer-benchmark")).toBeInTheDocument();
  });

  it("suppresses the inner peer benchmark when showPeerBenchmark=false (V2)", () => {
    mockData(mkDetail());
    render(<PersonaV2Card showPeerBenchmark={false} />);
    expect(screen.queryByTestId("inner-peer-benchmark")).toBeNull();
  });
});
