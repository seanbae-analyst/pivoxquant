import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ErrorBoundary from "@/app/error";

describe("ErrorBoundary page", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("renders the error eyebrow, headline, and reset button", () => {
    const reset = vi.fn();
    const error = new Error("synthetic test failure");
    render(<ErrorBoundary error={error} reset={reset} />);

    expect(
      screen.getByText(/화면을 그리다 멈췄어요/),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /다시 시도/ }),
    ).toBeInTheDocument();
  });

  it("invokes reset() when the 다시 시도 button is clicked", async () => {
    const reset = vi.fn();
    const user = userEvent.setup();
    const error = new Error("synthetic test failure");
    render(<ErrorBoundary error={error} reset={reset} />);

    await user.click(screen.getByRole("button", { name: /다시 시도/ }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("renders a '거울로 돌아가기' link pointing at /mirror", () => {
    const reset = vi.fn();
    const error = new Error("synthetic test failure");
    render(<ErrorBoundary error={error} reset={reset} />);

    const back = screen.getByRole("link", { name: /거울로 돌아가기/ });
    expect(back).toBeInTheDocument();
    expect(back).toHaveAttribute("href", "/mirror");
  });

  it("shows raw error message in non-production (dev/test) mode", () => {
    const reset = vi.fn();
    const error = new Error("very specific dev message");
    render(<ErrorBoundary error={error} reset={reset} />);

    // In dev/test (NODE_ENV !== 'production') the raw error.message renders.
    expect(screen.getByText(/very specific dev message/)).toBeInTheDocument();
  });
});
