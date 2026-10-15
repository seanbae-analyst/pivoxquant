/**
 * launch-cover (2026-10-10): an install that saved start_url "/mirror" opens on
 * the cover once per launch; nothing else is redirected.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

let standalone = true;
vi.mock("@/components/pwa/app-cover", () => ({ isStandaloneDisplay: () => standalone }));

import { NOTIFICATION_LAUNCH_PARAM, markLaunchCovered, shouldOpenOnCover } from "../launch-cover";

function at(path: string) {
  window.history.replaceState(null, "", path);
}

let navType = "navigate";
/** The document URL of the launch (PerformanceNavigationTiming.name); undefined = not reported. */
let navName: string | undefined;
beforeEach(() => {
  standalone = true;
  navType = "navigate";
  navName = undefined;
  window.sessionStorage.clear();
  vi.spyOn(window.performance, "getEntriesByType").mockImplementation(
    () => [{ type: navType, name: navName }] as unknown as PerformanceEntryList,
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  at("/");
});

describe("shouldOpenOnCover", () => {
  it("installed-app launch on bare /mirror → the cover first", () => {
    at("/mirror");
    expect(shouldOpenOnCover()).toBe(true);
  });

  it("once the cover has shown this session → never again", () => {
    at("/mirror");
    markLaunchCovered();
    expect(shouldOpenOnCover()).toBe(false);
  });

  it("leaves the browser alone", () => {
    standalone = false;
    at("/mirror");
    expect(shouldOpenOnCover()).toBe(false);
  });

  it("leaves deep links alone (other paths, any query)", () => {
    at("/journal");
    expect(shouldOpenOnCover()).toBe(false);
    at("/mirror?from=push");
    expect(shouldOpenOnCover()).toBe(false);
  });

  it("a reload is not a launch", () => {
    at("/mirror");
    navType = "reload";
    expect(shouldOpenOnCover()).toBe(false);
  });

  // 2026-10-15 bug hunt: the concentration alert opens bare /mirror, and a
  // cold launch from it was sent to the cover.
  it("a notification tap (the service worker's mark) is never sent to the cover", () => {
    at(`/mirror?${NOTIFICATION_LAUNCH_PARAM}=push`);
    expect(shouldOpenOnCover()).toBe(false);
    // …and the rest of that session skips the cover too, even on bare /mirror.
    at("/mirror");
    expect(shouldOpenOnCover()).toBe(false);
  });

  it("judges the URL the app was launched at, not where the page is now", () => {
    navName = "https://www.pivoxquant.com/journal";
    at("/mirror"); // walked here later; the dashboard layout mounted again
    expect(shouldOpenOnCover()).toBe(false);
    navName = "https://www.pivoxquant.com/mirror";
    expect(shouldOpenOnCover()).toBe(true);
  });
});
