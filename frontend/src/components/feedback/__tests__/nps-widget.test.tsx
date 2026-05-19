import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the API + toast surfaces — keep the test fast and offline.
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { apiFetch } from "@/lib/api";
import { toast } from "sonner";
import { NpsWidget } from "@/components/feedback/NpsWidget";

const mockedApiFetch = vi.mocked(apiFetch);
const mockedToastSuccess = vi.mocked(toast.success);
const mockedToastError = vi.mocked(toast.error);

describe("<NpsWidget /> — Wave G C-AC2", () => {
  beforeEach(() => {
    mockedApiFetch.mockReset();
    mockedToastSuccess.mockReset();
    mockedToastError.mockReset();
    window.localStorage.clear();
    cleanup();
  });

  it("renders all 10 score buttons (1–10)", () => {
    render(<NpsWidget weeklyMemoId="memo-1" />);
    for (let i = 1; i <= 10; i++) {
      expect(
        screen.getByRole("button", { name: `${i}점` }),
      ).toBeInTheDocument();
    }
  });

  it("renders the KR prompt + scale anchors", () => {
    render(<NpsWidget weeklyMemoId="memo-1" />);
    expect(
      screen.getByText(/이번 주간 메모를 친구에게 추천할 가능성/),
    ).toBeInTheDocument();
    expect(screen.getByText("1 — 매우 별로")).toBeInTheDocument();
    expect(screen.getByText("10 — 매우 좋음")).toBeInTheDocument();
  });

  it("POSTs the score + memo id, then shows acknowledgement", async () => {
    mockedApiFetch.mockResolvedValueOnce({
      ok: true,
      feedback: {
        id: 1,
        score: 9,
        weekly_memo_id: "memo-1",
        created_at: "2026-05-19T00:00:00",
      },
    });

    const onSubmitted = vi.fn();
    const user = userEvent.setup();
    render(<NpsWidget weeklyMemoId="memo-1" onSubmitted={onSubmitted} />);

    await user.click(screen.getByRole("button", { name: "9점" }));

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledTimes(1);
    });

    const [path, init] = mockedApiFetch.mock.calls[0];
    expect(path).toBe("/api/feedback/nps");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      score: 9,
      weekly_memo_id: "memo-1",
    });

    expect(mockedToastSuccess).toHaveBeenCalledWith("감사합니다");
    expect(onSubmitted).toHaveBeenCalledWith(9);
    expect(
      await screen.findByTestId("nps-widget-thanks"),
    ).toBeInTheDocument();
  });

  it("omits weekly_memo_id from body when not supplied", async () => {
    mockedApiFetch.mockResolvedValueOnce({
      ok: true,
      feedback: {
        id: 1,
        score: 7,
        weekly_memo_id: null,
        created_at: "2026-05-19T00:00:00",
      },
    });

    const user = userEvent.setup();
    render(<NpsWidget />);
    await user.click(screen.getByRole("button", { name: "7점" }));

    await waitFor(() => expect(mockedApiFetch).toHaveBeenCalledTimes(1));
    const [, init] = mockedApiFetch.mock.calls[0];
    const body = JSON.parse(init?.body as string);
    expect(body.score).toBe(7);
    expect(body.weekly_memo_id).toBeUndefined();
  });

  it("writes localStorage on submit so subsequent renders dedup", async () => {
    mockedApiFetch.mockResolvedValueOnce({
      ok: true,
      feedback: {
        id: 1,
        score: 8,
        weekly_memo_id: "memo-7",
        created_at: "2026-05-19T00:00:00",
      },
    });

    const user = userEvent.setup();
    const { unmount } = render(<NpsWidget weeklyMemoId="memo-7" />);
    await user.click(screen.getByRole("button", { name: "8점" }));

    await waitFor(() => {
      expect(window.localStorage.getItem("pivox_nps_submitted_memo-7")).not.toBeNull();
    });

    unmount();

    // Re-mount: the widget must NOT show the prompt again for the same memo.
    render(<NpsWidget weeklyMemoId="memo-7" />);
    await waitFor(() => {
      expect(screen.queryByTestId("nps-widget")).not.toBeInTheDocument();
    });
  });

  it("shows error toast and keeps the prompt when the POST fails", async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error("boom"));
    const user = userEvent.setup();
    render(<NpsWidget weeklyMemoId="memo-x" />);
    await user.click(screen.getByRole("button", { name: "5점" }));

    await waitFor(() => {
      expect(mockedToastError).toHaveBeenCalled();
    });

    // localStorage must NOT be written on failure — user can retry.
    expect(window.localStorage.getItem("pivox_nps_submitted_memo-x")).toBeNull();
    // Prompt still visible.
    expect(screen.getByTestId("nps-widget")).toBeInTheDocument();
  });

  it("uses v3 design tokens (Bronze accent + neutral surface)", () => {
    const { container } = render(<NpsWidget weeklyMemoId="memo-tokens" />);
    const html = container.innerHTML;
    // Bronze accent (NpsWidget hover/focus ring) — v3 token name.
    expect(html).toContain("accent");
    // Neutral surface — v3 semantic token (no hardcoded hex).
    expect(html).toContain("bg-card");
    expect(html).toContain("border-border");
    expect(html).toContain("text-foreground");
    // No raw hex colors — v3 lock-in (design-token-drift gate).
    expect(html).not.toMatch(/#[0-9a-fA-F]{6}/);
  });

  it("disables all buttons while a submit is in flight", async () => {
    // Never resolves — keeps state in busy mode.
    mockedApiFetch.mockImplementationOnce(
      () => new Promise(() => {}),
    );
    const user = userEvent.setup();
    render(<NpsWidget weeklyMemoId="memo-busy" />);
    await user.click(screen.getByRole("button", { name: "6점" }));

    await waitFor(() => {
      for (let i = 1; i <= 10; i++) {
        expect(screen.getByRole("button", { name: `${i}점` })).toBeDisabled();
      }
    });
  });
});
