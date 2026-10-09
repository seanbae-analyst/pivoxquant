/** Phone tab bar — 2026-10-09: four tabs, no drawer, native tap behaviour. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

const nav = vi.hoisted(() => ({ pathname: "/mirror" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));
vi.mock("next/link", () => ({
  default: ({ href, children, onClick, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a
      href={href}
      {...rest}
      onClick={(e) => {
        onClick?.(e);
        e.preventDefault(); // jsdom: never navigate
      }}
    >
      {children}
    </a>
  ),
}));

import { BottomNav } from "../bottom-nav";
import { SCROLL_TOP_EVENT } from "@/lib/scroll-top-event";

function bar() {
  return screen.getByRole("navigation", { name: "Primary mobile navigation" });
}

describe("BottomNav", () => {
  beforeEach(() => {
    nav.pathname = "/mirror";
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  });

  it("is 거울 · 멈춤 · 기록 · 포트폴리오 — no 더보기, no drawer", () => {
    render(<BottomNav />);
    const links = within(bar()).getAllByRole("link");
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["거울", "/mirror"],
      ["멈춤", "/pre-trade"],
      ["기록", "/journal"],
      ["포트폴리오", "/portfolio"],
    ]);
    expect(within(bar()).queryByRole("button")).toBeNull();
    expect(screen.queryByText("더보기")).toBeNull();
  });

  it("aria-current marks the shown route, including its sub-routes", () => {
    nav.pathname = "/journal/import";
    render(<BottomNav />);
    expect(screen.getByRole("link", { name: "기록" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "거울" })).not.toHaveAttribute("aria-current");
  });

  it("an unknown sub-path (the in-app 404) lights no tab", () => {
    for (const p of ["/mirror/nope", "/journal/nope", "/portfolio/x/y", "/pre-trade/1", "/mirrorx"]) {
      nav.pathname = p;
      const { unmount } = render(<BottomNav />);
      for (const a of within(bar()).getAllByRole("link")) {
        expect(a, p).not.toHaveAttribute("aria-current");
        expect(a, p).not.toHaveAttribute("data-lit");
      }
      unmount();
    }
  });

  it("a trailing slash still matches the tab root", () => {
    nav.pathname = "/portfolio/";
    render(<BottomNav />);
    expect(screen.getByRole("link", { name: "포트폴리오" })).toHaveAttribute("aria-current", "page");
  });

  it("/settings and /support light no tab", () => {
    for (const p of ["/settings", "/support/inbox/3"]) {
      nav.pathname = p;
      const { unmount } = render(<BottomNav />);
      for (const a of within(bar()).getAllByRole("link")) {
        expect(a).not.toHaveAttribute("aria-current");
        expect(a).not.toHaveAttribute("data-lit");
      }
      unmount();
    }
  });

  it("a tapped tab lights at once, before the route commits", () => {
    render(<BottomNav />);
    fireEvent.click(screen.getByRole("link", { name: "포트폴리오" }));
    expect(screen.getByRole("link", { name: "포트폴리오" })).toHaveAttribute("data-lit", "true");
    expect(screen.getByRole("link", { name: "거울" })).not.toHaveAttribute("data-lit");
    // aria-current still reports the route actually on screen.
    expect(screen.getByRole("link", { name: "거울" })).toHaveAttribute("aria-current", "page");
  });

  it("tapping the current tab scrolls to top and tells inner scrollers", () => {
    const onTop = vi.fn();
    window.addEventListener(SCROLL_TOP_EVENT, onTop);
    render(<BottomNav />);
    fireEvent.click(screen.getByRole("link", { name: "거울" }));
    expect(window.scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }));
    expect(onTop).toHaveBeenCalledTimes(1);
    window.removeEventListener(SCROLL_TOP_EVENT, onTop);
  });
});
