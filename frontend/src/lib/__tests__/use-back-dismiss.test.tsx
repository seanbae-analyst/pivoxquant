/**
 * useBackDismiss — Android / browser back closes an overlay
 * (lib/use-back-dismiss.ts). Shared by components/ui/sheet.tsx and the
 * bottom-nav 더보기 drawer.
 */
import * as React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, act, waitFor } from "@testing-library/react";
import {
  useBackDismiss,
  countStaleTrailing,
  markOverlayNavigation,
  __resetBackDismissForTests,
} from "@/lib/use-back-dismiss";

type S = { __pqOverlays?: string[]; page?: string } | null;
const stack = () => (window.history.state as S)?.__pqOverlays;

function Overlay({
  open,
  onClose,
  enabled,
  blocked,
}: {
  open: boolean;
  onClose: () => void;
  enabled?: boolean;
  blocked?: boolean;
}) {
  useBackDismiss(open, onClose, { enabled, blocked });
  return null;
}

beforeEach(() => {
  window.history.replaceState({ page: "base" }, "");
});
afterEach(async () => {
  vi.restoreAllMocks();
  cleanup();
  // Let an unmounted overlay's history.go(-n) land before the next case.
  await new Promise((r) => setTimeout(r, 30));
  __resetBackDismissForTests();
});

describe("countStaleTrailing", () => {
  it("counts closed overlays on top of the stack, stopping at an open one", () => {
    expect(countStaleTrailing([], new Set())).toBe(0);
    expect(countStaleTrailing(["a"], new Set(["a"]))).toBe(0);
    expect(countStaleTrailing(["a", "b"], new Set(["a"]))).toBe(1);
    expect(countStaleTrailing(["a", "b"], new Set())).toBe(2);
    expect(countStaleTrailing(["a", "b", "c"], new Set(["b"]))).toBe(1);
  });
});

describe("useBackDismiss", () => {
  it("pushes one entry on open (keeping existing state) and back calls onClose", async () => {
    const onClose = vi.fn();
    const push = vi.spyOn(window.history, "pushState");
    render(<Overlay open onClose={onClose} />);
    expect(push).toHaveBeenCalledTimes(1);
    expect(stack()).toHaveLength(1);
    expect((window.history.state as S)?.page).toBe("base");

    act(() => window.history.back());
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(stack()).toBeUndefined();
  });

  it("programmatic close goes back exactly once (no double back)", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<Overlay open onClose={onClose} />);
    expect(stack()).toHaveLength(1);
    rerender(<Overlay open={false} onClose={onClose} />);
    await waitFor(() => expect(stack()).toBeUndefined());
    expect((window.history.state as S)?.page).toBe("base");
    // The pop it caused does not loop back into onClose.
    expect(onClose).not.toHaveBeenCalled();
  });

  it("two overlays closing in the same tick pop both entries at once", async () => {
    const { rerender } = render(
      <>
        <Overlay open onClose={() => {}} />
        <Overlay open onClose={() => {}} />
      </>,
    );
    expect(stack()).toHaveLength(2);
    rerender(
      <>
        <Overlay open={false} onClose={() => {}} />
        <Overlay open={false} onClose={() => {}} />
      </>,
    );
    await waitFor(() => expect(stack()).toBeUndefined());
    expect((window.history.state as S)?.page).toBe("base");
  });

  it("back closes only the top overlay of a nested pair", async () => {
    const outer = vi.fn();
    const inner = vi.fn();
    render(
      <>
        <Overlay open onClose={outer} />
        <Overlay open onClose={inner} />
      </>,
    );
    act(() => window.history.back());
    await waitFor(() => expect(inner).toHaveBeenCalledTimes(1));
    expect(outer).not.toHaveBeenCalled();
    expect(stack()).toHaveLength(1);
  });

  it("a hand-off (one closes, another opens in the same tick) reuses the entry", async () => {
    const push = vi.spyOn(window.history, "pushState");
    const go = vi.spyOn(window.history, "go");
    const { rerender } = render(
      <>
        <Overlay open onClose={() => {}} />
        <Overlay open={false} onClose={() => {}} />
      </>,
    );
    expect(push).toHaveBeenCalledTimes(1);
    rerender(
      <>
        <Overlay open={false} onClose={() => {}} />
        <Overlay open onClose={() => {}} />
      </>,
    );
    await new Promise((r) => setTimeout(r, 50));
    expect(stack()).toHaveLength(1);
    expect(push).toHaveBeenCalledTimes(1); // replaced, not stacked
    expect(go).not.toHaveBeenCalled();
  });

  it("blocked → back is swallowed (entry re-pushed, no onClose)", async () => {
    const onClose = vi.fn();
    render(<Overlay open onClose={onClose} blocked />);
    act(() => window.history.back());
    await waitFor(() => expect(stack()).toHaveLength(1));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("enabled=false never touches history", () => {
    const push = vi.spyOn(window.history, "pushState");
    render(<Overlay open onClose={() => {}} enabled={false} />);
    expect(push).not.toHaveBeenCalled();
    expect(stack()).toBeUndefined();
  });

  it("closing for a navigation leaves history alone (does not cancel it)", async () => {
    const goSpy = vi.spyOn(window.history, "go");
    const { rerender } = render(<Overlay open onClose={() => {}} />);
    markOverlayNavigation();
    rerender(<Overlay open={false} onClose={() => {}} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(goSpy).not.toHaveBeenCalled();
    goSpy.mockRestore();
  });
});
