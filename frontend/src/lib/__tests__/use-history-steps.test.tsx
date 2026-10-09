/**
 * useHistorySteps — the system back gesture walks a phone step flow.
 *
 * Pinned:
 *   - each step forward pushes ONE same-URL entry; back pops to the previous
 *     step through onPopTo; back from the first step is left to the router;
 *   - an in-app back (이전) returns to that step's own entry (history.go),
 *     so the stack never holds a step twice;
 *   - a refused pop (e.g. system forward into an unanswered step) is undone;
 *   - locking the flow (submitted) collapses back to the page's own entry;
 *   - overlay entries (lib/use-back-dismiss `__pqOverlays`) are not steps;
 *   - disabled (desktop) pushes nothing.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, render } from "@testing-library/react";
import { useEffect, useState } from "react";
import { STEP_STATE_KEY, useHistorySteps } from "@/lib/use-history-steps";

type Api = {
  setStep: (n: number) => void;
  setLocked: (b: boolean) => void;
  step: () => number;
};

function Harness({
  api,
  enabled = true,
  allow = () => true,
  onAdvance,
}: {
  api: Partial<Api>;
  enabled?: boolean;
  allow?: (target: number, from: number) => boolean;
  onAdvance?: () => void;
}) {
  const [step, setStep] = useState(0);
  const [locked, setLocked] = useState(false);
  useEffect(() => {
    Object.assign(api, { setStep, setLocked, step: () => step });
  }, [api, step]);
  useHistorySteps({
    key: "test-flow",
    enabled,
    step,
    locked,
    onPopTo: (target) => {
      if (!allow(target, step)) return false;
      setStep(target);
      return true;
    },
    onAdvance,
  });
  return <div data-testid="step">{step}</div>;
}

/** jsdom fires popstate for history.go/back asynchronously. */
async function settle() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 30));
  });
}

let startLength = 0;
beforeEach(() => {
  window.history.replaceState({ __NA: true }, "", "/flow");
  startLength = window.history.length;
});
afterEach(() => cleanup());

function marker() {
  return (window.history.state as Record<string, { idx: number; step: number }> | null)?.[
    STEP_STATE_KEY
  ];
}

describe("useHistorySteps", () => {
  it("pushes one entry per step forward and back returns to the previous step", async () => {
    const api: Partial<Api> = {};
    const onAdvance = vi.fn();
    const { getByTestId } = render(<Harness api={api} onAdvance={onAdvance} />);
    expect(marker()).toMatchObject({ idx: 0, step: 0 });
    // The page's own entry keeps Next.js's marker.
    expect((window.history.state as { __NA?: boolean }).__NA).toBe(true);

    act(() => api.setStep!(1));
    act(() => api.setStep!(2));
    expect(window.history.length).toBe(startLength + 2);
    expect(marker()).toMatchObject({ idx: 2, step: 2 });
    expect(onAdvance).toHaveBeenCalledTimes(2);

    act(() => window.history.back());
    await settle();
    expect(getByTestId("step").textContent).toBe("1");
    act(() => window.history.back());
    await settle();
    expect(getByTestId("step").textContent).toBe("0");
    // No step was "advanced" by the pops.
    expect(onAdvance).toHaveBeenCalledTimes(2);
  });

  it("an in-app back returns to that step's own entry instead of stacking one", async () => {
    const api: Partial<Api> = {};
    render(<Harness api={api} />);
    act(() => api.setStep!(1));
    act(() => api.setStep!(2));
    act(() => api.setStep!(1)); // 이전
    await settle();
    expect(marker()).toMatchObject({ idx: 1, step: 1 });
    act(() => api.setStep!(2)); // forward again replaces the old step-2 entry
    expect(marker()).toMatchObject({ idx: 2, step: 2 });
    // Back walks 2 → 1 → 0 with no duplicate step in between.
    act(() => window.history.back());
    await settle();
    expect(api.step!()).toBe(1);
    act(() => window.history.back());
    await settle();
    expect(api.step!()).toBe(0);
    expect(marker()).toMatchObject({ idx: 0 });
  });

  it("a refused pop is undone and the shown step stays", async () => {
    const api: Partial<Api> = {};
    // Forward moves are refused (the next step is not answered any more).
    const allow = (target: number, from: number) => target < from;
    const { getByTestId } = render(<Harness api={api} allow={allow} />);
    act(() => api.setStep!(1));
    act(() => window.history.back());
    await settle();
    expect(getByTestId("step").textContent).toBe("0");
    act(() => window.history.forward());
    await settle(); // refused → the hook goes back again
    await settle();
    expect(getByTestId("step").textContent).toBe("0");
    expect(marker()).toMatchObject({ idx: 0 });
  });

  it("locking the flow collapses history to the page's own entry", async () => {
    const api: Partial<Api> = {};
    const { getByTestId } = render(<Harness api={api} />);
    act(() => api.setStep!(1));
    act(() => api.setStep!(2));
    act(() => api.setLocked!(true));
    await settle();
    expect(marker()).toMatchObject({ idx: 0 });
    // The result screen stays; nothing was re-entered.
    expect(getByTestId("step").textContent).toBe("2");
  });

  it("ignores overlay entries (useBackDismiss) on top of a step", async () => {
    const api: Partial<Api> = {};
    const { getByTestId } = render(<Harness api={api} />);
    act(() => api.setStep!(1));
    // A sheet opens: it copies the current state and adds its overlay id.
    act(() => {
      window.history.pushState({ ...window.history.state, __pqOverlays: ["o1"] }, "");
    });
    act(() => window.history.back()); // closes the sheet
    await settle();
    expect(getByTestId("step").textContent).toBe("1");
  });

  it("does nothing while disabled (desktop)", () => {
    const api: Partial<Api> = {};
    render(<Harness api={api} enabled={false} />);
    act(() => api.setStep!(1));
    expect(window.history.length).toBe(startLength);
    expect(marker()).toBeUndefined();
  });
});
