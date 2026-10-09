/**
 * "/" on a phone (2026-10-09): the home-screen app used to paint the whole web
 * landing before swapping to the app screen. The landing now always ships
 * inside .pq-browser-only next to a .pq-standalone-only cover (the landing's PIVOXQUANT page), so CSS hides
 * it in the installed app before hydration; once the client knows it is
 * standalone, the landing is never rendered at all.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";

const auth = { user: null as null | { id: number }, loading: true };
vi.mock("@/lib/auth", () => ({ useAuth: () => auth }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock("@/lib/demo", () => ({ isDemoMode: () => false }));
vi.mock("@/components/landing/landing-v2", () => ({ default: () => <div data-testid="landing" /> }));
vi.mock("@/components/pwa/app-welcome", () => ({
  AppWelcome: () => <div data-testid="app-welcome" />,
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
});

describe("root page — browser vs installed app", () => {
  it("browser: the landing sits in .pq-browser-only beside a standalone-only splash", () => {
    render(<Page />);
    const landing = screen.getByTestId("landing");
    expect(landing.closest(".pq-browser-only")).toBeTruthy();
    expect(document.querySelector(".pq-standalone-only [data-testid='app-cover']")).toBeTruthy();
  });

  it("installed app while auth loads: the cover only, never the landing", () => {
    standalone = true;
    render(<Page />);
    expect(screen.queryByTestId("landing")).toBeNull();
    expect(screen.getByTestId("app-cover")).toBeTruthy();
  });

  it("installed app, signed out: the app welcome, never the landing", () => {
    standalone = true;
    auth.loading = false;
    render(<Page />);
    expect(screen.getByTestId("app-welcome")).toBeTruthy();
    expect(screen.queryByTestId("landing")).toBeNull();
  });
});
