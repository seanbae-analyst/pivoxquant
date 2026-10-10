/**
 * AppWelcome — the installed app's front door, on every launch (2026-10-10):
 * the PIVOXQUANT cover, three cards, then a button that follows the sign-in
 * state. It used to show once and then jump to /login; a signed-in launch
 * skipped it for /mirror. The browser keeps the landing.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

const auth = { user: null as null | { id: number }, loading: false, waking: false };
vi.mock("@/lib/auth", () => ({ useAuth: () => auth }));
let returning = false;
vi.mock("@/lib/had-session", () => ({ hadSession: () => returning }));

import { AppWelcome, isStandaloneDisplay } from "../app-welcome";

const scrollTo = vi.fn();
Object.defineProperty(HTMLElement.prototype, "scrollTo", { value: scrollTo, configurable: true });

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  auth.user = null;
  auth.loading = false;
  auth.waking = false;
  returning = false;
});

/** jsdom has no layout: put the track on the last card by hand. */
function goToLastCard() {
  const track = screen.getByTestId("app-welcome-track");
  Object.defineProperty(track, "clientWidth", { value: 390, configurable: true });
  Object.defineProperty(track, "scrollLeft", { value: 1170, configurable: true });
  fireEvent.scroll(track);
}

describe("AppWelcome", () => {
  it("opens on the PIVOXQUANT cover; tapping it moves to the first card", () => {
    render(<AppWelcome />);
    const cover = screen.getByTestId("app-cover");
    expect(cover.textContent).toContain("PIVOXQUANT");
    // Chrome is faded out and inert on the cover.
    expect(screen.getByTestId("app-welcome-next").getAttribute("tabindex")).toBe("-1");
    const track = screen.getByTestId("app-welcome-track");
    Object.defineProperty(track, "clientWidth", { value: 390, configurable: true });
    fireEvent.click(cover);
    expect(scrollTo).toHaveBeenCalledWith({ left: 390, behavior: "smooth" });
  });

  it("signed out: three cards, then start / sign in", () => {
    render(<AppWelcome />);
    expect(screen.getAllByTestId("app-welcome-card")).toHaveLength(3);
    expect(screen.getByText("사기 전에, 멈춰서 이유를 적습니다.")).toBeTruthy();
    goToLastCard();
    expect(screen.getByTestId("app-welcome-start").getAttribute("href")).toBe("/signup");
    expect(screen.getByText("이미 계정이 있어요 · 로그인").getAttribute("href")).toBe("/login");
    expect(screen.queryByTestId("app-welcome-enter")).toBeNull();
  });

  it("a returning device that is signed out still gets the cover and cards — no jump to /login", () => {
    returning = true;
    render(<AppWelcome />);
    expect(screen.getByTestId("app-cover")).toBeTruthy();
    expect(screen.getAllByTestId("app-welcome-card")).toHaveLength(3);
    goToLastCard();
    expect(screen.getByTestId("app-welcome-start")).toBeTruthy();
  });

  it("signed in: the cover and cards too, and the last card leads into the app", () => {
    auth.user = { id: 1 };
    render(<AppWelcome />);
    expect(screen.getByTestId("app-cover")).toBeTruthy();
    goToLastCard();
    expect(screen.getByTestId("app-welcome-enter").getAttribute("href")).toBe("/mirror");
    expect(screen.queryByTestId("app-welcome-start")).toBeNull();
    expect(screen.queryByTestId("app-welcome-waking")).toBeNull();
  });

  it("server still waking on a returning device: leads in, and says the server is waking", () => {
    returning = true;
    auth.waking = true;
    render(<AppWelcome />);
    goToLastCard();
    expect(screen.getByTestId("app-welcome-enter").getAttribute("href")).toBe("/mirror");
    expect(screen.getByTestId("app-welcome-waking").textContent).toContain("서버를 깨우는 중");
  });

  it("server still waking on a first-time device: start / sign in", () => {
    auth.waking = true;
    render(<AppWelcome />);
    goToLastCard();
    expect(screen.getByTestId("app-welcome-start")).toBeTruthy();
    expect(screen.queryByTestId("app-welcome-enter")).toBeNull();
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
