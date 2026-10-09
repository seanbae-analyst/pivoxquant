/**
 * JournalPager — the /journal sections as swipeable phone pages.
 *
 * jsdom has no layout, so the track's width and its scrollTo are stubbed; the
 * browser-level behaviour (snap, momentum, scroll restore) is covered by the
 * 390x844 Playwright pass recorded in the change report.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { JournalPager } from "@/components/journal/journal-pager";

const WIDTH = 390;

const PAGES = [
  { id: "record", label: "기록", content: <p>record body</p> },
  { id: "habits", label: "습관", content: <p>habits body</p> },
  { id: "pulse", label: "주간 회고", content: <p>pulse body</p> },
];

function mockViewport(phone: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("max-width") ? phone : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderPager(requestedPage = 0) {
  const utils = render(
    <JournalPager pages={PAGES} requestedPage={requestedPage} ariaLabel="기록 화면" />,
  );
  const track = screen.getByTestId("journal-pager");
  Object.defineProperty(track, "clientWidth", { value: WIDTH, configurable: true });
  const scrollTo = vi.fn();
  track.scrollTo = scrollTo as unknown as typeof track.scrollTo;
  return { ...utils, track, scrollTo };
}

function selectedTab() {
  return screen
    .getAllByRole("tab", { hidden: true })
    .find((t) => t.getAttribute("aria-selected") === "true");
}

function swipeTo(track: HTMLElement, page: number) {
  track.scrollLeft = page * WIDTH;
  fireEvent.scroll(track);
  act(() => {
    vi.advanceTimersByTime(200);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("scrollTo", vi.fn());
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("JournalPager on a phone", () => {
  beforeEach(() => mockViewport(true));

  it("renders one tab and one page per section, the first one current", () => {
    renderPager();
    expect(screen.getAllByRole("tab", { hidden: true })).toHaveLength(3);
    expect(selectedTab()?.textContent).toBe("기록");
    expect(screen.getByTestId("journal-page-record")).not.toHaveAttribute("inert");
    expect(screen.getByTestId("journal-page-habits")).toHaveAttribute("inert");
    expect(screen.getByTestId("journal-page-pulse")).toHaveAttribute("inert");
    expect(screen.getByTestId("journal-page-record")).toHaveAttribute("role", "tabpanel");
  });

  it("keeps every section mounted, whichever page is in view", () => {
    renderPager();
    expect(screen.getByText("record body")).toBeInTheDocument();
    expect(screen.getByText("habits body")).toBeInTheDocument();
    expect(screen.getByText("pulse body")).toBeInTheDocument();
  });

  it("scrolls the track to a tapped tab's page", () => {
    const { scrollTo } = renderPager();
    fireEvent.click(screen.getByTestId("journal-tab-pulse"));
    expect(scrollTo).toHaveBeenCalledWith(
      expect.objectContaining({ left: 2 * WIDTH }),
    );
  });

  it("glides on a tap, but jumps when the reader asked for reduced motion", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({
        matches: true,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
    const { scrollTo } = renderPager();
    fireEvent.click(screen.getByTestId("journal-tab-habits"));
    expect(scrollTo).toHaveBeenCalledWith({ left: WIDTH, behavior: "auto" });
  });

  it("makes the swiped-to page current once the swipe settles", () => {
    const { track } = renderPager();
    swipeTo(track, 1);
    expect(selectedTab()?.textContent).toBe("습관");
    expect(screen.getByTestId("journal-page-habits")).not.toHaveAttribute("inert");
    expect(screen.getByTestId("journal-page-record")).toHaveAttribute("inert");
  });

  it("moves between pages with the arrow keys on the tab strip", () => {
    const { scrollTo } = renderPager();
    fireEvent.keyDown(screen.getByTestId("journal-tab-record"), { key: "ArrowRight" });
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ left: WIDTH }));
    expect(document.activeElement).toBe(screen.getByTestId("journal-tab-habits"));
  });

  it("lands on a deep-linked page (e.g. #weekly-pulse) without a glide", () => {
    const { track, rerender } = renderPager(0);
    rerender(
      <JournalPager pages={PAGES} requestedPage={2} ariaLabel="기록 화면" />,
    );
    expect(track.scrollLeft).toBe(2 * WIDTH);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(selectedTab()?.textContent).toBe("주간 회고");
  });
});

describe("JournalPager onPageChange", () => {
  beforeEach(() => mockViewport(true));

  it("reports each committed page, from a swipe and from a requested page", () => {
    const onPageChange = vi.fn();
    const { rerender } = render(
      <JournalPager pages={PAGES} requestedPage={0} ariaLabel="기록 화면" onPageChange={onPageChange} />,
    );
    const track = screen.getByTestId("journal-pager");
    Object.defineProperty(track, "clientWidth", { value: WIDTH, configurable: true });
    expect(onPageChange).not.toHaveBeenCalled();
    swipeTo(track, 1);
    expect(onPageChange).toHaveBeenLastCalledWith(1);
    rerender(
      <JournalPager pages={PAGES} requestedPage={2} ariaLabel="기록 화면" onPageChange={onPageChange} />,
    );
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(onPageChange).toHaveBeenLastCalledWith(2);
    expect(onPageChange).toHaveBeenCalledTimes(2);
  });
});

describe("JournalPager on desktop", () => {
  beforeEach(() => mockViewport(false));

  it("leaves every section interactive and drops the tab semantics", () => {
    renderPager();
    for (const id of ["record", "habits", "pulse"]) {
      const page = screen.getByTestId(`journal-page-${id}`);
      expect(page).not.toHaveAttribute("inert");
      expect(page).not.toHaveAttribute("role");
    }
  });
});
