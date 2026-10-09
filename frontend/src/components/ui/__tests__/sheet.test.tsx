/**
 * <Sheet /> — the shared modal primitive (components/ui/sheet.tsx).
 *
 *   - gesture math: dismiss threshold (distance OR velocity), rubber band,
 *     release velocity
 *   - desktop: caller's overlay/panel markup, Escape, backdrop, focus trap,
 *     focus returns to the trigger
 *   - phone: bottom sheet, backdrop close, drag-to-dismiss vs snap back,
 *     Android/browser back closes it, in-app close pops its history entry,
 *     body scroll lock
 */
import * as React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, act } from "@testing-library/react";
import {
  Sheet,
  SheetFooter,
  computeVelocity,
  rubberBand,
  sheetDismissDistance,
  sheetDragOffset,
  shouldDismissSheet,
  sheetClock,
  SHEET_DISMISS_VELOCITY,
  SHEET_RUBBER_BAND_LIMIT,
  type SheetHandle,
} from "@/components/ui/sheet";
import { __resetBackDismissForTests } from "@/lib/use-back-dismiss";

const originalMatchMedia = window.matchMedia;

function setPhone(on: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: on && q === "(max-width: 767px)",
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
}

afterEach(async () => {
  cleanup();
  // Let a closing sheet's history.go(-n) land before the next case.
  await new Promise((r) => setTimeout(r, 30));
  window.matchMedia = originalMatchMedia;
  vi.restoreAllMocks();
  __resetBackDismissForTests();
  document.body.removeAttribute("style");
});

// ─── Gesture math ──────────────────────────────────────────────────────────

describe("sheet gesture math", () => {
  it("dismiss distance is 30% of height, clamped to 64..200px", () => {
    expect(sheetDismissDistance(100)).toBe(64);
    expect(sheetDismissDistance(500)).toBe(150);
    expect(sheetDismissDistance(900)).toBe(200);
  });

  it("dismisses past the distance threshold on a slow release", () => {
    expect(shouldDismissSheet({ offset: 149, velocity: 0, height: 500 })).toBe(false);
    expect(shouldDismissSheet({ offset: 150, velocity: 0, height: 500 })).toBe(true);
  });

  it("a fast downward fling dismisses even when short", () => {
    expect(shouldDismissSheet({ offset: 20, velocity: SHEET_DISMISS_VELOCITY, height: 800 })).toBe(true);
    expect(shouldDismissSheet({ offset: 20, velocity: SHEET_DISMISS_VELOCITY - 0.01, height: 800 })).toBe(false);
  });

  it("flicking back up cancels a long drag; dragging up never dismisses", () => {
    expect(shouldDismissSheet({ offset: 300, velocity: -0.4, height: 800 })).toBe(false);
    expect(shouldDismissSheet({ offset: -40, velocity: 2, height: 800 })).toBe(false);
    expect(shouldDismissSheet({ offset: 0, velocity: 2, height: 800 })).toBe(false);
  });

  it("rubber band resists, keeps sign, never exceeds the limit", () => {
    expect(rubberBand(0)).toBe(0);
    const up = rubberBand(-100);
    expect(up).toBeLessThan(0);
    expect(Math.abs(up)).toBeLessThan(100);
    expect(Math.abs(rubberBand(-100000))).toBeLessThan(SHEET_RUBBER_BAND_LIMIT);
    expect(Math.abs(rubberBand(-200))).toBeGreaterThan(Math.abs(rubberBand(-100)));
  });

  it("drag offset: free downward when dismissible, rubber band otherwise and upward", () => {
    expect(sheetDragOffset(120, true)).toBe(120);
    expect(sheetDragOffset(120, false)).toBeLessThan(SHEET_RUBBER_BAND_LIMIT);
    expect(sheetDragOffset(-120, true)).toBeCloseTo(rubberBand(-120));
  });

  it("velocity uses only the last 100ms of samples", () => {
    expect(computeVelocity([])).toBe(0);
    expect(computeVelocity([{ t: 0, y: 0 }])).toBe(0);
    // An old slow segment, then 40px in the last 40ms = 1 px/ms.
    const v = computeVelocity([
      { t: 0, y: 0 },
      { t: 500, y: 10 },
      { t: 520, y: 30 },
      { t: 540, y: 50 },
    ]);
    expect(v).toBeCloseTo(1);
  });
});

