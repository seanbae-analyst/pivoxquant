/**
 * launch-cover (2026-10-10): an install that saved start_url "/mirror" opens on
 * the cover once per launch; nothing else is redirected.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

let standalone = true;
vi.mock("@/components/pwa/app-cover", () => ({ isStandaloneDisplay: () => standalone }));

import { markLaunchCovered, shouldOpenOnCover } from "../launch-cover";

function at(path: string) {
  window.history.replaceState(null, "", path);
}

let navType = "navigate";
beforeEach(() => {
  standalone = true;
  navType = "navigate";
  window.sessionStorage.clear();
  vi.spyOn(window.performance, "getEntriesByType").mockImplementation(
    () => [{ type: navType }] as unknown as PerformanceEntryList,
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
});
