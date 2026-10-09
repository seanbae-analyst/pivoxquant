/**
 * <PhoneRouteFrame> — phone route motion + per-route scroll memory.
 *
 * Pinned (measured bug: 기록 scrolled to 900 → 거울 landed at 128 → back to
 * 기록 landed at 128):
 *   - a tab without memory starts at the top; returning to 기록 restores 900,
 *     with an instant jump (html is scroll-behavior: smooth);
 *   - tab switches fade, drill-downs slide in from the right, back from the
 *     left; an iOS edge swipe (hasUAVisualTransition) plays nothing on top;
 *   - md+ does nothing.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, render } from "@testing-library/react";

let pathname = "/journal";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

import { PhoneRouteFrame } from "@/components/layout/phone-route-frame";
import { __resetScrollMemoryForTests } from "@/lib/scroll-memory";
import { PQ_ROUTE_SLIDE_PX } from "@/lib/motion";

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

const originalMatchMedia = window.matchMedia;
const scrollTo = vi.fn((x: number, y: number) => {
  void x;
  (window as { scrollY: number }).scrollY = y;
});
const animate = vi.fn(() => {
  const a = { cancel: vi.fn(), addEventListener: vi.fn() };
  return a as unknown as Animation;
});

beforeEach(() => {
  window.sessionStorage.clear();
  __resetScrollMemoryForTests();
  pathname = "/journal";
  Object.defineProperty(window, "scrollY", { value: 0, configurable: true, writable: true });
  window.scrollTo = scrollTo as unknown as typeof window.scrollTo;
  Object.defineProperty(document.documentElement, "scrollHeight", { value: 5000, configurable: true });
  HTMLElement.prototype.animate = animate as unknown as HTMLElement["animate"];
  scrollTo.mockClear();
  animate.mockClear();
});
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
});

function mount() {
  const utils = render(
    <main>
      <PhoneRouteFrame>
        <p>{pathname}</p>
      </PhoneRouteFrame>
    </main>,
  );
  const go = (next: string) => {
    pathname = next;
    utils.rerender(
      <main>
        <PhoneRouteFrame>
          <p>{pathname}</p>
        </PhoneRouteFrame>
      </main>,
    );
  };
  return go;
}

function scrollWindow(y: number) {
  act(() => {
    (window as { scrollY: number }).scrollY = y;
    window.dispatchEvent(new Event("scroll"));
  });
}

type Frames = Array<Record<string, string | number>>;
const lastFrames = () => (animate.mock.calls.at(-1) as unknown as [Frames])[0];

describe("<PhoneRouteFrame> · scroll memory", () => {
  it("기록 900 → 거울 starts at top → back to 기록 lands at 900", () => {
    stubViewport(true);
    const go = mount();
    scrollWindow(900);

    go("/mirror");
    expect(scrollTo).toHaveBeenLastCalledWith(0, 0);

    go("/journal");
    expect(scrollTo).toHaveBeenLastCalledWith(0, 900);
    // The jump lifted html's smooth scrolling for that one call.
    expect(document.documentElement.style.scrollBehavior).toBe("");
  });

  it("a drill-down starts at its top", () => {
    stubViewport(true);
    const go = mount();
    scrollWindow(700);
    go("/journal/import");
    expect(scrollTo).toHaveBeenLastCalledWith(0, 0);
  });
});

describe("<PhoneRouteFrame> · motion", () => {
  it("fades between tabs and slides drill-downs in from the right, back from the left", () => {
    stubViewport(true);
    const go = mount();
    go("/mirror");
    expect(lastFrames()).toEqual([{ opacity: 0 }, { opacity: 1 }]);

    go("/journal");
    go("/journal/import");
    expect(lastFrames()[0]).toEqual({ opacity: 0, left: `${PQ_ROUTE_SLIDE_PX}px` });

    go("/journal");
    expect(lastFrames()[0]).toEqual({ opacity: 0, left: `${-PQ_ROUTE_SLIDE_PX}px` });
  });

  it("plays nothing over the browser's own back animation (iOS edge swipe)", () => {
    stubViewport(true);
    const go = mount();
    go("/journal/import");
    animate.mockClear();
    window.history.replaceState({}, "", "/journal");
    const ev = new PopStateEvent("popstate", { state: {} });
    Object.defineProperty(ev, "hasUAVisualTransition", { value: true });
    act(() => {
      window.dispatchEvent(ev);
    });
    go("/journal");
    expect(animate).not.toHaveBeenCalled();
  });

  it("does nothing at md and up", () => {
    stubViewport(false);
    const go = mount();
    scrollWindow(500);
    go("/mirror");
    expect(animate).not.toHaveBeenCalled();
    expect(scrollTo).not.toHaveBeenCalled();
  });
});
