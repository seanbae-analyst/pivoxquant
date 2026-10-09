/**
 * Only the Korean catalog ships in the shared bundle (2026-10-09 perf).
 * English is a lazy chunk loaded the first time the locale is "en"; until it
 * lands `t()` answers in Korean — never a raw key.
 */
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { LocaleProvider, useLocale } from "@/lib/locale";
import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

function Label() {
  const { t, setLocale } = useLocale();
  return (
    <div>
      <span data-testid="label">{t("auth.login.wakeRetry")}</span>
      <button onClick={() => setLocale("en")}>en</button>
    </div>
  );
}

afterEach(() => {
  document.cookie = "sp_locale=ko; path=/";
});

describe("LocaleProvider lazy English", () => {
  it("renders Korean by default", () => {
    render(<LocaleProvider><Label /></LocaleProvider>);
    expect(screen.getByTestId("label").textContent).toBe(ko.auth.login.wakeRetry);
  });

  it("switches to English once the chunk has loaded", async () => {
    render(<LocaleProvider><Label /></LocaleProvider>);
    await act(async () => {
      screen.getByText("en").click();
    });
    await waitFor(() =>
      expect(screen.getByTestId("label").textContent).toBe(en.auth.login.wakeRetry),
    );
  });

  it("honours an existing en cookie on mount", async () => {
    document.cookie = "sp_locale=en; path=/";
    render(<LocaleProvider><Label /></LocaleProvider>);
    await waitFor(() =>
      expect(screen.getByTestId("label").textContent).toBe(en.auth.login.wakeRetry),
    );
  });
});
