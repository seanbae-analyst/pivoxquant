/**
 * Settings on a phone (2026-10-07): a list of rows, a row opens one section,
 * back returns to the list. The open section lives in the URL, and the old
 * anchors (#import-tokens …) still open their section.
 */
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent, act } from "@testing-library/react";

import {
  SettingsPhoneList,
  SettingsPhoneBack,
  paneFromLocation,
  useSettingsPane,
} from "../settings-phone-nav";

function Probe() {
  const pane = useSettingsPane();
  return (
    <div>
      <span data-testid="pane">{pane ?? "list"}</span>
      {pane === null ? <SettingsPhoneList /> : <SettingsPhoneBack pane={pane} />}
    </div>
  );
}

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/settings");
});

describe("paneFromLocation", () => {
  it("reads ?s= and the legacy anchors", () => {
    expect(paneFromLocation("?s=notifications", "")).toBe("notifications");
    expect(paneFromLocation("", "#import-tokens")).toBe("import");
    expect(paneFromLocation("", "#section-e")).toBe("privacy");
    expect(paneFromLocation("?s=bogus", "")).toBeNull();
    expect(paneFromLocation("", "")).toBeNull();
  });
});

describe("settings phone navigation", () => {
  it("row opens its section in the URL; back returns to the list", () => {
    window.history.replaceState(null, "", "/settings");
    render(<Probe />);
    expect(screen.getByTestId("pane").textContent).toBe("list");
    expect(screen.getAllByRole("button")).toHaveLength(4);

    fireEvent.click(screen.getByTestId("settings-row-import"));
    expect(window.location.search).toBe("?s=import");
    expect(screen.getByTestId("pane").textContent).toBe("import");
    expect(screen.getByText("· 체결 자동 기록")).toBeTruthy();

    // Pushed by the row → back pops the history entry.
    act(() => {
      window.history.replaceState(null, "", "/settings");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(screen.getByTestId("pane").textContent).toBe("list");
  });

  it("a deep link with no list behind it: back replaces the URL", () => {
    window.history.replaceState(null, "", "/settings?s=privacy");
    render(<Probe />);
    expect(screen.getByTestId("pane").textContent).toBe("privacy");
    fireEvent.click(screen.getByTestId("settings-phone-back"));
    expect(window.location.search).toBe("");
    expect(screen.getByTestId("pane").textContent).toBe("list");
  });
});
