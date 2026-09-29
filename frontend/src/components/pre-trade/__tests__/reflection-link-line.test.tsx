/**
 * <ReflectionLinkLine /> + useReflectionLink() — link a recorded buy to the
 * pause that preceded it (2026-09-29). Pinned here:
 *   1. nothing renders without a candidate,
 *   2. with a candidate the checkbox is ON by default and `reflectionId` is
 *      the candidate's id; unchecking clears it,
 *   3. a null ticker disables the fetch (sell / edit / review mode).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks", () => ({
  useLinkableReflections: vi.fn(),
}));

import { useLinkableReflections } from "@/lib/hooks";
import {
  ReflectionLinkLine,
  daysSince,
  rationaleFirstLine,
  reflectionLinkBody,
  useReflectionLink,
  LINK_EXCERPT_CHARS,
} from "@/components/pre-trade/reflection-link-line";
import type { PreTradeReflection } from "@/lib/types";

const mockedHook = vi.mocked(useLinkableReflections);

function refl(id: number, over: Partial<PreTradeReflection> = {}): PreTradeReflection {
  return {
    id,
    intended_ticker: "AAPL",
    intended_side: null,
    intended_shares: null,
    rationale: "실적 발표 전에 비중을 늘린다\n둘째 줄",
    devil_advocate_seen: null,
    market_volatility_at_request: null,
    cooldown_started_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
    cooldown_ends_at: null,
    proceeded_at: null,
    cancelled_at: null,
    auto_extended_reason: null,
    seconds_remaining: 0,
    status: "proceeded",
    ...over,
  };
}

function result(reflections: PreTradeReflection[]) {
  return { reflections, isLoading: false, error: undefined } as ReturnType<
    typeof useLinkableReflections
  >;
}

function Harness({ ticker }: { ticker: string | null }) {
  const link = useReflectionLink(ticker);
  return (
    <div>
      <ReflectionLinkLine link={link} />
      <span data-testid="rid">{String(link.reflectionId)}</span>
      <span data-testid="body">{JSON.stringify(reflectionLinkBody(link))}</span>
    </div>
  );
}

describe("pure helpers", () => {
  it("rationaleFirstLine keeps the first non-empty line and cuts at the budget", () => {
    expect(rationaleFirstLine("\n  첫 줄  \n둘째")).toBe("첫 줄");
    const out = rationaleFirstLine("가".repeat(LINK_EXCERPT_CHARS + 5));
    expect(out).toHaveLength(LINK_EXCERPT_CHARS + 1);
    expect(out.endsWith("…")).toBe(true);
  });

  it("daysSince counts whole days, never negative, null on garbage", () => {
    const now = Date.parse("2026-09-29T00:00:00Z");
    expect(daysSince("2026-09-26T00:00:00Z", now)).toBe(3);
    expect(daysSince("2026-09-30T00:00:00Z", now)).toBe(0);
    expect(daysSince("nope", now)).toBeNull();
  });
});

describe("<ReflectionLinkLine />", () => {
  beforeEach(() => mockedHook.mockReset());

  it("renders nothing and links nothing without a candidate", () => {
    mockedHook.mockReturnValue(result([]));
    render(<Harness ticker="AAPL" />);
    expect(screen.queryByTestId("reflection-link-line")).toBeNull();
    expect(screen.getByTestId("rid").textContent).toBe("null");
  });

  it("defaults ON to the newest candidate and can be unchecked", () => {
    mockedHook.mockReturnValue(result([refl(7), refl(3)]));
    render(<Harness ticker="aapl" />);
    expect(mockedHook).toHaveBeenCalledWith("AAPL");
    const box = screen.getByRole("checkbox") as HTMLInputElement;
    expect(box.checked).toBe(true);
    expect(screen.getByTestId("rid").textContent).toBe("7");
    expect(screen.getByText(/실적 발표 전에 비중을 늘린다/)).toBeTruthy();
    expect(screen.queryByText(/둘째 줄/)).toBeNull();
    expect(JSON.parse(screen.getByTestId("body").textContent!)).toEqual({ reflection_id: 7 });
    fireEvent.click(box);
    expect(box.checked).toBe(false);
    expect(screen.getByTestId("rid").textContent).toBe("null");
    // Unchecking a shown pause is an explicit decline (2026-09-29).
    expect(JSON.parse(screen.getByTestId("body").textContent!)).toEqual({
      reflection_id: null,
      reflection_declined: true,
    });
  });

  it("with no candidate the body carries no link keys", () => {
    mockedHook.mockReturnValue(result([]));
    render(<Harness ticker="AAPL" />);
    expect(screen.getByTestId("body").textContent).toBe("{}");
  });

  it("a null ticker disables the fetch", () => {
    mockedHook.mockReturnValue(result([]));
    render(<Harness ticker={null} />);
    expect(mockedHook).toHaveBeenCalledWith(null);
  });
});
