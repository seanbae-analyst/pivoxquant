/**
 * "/" on a phone (2026-10-09): the home-screen app used to paint the whole web
 * landing before swapping to the app screen. The landing now always ships
 * inside .pq-browser-only next to a .pq-standalone-only cover (the landing's PIVOXQUANT page), so CSS hides
 * it in the installed app before hydration; once the client knows it is
 * standalone, the landing is never rendered at all.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";

const auth = { user: null as null | { id: number }, loading: true, waking: false };
vi.mock("@/lib/auth", () => ({ useAuth: () => auth }));
const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
let returning = false;
vi.mock("@/lib/had-session", () => ({ hadSession: () => returning }));
vi.mock("@/lib/demo", () => ({ isDemoMode: () => false }));
vi.mock("@/components/landing/landing-v2", () => ({ default: () => <div data-testid="landing" /> }));
vi.mock("@/components/pwa/app-welcome", () => ({
  AppWelcome: () => <div data-testid="app-welcome" />,
}));
// 2026-10-09: the cover + standalone probe moved to app-cover.tsx so "/" can
// lazy-load the welcome cards and the landing (next/dynamic).
vi.mock("@/components/pwa/app-cover", () => ({
  AppCover: () => <div data-testid="app-cover" />,
  isStandaloneDisplay: () => standalone,
}));

let standalone = false;

import Page from "../page";

afterEach(() => {
  cleanup();
  standalone = false;
  returning = false;
  auth.user = null;
  auth.loading = true;
  auth.waking = false;
  replace.mockReset();
});

describe("root page — browser vs installed app", () => {
  it("browser: the landing sits in .pq-browser-only beside a standalone-only splash", async () => {
    render(<Page />);
    const landing = await screen.findByTestId("landing");
    expect(landing.closest(".pq-browser-only")).toBeTruthy();
    expect(document.querySelector(".pq-standalone-only [data-testid='app-cover']")).toBeTruthy();
  });

  it("installed app while auth loads: the cover only, never the landing", () => {
    standalone = true;
    render(<Page />);
    expect(screen.queryByTestId("landing")).toBeNull();
    expect(screen.getByTestId("app-cover")).toBeTruthy();
  });

  it("installed app, signed out: the app welcome, never the landing", async () => {
    standalone = true;
    auth.loading = false;
    render(<Page />);
    expect(await screen.findByTestId("app-welcome")).toBeTruthy();
    expect(screen.queryByTestId("landing")).toBeNull();
  });

  it("installed app, signed in: the cover holds through the redirect — no loading screen", () => {
    standalone = true;
    auth.loading = false;
    auth.user = { id: 1 };
    render(<Page />);
    expect(screen.getByTestId("app-cover")).toBeTruthy();
    expect(screen.queryByRole("status", { name: "Loading PivoxQuant" })).toBeNull();
    expect(screen.queryByTestId("landing")).toBeNull();
  });

  // 2026-10-10: a signed-in launch on a cold backend held the bare cover, then
  // read the unknown state as a guest — and, once the poll gave up, stayed on
  // the cover for good. A device that has held a session opens the home tab,
  // whose shell holds a skeleton with the wake line and a retry.
  it("installed app, auth unknown (waking), device has held a session: opens the home tab", () => {
    standalone = true;
    returning = true;
    auth.loading = false;
    auth.waking = true;
    render(<Page />);
    expect(replace).toHaveBeenCalledWith("/mirror");
    expect(screen.getByTestId("app-cover")).toBeTruthy();
    expect(screen.queryByTestId("app-welcome")).toBeNull();
  });

  it("installed app, auth still loading, device has held a session: opens the home tab at once", () => {
    standalone = true;
    returning = true;
    render(<Page />);
    expect(replace).toHaveBeenCalledWith("/mirror");
  });

  it("installed app, auth unknown, first-time device: the welcome cards (no server needed)", async () => {
    standalone = true;
    auth.loading = false;
    auth.waking = true;
    render(<Page />);
    expect(await screen.findByTestId("app-welcome")).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });

  it("installed app, a definite signed-out answer: the welcome, never back to /mirror (no loop)", async () => {
    standalone = true;
    returning = true;
    auth.loading = false;
    auth.waking = false;
    render(<Page />);
    expect(await screen.findByTestId("app-welcome")).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });

  it("browser tab: a returning device still gets the landing while auth loads", async () => {
    returning = true;
    render(<Page />);
    expect(await screen.findByTestId("landing")).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });
});
