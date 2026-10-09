/**
 * <PhonePager /> — the swipe container behind the phone /portfolio.
 *
 * jsdom has no layout, so the track's width and scroll offset are stubbed;
 * what is under test is the wiring: a scroll moves the current tab, a tap or
 * an arrow key moves the track, and only the current page is reachable.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PhonePager } from "@/components/portfolio/v2/phone-pager";

const reduced = vi.hoisted(() => ({ value: false }));
vi.mock("motion/react", () => ({ useReducedMotion: () => reduced.value }));

const PAGES = [
  { id: "a", label: "보유", content: <p>page a</p> },
  { id: "b", label: "현황", content: <p>page b</p> },
  { id: "c", label: "섹터", content: <p>page c</p> },
];

const WIDTH = 390;

function stubTrack(track: HTMLElement) {
  Object.defineProperty(track, "clientWidth", { configurable: true, value: WIDTH });
  const scrollTo = vi.fn((opts: ScrollToOptions) => {
    track.scrollLeft = opts.left ?? 0;
  });
  (track as unknown as { scrollTo: typeof scrollTo }).scrollTo = scrollTo;
  return scrollTo;
}

beforeEach(() => {
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    cb(0);
    return 1;
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  reduced.value = false;
});

describe("PhonePager", () => {
  it("renders a tab per page and marks only the first page current", () => {
    render(<PhonePager label="화면" pages={PAGES} />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.getAttribute("aria-selected"))).toEqual(["true", "false", "false"]);
    expect(screen.getByTestId("phone-page-a")).not.toHaveAttribute("inert");
    expect(screen.getByTestId("phone-page-b")).toHaveAttribute("inert");
    // Tab and panel are cross-linked for assistive tech.
    const panel = screen.getByTestId("phone-page-a");
    expect(panel).toHaveAttribute("aria-labelledby", tabs[0].id);
    expect(tabs[0]).toHaveAttribute("aria-controls", panel.id);
  });

  it("follows a swipe: the nearest page becomes current", () => {
    render(<PhonePager label="화면" pages={PAGES} />);
    const track = screen.getByTestId("phone-pager-track");
    stubTrack(track);
    track.scrollLeft = WIDTH * 1.6;
    fireEvent.scroll(track);
    expect(screen.getByRole("tab", { name: "섹터" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("phone-page-c")).not.toHaveAttribute("inert");
  });

  it("glides to a tapped tab, and jumps when motion is reduced", async () => {
    const { unmount } = render(<PhonePager label="화면" pages={PAGES} />);
    let scrollTo = stubTrack(screen.getByTestId("phone-pager-track"));
    await userEvent.click(screen.getByRole("tab", { name: "섹터" }));
    expect(scrollTo).toHaveBeenCalledWith({ left: WIDTH * 2, behavior: "smooth" });
    expect(screen.getByRole("tab", { name: "섹터" })).toHaveAttribute("aria-selected", "true");
    unmount();

    reduced.value = true;
    render(<PhonePager label="화면" pages={PAGES} />);
    scrollTo = stubTrack(screen.getByTestId("phone-pager-track"));
    await userEvent.click(screen.getByRole("tab", { name: "현황" }));
    expect(scrollTo).toHaveBeenCalledWith({ left: WIDTH, behavior: "auto" });
  });

  it("does not flicker through the pages in between while gliding to a tapped tab", async () => {
    render(<PhonePager label="화면" pages={PAGES} />);
    const track = screen.getByTestId("phone-pager-track");
    stubTrack(track);
    (track as unknown as { scrollTo: () => void }).scrollTo = () => {};
    await userEvent.click(screen.getByRole("tab", { name: "섹터" }));
    // Smooth scroll passes page b on its way to c.
    act(() => {
      track.scrollLeft = WIDTH * 1.0;
      fireEvent.scroll(track);
    });
    expect(screen.getByRole("tab", { name: "섹터" })).toHaveAttribute("aria-selected", "true");
  });

  it("moves with the arrow keys and Home / End", async () => {
    render(<PhonePager label="화면" pages={PAGES} />);
    stubTrack(screen.getByTestId("phone-pager-track"));
    screen.getAllByRole("tab")[0].focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "현황" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "현황" })).toHaveFocus();
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "섹터" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "보유" })).toHaveAttribute("aria-selected", "true");
  });

  it("renders one indicator dot per page", () => {
    render(<PhonePager label="화면" pages={PAGES} />);
    expect(screen.getByTestId("phone-pager-dots").children).toHaveLength(3);
  });
});

describe("PhonePager — nav=\"dots\" (story cards)", () => {
  it("drops the tab strip and makes the dots the tablist, named by page label", () => {
    render(<PhonePager label="카드" pages={PAGES} nav="dots" />);
    expect(screen.queryByTestId("phone-pager-tabs")).toBeNull();
    const list = screen.getByRole("tablist", { name: "카드" });
    expect(list).toBe(screen.getByTestId("phone-pager-dots"));
    expect(list).not.toHaveAttribute("aria-hidden");
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.getAttribute("aria-label"))).toEqual(["보유", "현황", "섹터"]);
    expect(tabs.map((t) => t.getAttribute("aria-selected"))).toEqual(["true", "false", "false"]);
    const panel = screen.getByTestId("phone-page-a");
    expect(panel).toHaveAttribute("aria-labelledby", tabs[0].id);
    expect(screen.getByTestId("phone-page-b")).toHaveAttribute("inert");
  });

  it("a tapped dot moves the track", async () => {
    render(<PhonePager label="카드" pages={PAGES} nav="dots" />);
    const scrollTo = stubTrack(screen.getByTestId("phone-pager-track"));
    await userEvent.click(screen.getByRole("tab", { name: "섹터" }));
    expect(scrollTo).toHaveBeenCalledWith({ left: WIDTH * 2, behavior: "smooth" });
    expect(screen.getByRole("tab", { name: "섹터" })).toHaveAttribute("aria-selected", "true");
  });

  it("a swipe moves the current dot", () => {
    render(<PhonePager label="카드" pages={PAGES} nav="dots" />);
    const track = screen.getByTestId("phone-pager-track");
    stubTrack(track);
    track.scrollLeft = WIDTH * 0.9;
    fireEvent.scroll(track);
    expect(screen.getByRole("tab", { name: "현황" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("phone-page-b")).not.toHaveAttribute("inert");
  });

  it("moves with the arrow keys from a focused dot", async () => {
    render(<PhonePager label="카드" pages={PAGES} nav="dots" />);
    stubTrack(screen.getByTestId("phone-pager-track"));
    screen.getAllByRole("tab")[0].focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "현황" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "현황" })).toHaveFocus();
  });

  it("default nav keeps the labelled tab strip and decorative dots", () => {
    render(<PhonePager label="화면" pages={PAGES} />);
    expect(screen.getByTestId("phone-pager-tabs")).toHaveAttribute("role", "tablist");
    expect(screen.getByTestId("phone-pager-dots")).toHaveAttribute("aria-hidden");
    expect(screen.getByTestId("phone-pager-dots").querySelector("button")).toBeNull();
  });
});
