/**
 * AppWelcome (2026-10-07) — the installed app has no landing page. A
 * signed-out user who opens the home-screen icon sees three cards once;
 * after that the icon opens straight to /login. The browser keeps the landing.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));

import { AppWelcome, WELCOME_SEEN_KEY, isStandaloneDisplay } from "../app-welcome";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

describe("AppWelcome", () => {
  it("first launch: three cards, a next button, and on the last card start / login", () => {
    render(<AppWelcome />);
    expect(screen.getAllByTestId("app-welcome-card")).toHaveLength(3);
    expect(screen.getByText("사기 전에, 멈춰서 이유를 적습니다.")).toBeTruthy();
    expect(screen.getByTestId("app-welcome-next")).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();

    // jsdom has no layout, so drive the "last card" state through the skip button's target.
    const track = screen.getByTestId("app-welcome-track");
    Object.defineProperty(track, "clientWidth", { value: 390, configurable: true });
    Object.defineProperty(track, "scrollLeft", { value: 780, configurable: true });
    fireEvent.scroll(track);
    const start = screen.getByTestId("app-welcome-start");
    expect(start.getAttribute("href")).toBe("/signup");
    fireEvent.click(start);
    expect(localStorage.getItem(WELCOME_SEEN_KEY)).toBe("1");
  });

  it("after the cards were seen, goes straight to login", () => {
    localStorage.setItem(WELCOME_SEEN_KEY, "1");
    render(<AppWelcome />);
    expect(replace).toHaveBeenCalledWith("/login");
    expect(screen.queryByTestId("app-welcome")).toBeNull();
  });

  it("isStandaloneDisplay reads the display mode", () => {
    const mm = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: q === "(display-mode: standalone)" })) as unknown as typeof window.matchMedia;
    expect(isStandaloneDisplay()).toBe(true);
    window.matchMedia = (() => ({ matches: false })) as unknown as typeof window.matchMedia;
    expect(isStandaloneDisplay()).toBe(false);
    window.matchMedia = mm;
  });
});