// ─── Desktop ───────────────────────────────────────────────────────────────

function Harness({
  initialOpen = true,
  onClose,
  dismissible = true,
  sheetRef,
}: {
  initialOpen?: boolean;
  onClose?: () => void;
  dismissible?: boolean;
  sheetRef?: React.Ref<SheetHandle>;
}) {
  const [open, setOpen] = React.useState(initialOpen);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        open-trigger
      </button>
      <Sheet
        ref={sheetRef}
        open={open}
        onClose={() => {
          onClose?.();
          setOpen(false);
        }}
        ariaLabel="테스트 시트"
        dismissible={dismissible}
        desktopOverlayClassName="test-overlay"
        desktopOverlayStyle={{ position: "fixed", inset: 0 }}
        desktopPanelClassName="test-panel"
        desktopPanelStyle={{ maxWidth: 560 }}
      >
        <form>
          <input aria-label="first-field" />
          <SheetFooter desktopStyle={{ display: "flex", marginTop: 12 }}>
            <button type="button">last-button</button>
          </SheetFooter>
        </form>
      </Sheet>
    </>
  );
}

describe("<Sheet /> on desktop (md+)", () => {
  it("renders the caller's overlay + panel markup as a modal dialog", () => {
    render(<Harness />);
    const dialog = screen.getByRole("dialog", { name: "테스트 시트" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("data-sheet-presentation", "desktop");
    expect(dialog.className).toBe("test-overlay");
    const panel = dialog.firstElementChild as HTMLElement;
    expect(panel.className).toBe("test-panel");
    expect(panel.style.maxWidth).toBe("560px");
    // Footer is the caller's div, not the sticky phone footer.
    expect(document.querySelector("[data-sheet-footer]")).toBeNull();
  });

  it("Escape and a backdrop click close it; a click inside does not", () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("first-field"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();

    cleanup();
    const onClose2 = vi.fn();
    render(<Harness onClose={onClose2} />);
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose2).toHaveBeenCalledTimes(1);
  });

  it("not dismissible → Escape and backdrop are ignored", () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} dismissible={false} />);
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("traps Tab inside and returns focus to the trigger on close", async () => {
    render(<Harness initialOpen={false} />);
    const trigger = screen.getByText("open-trigger");
    trigger.focus();
    fireEvent.click(trigger);
    const first = await screen.findByLabelText("first-field");
    await waitFor(() => expect(document.activeElement).toBe(first));

    const last = screen.getByText("last-button");
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it("dismiss() closes immediately on desktop", () => {
    const ref = React.createRef<SheetHandle>();
    const onClose = vi.fn();
    render(<Harness sheetRef={ref} onClose={onClose} />);
    act(() => ref.current?.dismiss());
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

// ─── Phone ─────────────────────────────────────────────────────────────────

let now = 0;

function touch(el: Element, type: string, y: number, x = 100) {
  const ev = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(ev, "touches", {
    value: type === "touchend" ? [] : [{ clientX: x, clientY: y }],
  });
  el.dispatchEvent(ev);
  return ev;
}

describe("<Sheet /> on a phone (<768px)", () => {
  beforeEach(() => {
    setPhone(true);
    now = 1000;
    // Drag velocity samples read this clock — drive it directly.
    vi.spyOn(sheetClock, "now").mockImplementation(() => now);
    window.history.replaceState({ page: "base" }, "");
  });

  it("renders a bottom sheet with a grabber, sticky footer and body lock", () => {
    render(<Harness />);
    const dialog = screen.getByRole("dialog", { name: "테스트 시트" });
    expect(dialog).toHaveAttribute("data-sheet-presentation", "phone");
    expect(dialog.querySelector("[data-sheet-handle]")).not.toBeNull();
    expect(dialog.querySelector("[data-sheet-footer]")).not.toBeNull();
    expect(document.body.style.position).toBe("fixed");
    expect(document.documentElement.hasAttribute("data-pq-sheet-open")).toBe(true);
  });

  it("does not autofocus a text field on a phone (keyboard stays down)", async () => {
    render(<Harness />);
    const dialog = screen.getByRole("dialog");
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
    expect(document.activeElement).not.toBe(screen.getByLabelText("first-field"));
  });

  it("backdrop tap closes it (after the exit animation) and unlocks the body", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    fireEvent.click(screen.getByTestId("sheet-backdrop"));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 3000 });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull(), { timeout: 3000 });
    expect(document.body.style.position).toBe("");
    expect(document.documentElement.hasAttribute("data-pq-sheet-open")).toBe(false);
  });

  it("a long drag down on the grabber dismisses", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const handle = screen.getByRole("dialog").querySelector("[data-sheet-handle]")!;
    touch(handle, "touchstart", 100);
    // Slow: 300px over 3s (0.1 px/ms) — distance, not velocity, decides.
    for (let i = 1; i <= 30; i++) {
      now += 100;
      touch(handle, "touchmove", 100 + i * 10);
    }
    touch(handle, "touchend", 400);
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 3000 });
  });

  it("a short slow drag snaps back; a short fast flick dismisses", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const handle = screen.getByRole("dialog").querySelector("[data-sheet-handle]")!;

    touch(handle, "touchstart", 100);
    for (let i = 1; i <= 4; i++) {
      now += 100;
      touch(handle, "touchmove", 100 + i * 10); // 40px, 0.1 px/ms
    }
    touch(handle, "touchend", 140);
    await new Promise((r) => setTimeout(r, 600));
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeTruthy();

    touch(handle, "touchstart", 100);
    for (let i = 1; i <= 4; i++) {
      now += 10;
      touch(handle, "touchmove", 100 + i * 10); // 40px in 40ms = 1 px/ms
    }
    touch(handle, "touchend", 140);
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 3000 });
  });

  it("dragging down from scrolled content scrolls instead of dragging", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const body = screen.getByRole("dialog").querySelector("[data-sheet-body]") as HTMLElement;
    body.scrollTop = 50;
    const field = screen.getByText("last-button");
    touch(field, "touchstart", 100);
    now += 10;
    const move = touch(field, "touchmove", 300);
    touch(field, "touchend", 300);
    expect(move.defaultPrevented).toBe(false);
    await new Promise((r) => setTimeout(r, 400));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("not dismissible → a long fast drag only rubber-bands", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} dismissible={false} />);
    const handle = screen.getByRole("dialog").querySelector("[data-sheet-handle]")!;
    touch(handle, "touchstart", 100);
    now += 10;
    touch(handle, "touchmove", 500);
    touch(handle, "touchend", 500);
    await new Promise((r) => setTimeout(r, 600));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("pushes a history entry; the back button closes the sheet", async () => {
    const onClose = vi.fn();
    const push = vi.spyOn(window.history, "pushState");
    render(<Harness onClose={onClose} />);
    await waitFor(() =>
      expect((window.history.state as { __pqOverlays?: string[] }).__pqOverlays?.length).toBe(1),
    );
    expect(push).toHaveBeenCalledTimes(1);
    // The marker rides on the existing state (Next's __NA tree is kept).
    expect((window.history.state as { page?: string }).page).toBe("base");

    act(() => window.history.back());
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 3000 });
    expect((window.history.state as { __pqOverlays?: string[] }).__pqOverlays).toBeUndefined();
  });

  it("closing in-app pops its own history entry (no stray entry left)", async () => {
    const ref = React.createRef<SheetHandle>();
    render(<Harness sheetRef={ref} />);
    await waitFor(() =>
      expect((window.history.state as { __pqOverlays?: string[] }).__pqOverlays?.length).toBe(1),
    );
    act(() => ref.current?.dismiss());
    await waitFor(
      () =>
        expect((window.history.state as { __pqOverlays?: string[] }).__pqOverlays).toBeUndefined(),
      { timeout: 3000 },
    );
    expect((window.history.state as { page?: string }).page).toBe("base");
  });

  it("Escape closes the topmost sheet only", async () => {
    const outer = vi.fn();
    const inner = vi.fn();
    function Nested() {
      const [a, setA] = React.useState(true);
      const [b, setB] = React.useState(true);
      return (
        <>
          <Sheet open={a} onClose={() => { outer(); setA(false); }} ariaLabel="outer">
            <button type="button">outer-btn</button>
          </Sheet>
          <Sheet open={b} onClose={() => { inner(); setB(false); }} ariaLabel="inner" zIndex={1100}>
            <button type="button">inner-btn</button>
          </Sheet>
        </>
      );
    }
    render(<Nested />);
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(inner).toHaveBeenCalledTimes(1), { timeout: 3000 });
    expect(outer).not.toHaveBeenCalled();
  });
});
