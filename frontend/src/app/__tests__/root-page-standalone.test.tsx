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
const markLaunchCovered = vi.fn();
vi.mock("@/lib/launch-cover", () => ({ markLaunchCovered: () => markLaunchCovered() }));
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
  auth.user = null;
  auth.loading = true;
  auth.waking = false;
  replace.mockReset();
  markLaunchCovered.mockReset();
});

describe("root page — browser vs installed app", () => {
  it("browser: the landing sits in .pq-browser-only beside a standalone-only splash", async () => {
    render(<Page />);
    const landing = await screen.findByTestId("landing");
    expect(landing.closest(".pq-browser-only")).toBeTruthy();
    expect(document.querySelector(".pq-standalone-only [data-testid='app-cover']")).toBeTruthy();
  });

  // 2026-10-10, CEO: every launch of the installed app opens on the cover and
  // its cards — signed in or not, server awake or not — and "/" never sends it
  // on by itself (it used to jump to /mirror for a signed-in user).
  it.each([
    ["auth still loading", { loading: true, waking: false, user: null }],
    ["server waking", { loading: false, waking: true, user: null }],
    ["signed out", { loading: false, waking: false, user: null }],
    ["signed in", { loading: false, waking: false, user: { id: 1 } }],
  ])("installed app, %s: the cover and cards, never the landing, no redirect", async (_label, state) => {
    standalone = true;
    Object.assign(auth, state);
    render(<Page />);
    expect(await screen.findByTestId("app-welcome")).toBeTruthy();
    expect(screen.queryByTestId("landing")).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  it("installed app: marks this launch as covered", async () => {
    standalone = true;
    render(<Page />);
    await screen.findByTestId("app-welcome");
    expect(markLaunchCovered).toHaveBeenCalled();
  });

  it("browser, signed in: still goes straight to the app", () => {
    auth.loading = false;
    auth.user = { id: 1 };
    render(<Page />);
    expect(replace).toHaveBeenCalledWith("/mirror");
    expect(markLaunchCovered).not.toHaveBeenCalled();
  });
});
