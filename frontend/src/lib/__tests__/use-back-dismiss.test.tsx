/**
 * useBackDismiss — Android / browser back closes an overlay
 * (lib/use-back-dismiss.ts). Shared by components/ui/sheet.tsx and the
 * bottom-nav 더보기 drawer.
 */
import * as React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, act, waitFor, fireEvent, screen } from "@testing-library/react";
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime";
import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import {
  useBackDismiss,
  countStaleTrailing,
  markOverlayNavigation,
  navigateFromOverlay,
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
  window.history.replaceState({ page: "base" }, "", "/mirror");
});

/** A stand-in App Router that moves real (jsdom) history like Next does:
 *  a navigation's entry carries Next's own state, not the overlay marker. */
function fakeRouter() {
  const r = {
    push: vi.fn((href: string) => window.history.pushState({ page: href }, "", href)),
    replace: vi.fn((href: string) => window.history.replaceState({ page: href }, "", href)),
  };
  return r as typeof r & AppRouterInstance;
}

function SheetWithLink({
  open,
  onClose,
  router,
}: {
  open: boolean;
  onClose: () => void;
  router: AppRouterInstance | null;
}) {
  return (
    <AppRouterContext.Provider value={router}>
      <Overlay open={open} onClose={onClose} />
      {open ? (
        <a href="/settings" onClick={onClose}>
          설정
        </a>
      ) : null}
    </AppRouterContext.Provider>
  );
}
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

  it("a link inside the overlay replaces the overlay's entry: one Back returns to the opener", async () => {
    const router = fakeRouter();
    const go = vi.spyOn(window.history, "go");
    const before = window.history.length;
    let open = true;
    const onClose = vi.fn(() => {
      open = false;
    });
    const { rerender } = render(<SheetWithLink open onClose={onClose} router={router} />);
    expect(window.history.length).toBe(before + 1); // the overlay's entry

    // Click 설정: handled before next/link (default prevented → no push),
    // the link's own onClick (closing the sheet) still runs.
    const notPrevented = fireEvent.click(screen.getByText("설정"));
    expect(notPrevented).toBe(false);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith("/settings");
    expect(router.push).not.toHaveBeenCalled();
    rerender(<SheetWithLink open={open} onClose={onClose} router={router} />);

    // Arrived: the overlay entry became /settings — no extra entry left behind.
    await new Promise((r) => setTimeout(r, 30));
    expect(go).not.toHaveBeenCalled(); // and the navigation was not cancelled
    expect(window.location.pathname).toBe("/settings");
    expect(window.history.length).toBe(before + 1);
    expect(stack()).toBeUndefined();

    // One Back → the page that opened the sheet.
    act(() => window.history.back());
    await waitFor(() => expect((window.history.state as S)?.page).toBe("base"));
    expect(window.location.pathname).toBe("/mirror");
  });

  it("without an App Router mounted, a link is left to the browser (old behaviour)", async () => {
    const go = vi.spyOn(window.history, "go");
    const onClose = vi.fn();
    // Record what reached the browser, then stop jsdom's own navigation.
    let reachedBrowser = false;
    const sink = (e: Event) => {
      reachedBrowser = !e.defaultPrevented;
      e.preventDefault();
    };
    window.addEventListener("click", sink);
    const { rerender } = render(<SheetWithLink open onClose={onClose} router={null} />);
    fireEvent.click(screen.getByText("설정"));
    window.removeEventListener("click", sink);
    expect(reachedBrowser).toBe(true);
    rerender(<SheetWithLink open={false} onClose={onClose} router={null} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(go).not.toHaveBeenCalled(); // still never cancels the navigation
  });

  it("only the top overlay takes the link over (one replace for a nested pair)", () => {
    const router = fakeRouter();
    render(
      <AppRouterContext.Provider value={router}>
        <Overlay open onClose={() => {}} />
        <Overlay open onClose={() => {}} />
        <a href="/settings">설정</a>
      </AppRouterContext.Provider>,
    );
    fireEvent.click(screen.getByText("설정"));
    expect(router.replace).toHaveBeenCalledTimes(1);
  });

  it("modified clicks, new-tab links and in-page hashes are not taken over", () => {
    const router = fakeRouter();
    render(
      <AppRouterContext.Provider value={router}>
        <Overlay open onClose={() => {}} />
        <a href="/settings">a</a>
        <a href="/settings" target="_blank">b</a>
        <a href="#top">c</a>
        <a href="https://example.com/x">d</a>
      </AppRouterContext.Provider>,
    );
    const sink = (e: Event) => e.preventDefault(); // jsdom: never navigate
    window.addEventListener("click", sink);
    fireEvent.click(screen.getByText("a"), { metaKey: true });
    fireEvent.click(screen.getByText("b"));
    fireEvent.click(screen.getByText("c"));
    fireEvent.click(screen.getByText("d"));
    window.removeEventListener("click", sink);
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("navigateFromOverlay", () => {
  it("replaces while the overlay's entry is current, pushes otherwise", () => {
    const router = fakeRouter();
    const { rerender } = render(<Overlay open onClose={() => {}} />);
    navigateFromOverlay(router, "/journal");
    expect(router.replace).toHaveBeenCalledWith("/journal");
    expect(router.push).not.toHaveBeenCalled();

    rerender(<Overlay open={false} onClose={() => {}} />);
    window.history.replaceState({ page: "base" }, "", "/mirror");
    navigateFromOverlay(router, "/portfolio");
    expect(router.push).toHaveBeenCalledWith("/portfolio");
  });
});
