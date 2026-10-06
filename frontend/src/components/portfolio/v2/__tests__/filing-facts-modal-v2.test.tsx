import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";

import { API } from "@/lib/endpoints";
import {
  FilingFactsModalV2,
  FactsBody,
  fmtAmount,
  type FilingFacts,
} from "@/components/portfolio/v2/filing-facts-modal-v2";

const base: FilingFacts = {
  source: "SEC EDGAR",
  entity_name: "Example",
  currency: "USD",
  as_of: "2026-06-30",
  quarters: [
    { end: "2026-03-31", revenue: 24_200_000, net_income: -230_000_000 },
    { end: "2026-06-30", revenue: 38_600_000, net_income: -245_400_000 },
  ],
  revenue_ttm: 116_300_000,
  net_income_ttm: -878_200_000,
  net_income_streak: { kind: "loss", quarters: 11 },
  net_income_per_share_ttm: -0.9,
  cash: { as_of: "2026-06-30", value: 2_263_826_000, includes_short_term: true },
  operating_cf_ttm: -609_900_000,
  cash_months_at_ttm_burn: 44.5,
  liabilities_to_equity: { as_of: "2026-06-30", value: 0.558 },
  shares_change_1y: { from: "2025-06-30", to: "2026-06-30", pct: 0.217 },
};

afterEach(() => vi.unstubAllGlobals());

describe("fmtAmount", () => {
  it("formats USD and KRW at readable scales", () => {
    expect(fmtAmount(2_263_826_000, "USD")).toBe("$2.26B");
    expect(fmtAmount(-245_400_000, "USD")).toBe("-$245.4M");
    expect(fmtAmount(1.2e13, "KRW")).toBe("12.0조 원");
    expect(fmtAmount(3.45e10, "KRW")).toBe("345억 원");
    expect(fmtAmount(null, "USD")).toBe("—");
  });
});

describe("<FactsBody />", () => {
  it("loss-making company has no PER, shows the streak and the cash months", () => {
    render(<FactsBody facts={base} avgCost={6.12} peAtCost={null} />);
    expect(screen.getByText("해당 없음 · 최근 4분기 적자")).toBeInTheDocument();
    expect(screen.getByText("11분기 연속 적자")).toBeInTheDocument();
    expect(screen.getByText("현금 + 단기투자")).toBeInTheDocument();
    expect(screen.getByText("약 45개월분")).toBeInTheDocument();
    expect(screen.getByText("+21.70%")).toBeInTheDocument();
    expect(screen.getByText(/미국 SEC EDGAR/)).toBeInTheDocument();
  });

  it("shows PER at my average cost when profitable", () => {
    render(
      <FactsBody
        facts={{ ...base, net_income_ttm: 10, net_income_streak: { kind: "profit", quarters: 4 } }}
        avgCost={50}
        peAtCost={25}
      />,
    );
    expect(screen.getByText("25.0배")).toBeInTheDocument();
    expect(screen.getByText("내 평단($50) 기준 PER")).toBeInTheDocument();
  });

  it("never uses judgement vocabulary", () => {
    const { container } = render(<FactsBody facts={base} avgCost={6.12} peAtCost={null} />);
    const text = container.textContent ?? "";
    for (const w of ["점수", "등급", "추천", "조언", "매수", "매도", "BUY", "SELL"]) {
      expect(text).not.toContain(w);
    }
  });
});

describe("<FilingFactsModalV2 />", () => {
  it("fetches by position id and renders the unavailable reason", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ticker: "005930.KS", available: false, reason: "source_unconfigured" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <FilingFactsModalV2 open positionId="7" symbol="005930.KS" name="삼성전자" onClose={() => {}} />
      </SWRConfig>,
    );
    await waitFor(() =>
      expect(screen.getByText("한국 공시(DART) 연결이 아직 설정되지 않았습니다.")).toBeInTheDocument(),
    );
    expect(fetchMock.mock.calls[0][0]).toBe(API.portfolio.filings("7"));
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <FilingFactsModalV2 open={false} positionId="7" symbol="AAPL" onClose={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
