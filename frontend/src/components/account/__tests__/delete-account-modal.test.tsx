import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the API + toast surfaces — keep the test fast and offline.
// ApiError must be a real class so the component's `e instanceof ApiError`
// branch type-checks and runs.
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { apiFetch, ApiError } from "@/lib/api";
import { toast } from "sonner";
import { DeleteAccountModal } from "@/components/account/delete-account-modal";

const mockedApiFetch = vi.mocked(apiFetch);
const mockedToastError = vi.mocked(toast.error);

describe("<DeleteAccountModal /> — self-service deletion (GAP-J)", () => {
  beforeEach(() => {
    mockedApiFetch.mockReset();
    mockedToastError.mockReset();
    cleanup();
  });

  it("offers the 30-day soft-delete as the default action (no mailto)", () => {
    render(<DeleteAccountModal onClose={() => {}} />);
    expect(
      screen.getByRole("button", { name: /30일 후 삭제/ }),
    ).toBeInTheDocument();
    // The immediate path is hidden behind a secondary reveal.
    expect(screen.queryByPlaceholderText("삭제")).not.toBeInTheDocument();
    // No "contact support" mailto anywhere.
    expect(screen.queryByText(/support@pivoxquant/i)).not.toBeInTheDocument();
  });

  it("soft-delete posts to /delete-request and shows the grace-period panel", async () => {
    mockedApiFetch.mockResolvedValueOnce({ ok: true });
    render(<DeleteAccountModal onClose={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: /30일 후 삭제/ }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/auth/delete-request",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText(/탈퇴 요청이 접수되었습니다/)).toBeInTheDocument();
    expect(screen.getByText(/30일 후/)).toBeInTheDocument();
  });

  it("gates the immediate hard-delete behind a type-to-confirm phrase", async () => {
    mockedApiFetch.mockResolvedValueOnce({ ok: true });
    render(<DeleteAccountModal onClose={() => {}} />);

    await userEvent.click(
      screen.getByRole("button", { name: /지금 즉시 영구 삭제/ }),
    );

    const confirmBtn = screen.getByRole("button", { name: "영구 삭제" });
    expect(confirmBtn).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText("삭제"), "삭제");
    expect(confirmBtn).toBeEnabled();

    await userEvent.click(confirmBtn);
    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/auth/delete-account",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
    expect(await screen.findByText(/계정이 삭제되었습니다/)).toBeInTheDocument();
  });

  it("surfaces a toast on API failure and stays on the form", async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError(500, "서버 오류"));
    render(<DeleteAccountModal onClose={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: /30일 후 삭제/ }));

    await waitFor(() => expect(mockedToastError).toHaveBeenCalledWith("서버 오류"));
    // Did not advance to the success panel.
    expect(screen.queryByText(/탈퇴 요청이 접수되었습니다/)).not.toBeInTheDocument();
  });
});
