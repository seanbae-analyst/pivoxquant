/**
 * <PullToRefresh> — phone pull at the top of a screen re-reads its data.
 *
 * Pinned:
 *   - a vertical pull past the threshold calls onRefresh once, with one
 *     haptic tick at the threshold;
 *   - a short pull, a sideways swipe (the pagers'), a pull while scrolled or
 *     while a bottom sheet is open does nothing;
 *   - md+ attaches nothing.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PullToRefresh } from "@/components/layout/pull-to-refresh";

function stubViewport(phone: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("max-width") ? phone : false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function drag(el: Element, dx: number, dy: number) {
  const start = { clientX: 100, clientY: 100 };
  fireEvent.touchStart(el, { touches: [start] });
  const steps = 6;
  for (let i = 1; i <= steps; i++) {
    fireEvent.touchMove(el, {
      touches: [{ clientX: start.clientX + (dx * i) / steps, clientY: start.clientY + (dy * i) / steps }],
    });
  }
  fireEvent.touchEnd(el, { touches: [] });
}

const originalMatchMedia = window.matchMedia;
let vibrate: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vibrate = vi.fn();
  Object.defineProperty(navigator, "vibrate", { value: vibrate, configurable: true });
  Object.defineProperty(window, "scrollY", { value: 0, configurable: true, writable: true });
});
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
  // @ts-expect-error — remove the stub
  delete navigator.vibrate;
  document.documentElement.removeAttribute("data-pq-sheet-open");
});

function setup(phone = true) {
  stubViewport(phone);
  const onRefresh = vi.fn(() => Promise.resolve());
  render(
    <PullToRefresh onRefresh={onRefresh}>
      <p>screen</p>
    </PullToRefresh>,
  );
  return { onRefresh, target: screen.getByText("screen") };
}

describe("<PullToRefresh>", () => {
  it("a pull past the threshold refreshes once, with one haptic tick", async () => {
    const { onRefresh, target } = setup();
    await act(async () => drag(target, 0, 160));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(vibrate).toHaveBeenCalledTimes(1);
    expect(vibrate).toHaveBeenCalledWith(10);
  });

  it("a short pull springs back without refreshing", async () => {
    const { onRefresh, target } = setup();
    await act(async () => drag(target, 0, 60));
    expect(onRefresh).not.toHaveBeenCalled();
    expect(vibrate).not.toHaveBeenCalled();
  });

  it("leaves sideways swipes to the pagers", async () => {
    const { onRefresh, target } = setup();
    await act(async () => drag(target, 160, 40));
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("does not start when the page is scrolled", async () => {
    const { onRefresh, target } = setup();
    window.scrollY = 240;
    await act(async () => drag(target, 0, 160));
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("does not start while a bottom sheet is open", async () => {
    const { onRefresh, target } = setup();
    document.documentElement.setAttribute("data-pq-sheet-open", "");
    await act(async () => drag(target, 0, 160));
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("is inert at md and up", async () => {
    const { onRefresh, target } = setup(false);
    await act(async () => drag(target, 0, 160));
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.queryByTestId("pull-indicator")).toBeNull();
  });
});
