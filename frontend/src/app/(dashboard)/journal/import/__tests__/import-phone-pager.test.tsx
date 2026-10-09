/**
 * /journal/import on a phone (CEO 2026-10-09 "앱처럼"): the three input
 * methods are swipeable pages (components/journal/journal-pager) and the page
 * in view is the submit target.
 *
 * Pinned here:
 *   - one pager page per input method, in the desktop tab order;
 *   - `?tab=image` and the share-sheet `?text=` still pick the starting page;
 *   - a settled swipe moves the submit target (file → text) and the payload
 *     is the same JSON body the desktop text tab sends;
 *   - consent still gates the submit; the capture page shows no submit bar;
 *   - the AI read stays hidden while NEXT_PUBLIC_AI_READ is off;
 *   - desktop keeps its tab buttons and shows one panel at a time.
 *
 * jsdom has no layout, so the track's width is stubbed; snap, momentum and
 * the sticky bar are covered by the 390x844 Playwright pass.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {}
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("swr", () => ({ mutate: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { id: 7 } }) }));

let search = "";
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(search),
}));

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import ImportPage from "@/app/(dashboard)/journal/import/page";

const mockedFetch = vi.mocked(apiFetch);
const WIDTH = 390;

function stubViewport(phone: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("max-width") ? phone : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderPage(query = "") {
  search = query;
  const utils = render(<ImportPage />);
  const track = screen.getByTestId("journal-pager");
  Object.defineProperty(track, "clientWidth", { value: WIDTH, configurable: true });
  track.scrollTo = vi.fn() as unknown as typeof track.scrollTo;
  // Let a requested starting page commit (it lands on the next frame).
  act(() => {
    vi.advanceTimersByTime(50);
  });
  return { ...utils, track };
}

function swipeTo(track: HTMLElement, page: number) {
  track.scrollLeft = page * WIDTH;
  fireEvent.scroll(track);
  act(() => {
    vi.advanceTimersByTime(200);
  });
}

const phoneTab = (id: string) => screen.getByTestId(`journal-tab-${id}`);
const submit = () => screen.getByTestId("import-submit") as HTMLButtonElement;
const textArea = () => document.getElementById("import-text") as HTMLTextAreaElement;
const consentBox = () => screen.getByRole("checkbox") as HTMLInputElement;

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("scrollTo", vi.fn());
  window.localStorage.clear();
  mockedFetch.mockReset();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("/journal/import on a phone", () => {
  beforeEach(() => stubViewport(true));

  it("renders one swipeable page per input method, file first", () => {
    renderPage();
    const ids = ["file", "text", "image"];
    for (const id of ids) expect(screen.getByTestId(`journal-page-${id}`)).toBeInTheDocument();
    expect(phoneTab("file")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("journal-page-text")).toHaveAttribute("inert");
    expect(screen.getByTestId("journal-page-dots")).toBeInTheDocument();
  });

  it("opens on the capture page for ?tab=image and hides the submit bar there", () => {
    renderPage("tab=image");
    expect(phoneTab("image")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("journal-page-image")).not.toHaveAttribute("inert");
    expect(submit().parentElement).toHaveClass("hidden");
    expect(screen.getByTestId("import-action-bar").className).not.toContain("sticky");
  });

  it("opens on the text page with the share-sheet text filled in", () => {
    renderPage("text=" + encodeURIComponent("삼성전자 10주 매수 체결 71,200원"));
    expect(phoneTab("text")).toHaveAttribute("aria-selected", "true");
    expect(textArea().value).toBe(
      "삼성전자 10주 매수 체결 71,200원",
    );
  });

  it("pins the submit on file/text pages and keeps it consent-gated", () => {
    renderPage();
    expect(screen.getByTestId("import-action-bar").className).toContain("max-md:sticky");
    swipeTo(screen.getByTestId("journal-pager"), 1);
    fireEvent.change(textArea(), {
      target: { value: "삼성전자 10주 매수 체결 71,200원" },
    });
    expect(submit()).toBeDisabled();
    fireEvent.click(consentBox());
    expect(submit()).not.toBeDisabled();
  });

  it("sends the page in view: a swipe to text submits the text body", async () => {
    mockedFetch.mockResolvedValue({
      batch: { parsed_count: 1, duplicate_count: 0, unresolved_count: 0 },
      pending: [],
      unmapped_headers: [],
    });
    const { track } = renderPage();
    fireEvent.click(consentBox());
    swipeTo(track, 1);
    expect(phoneTab("text")).toHaveAttribute("aria-selected", "true");
    fireEvent.change(textArea(), {
      target: { value: "  삼성전자 10주 매수 체결 71,200원 " },
    });
    await act(async () => {
      fireEvent.click(submit());
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      API.imports.create,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          text: "삼성전자 10주 매수 체결 71,200원",
          source: "screenshot_text",
          consent: true,
        }),
      }),
    );
    // The result lands below the pager — it is brought into view.
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("keeps the AI read hidden while NEXT_PUBLIC_AI_READ is off", () => {
    renderPage("text=" + encodeURIComponent("알 수 없는 형식의 체결 문자"));
    expect(screen.getByTestId("ai-text-read-panel")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /AI/ })).toBeNull();
  });

  it("keeps the webhook-token deep link", () => {
    renderPage();
    expect(
      screen.getAllByRole("link").some((a) => a.getAttribute("href") === "/settings#import-tokens"),
    ).toBe(true);
  });
});

describe("/journal/import on desktop", () => {
  beforeEach(() => stubViewport(false));

  it("keeps the tab buttons and shows only the selected panel", () => {
    renderPage();
    const tabs = screen.getByTestId("import-tabs-desktop");
    expect(tabs).toHaveClass("md:flex");
    expect(screen.getByTestId("journal-page-file")).not.toHaveAttribute("inert");
    expect(screen.getByTestId("journal-page-text")).not.toHaveAttribute("role");
    // Inactive panels are hidden at md and up; the pager boxes dissolve.
    expect(screen.getByTestId("journal-page-text").firstElementChild).toHaveClass("md:hidden");
    expect(screen.getByTestId("journal-page-file").firstElementChild).not.toHaveClass("md:hidden");

    fireEvent.click(screen.getByTestId("import-tab-image"));
    expect(screen.getByTestId("journal-page-image").firstElementChild).not.toHaveClass("md:hidden");
    expect(screen.getByTestId("journal-page-file").firstElementChild).toHaveClass("md:hidden");
  });
});
