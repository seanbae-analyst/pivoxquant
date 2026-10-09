"use client";

/**
 * <Sheet /> — one modal primitive, two presentations.
 * --------------------------------------------------------------------------
 * Phone (<768px, incl. the installed PWA): a native-quality bottom sheet.
 *   - Slides up from the bottom (spring built on lib/motion.ts duration
 *     tokens; prefers-reduced-motion → no travel, a short fade).
 *   - Rounded top corners + grabber. Backdrop dims with the sheet's travel.
 *   - Drag down to dismiss (distance OR velocity threshold, see
 *     `shouldDismissSheet`). Dragging up rubber-bands. Dragging from the
 *     content only takes over when that content is scrolled to the top, so
 *     scrolling a long form never fights the gesture.
 *   - max-height 92dvh, the body scrolls inside (overscroll-behavior:
 *     contain — no scroll chaining into the page), safe-area bottom padding.
 *   - <SheetFooter /> pins the actions above the home indicator.
 *   - Keyboard-aware: follows `visualViewport`, so the iOS keyboard lifts the
 *     sheet instead of covering the focused field, and the focused field is
 *     scrolled clear of the pinned footer.
 *   - Android back / browser back closes it (lib/use-back-dismiss).
 *   - Body scroll lock without a jump (position:fixed + restored scrollY).
 *   - Touch pointers (pointer: coarse) do NOT get an input autofocused —
 *     the keyboard should not pop up before the user asks for it.
 *
 * Desktop (md+): renders the caller's existing overlay + panel markup
 * (`desktopOverlay*` / `desktopPanel*`) unchanged — same classes, same inline
 * styles, same backdrop behavior.
 *
 * Both: role=dialog + aria-modal, focus trap (only the topmost sheet traps),
 * Escape (topmost only), focus returns to the trigger on close.
 *
 * Usage — always render it and pass `open`, so the exit animation can run:
 *
 *     <Sheet open={open} onClose={onClose} ariaLabelledBy="x-title" ...>
 *       ...content...
 *       <SheetFooter desktopStyle={...}>buttons</SheetFooter>
 *     </Sheet>
 *
 * Programmatic close with the exit animation: `sheetRef.current?.dismiss()`.
 */

import * as React from "react";
import { createPortal } from "react-dom";
import {
  AnimatePresence,
  animate,
  motion,
  useMotionValue,
  usePresence,
  useReducedMotion,
  useTransform,
} from "motion/react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useIsPhone } from "@/lib/use-phone";
import { useBackDismiss } from "@/lib/use-back-dismiss";
import { PQ_DUR_BASE, PQ_DUR_FAST, PQ_DUR_MICRO, PQ_EASE } from "@/lib/motion";

// ─── Gesture math (pure — unit tested) ──────────────────────────────────────

/** Fraction of the sheet's height a slow drag must cover to dismiss. */
export const SHEET_DISMISS_DISTANCE_RATIO = 0.3;
/** Clamp for that distance (px) — short sheets need some travel, tall ones not 300px. */
export const SHEET_DISMISS_DISTANCE_MIN = 64;
export const SHEET_DISMISS_DISTANCE_MAX = 200;
/** Downward fling speed (px/ms, 0.5 = 500 px/s) that dismisses regardless of distance. */
export const SHEET_DISMISS_VELOCITY = 0.5;
/** Rubber-band asymptote (px) for dragging past a bound. */
export const SHEET_RUBBER_BAND_LIMIT = 64;

export function sheetDismissDistance(height: number): number {
  return Math.min(
    SHEET_DISMISS_DISTANCE_MAX,
    Math.max(SHEET_DISMISS_DISTANCE_MIN, height * SHEET_DISMISS_DISTANCE_RATIO),
  );
}

/** Release decision for a drag: offset (px, + is down), velocity (px/ms, + is down). */
export function shouldDismissSheet({
  offset,
  velocity,
  height,
}: {
  offset: number;
  velocity: number;
  height: number;
}): boolean {
  if (offset <= 0) return false;
  if (velocity >= SHEET_DISMISS_VELOCITY) return true;
  // Flicking back up cancels a long drag — the user changed their mind.
  if (velocity <= -SHEET_DISMISS_VELOCITY * 0.4) return false;
  return offset >= sheetDismissDistance(height);
}

/** iOS-style resistance: grows with x but never past `limit`. Sign preserved. */
export function rubberBand(x: number, limit = SHEET_RUBBER_BAND_LIMIT): number {
  if (x === 0) return 0;
  const d = Math.abs(x);
  const out = (1 - 1 / ((d * 0.55) / limit + 1)) * limit;
  return Math.sign(x) * out;
}

/** Visual offset for a raw finger offset: free downward (if dismissible), rubber-band otherwise. */
export function sheetDragOffset(raw: number, dismissible: boolean): number {
  if (raw >= 0) return dismissible ? raw : rubberBand(raw);
  return rubberBand(raw);
}

export interface DragSample {
  t: number;
  y: number;
}

/** Release velocity (px/ms) over the last `windowMs` of samples. */
export function computeVelocity(samples: DragSample[], windowMs = 100): number {
  if (samples.length < 2) return 0;
  const last = samples[samples.length - 1];
  let first = samples[samples.length - 2];
  for (let i = samples.length - 2; i >= 0; i--) {
    if (last.t - samples[i].t > windowMs) break;
    first = samples[i];
  }
  const dt = last.t - first.t;
  if (dt <= 0) return 0;
  return (last.y - first.y) / dt;
}

/**
 * Clock for drag velocity samples. performance.now() rather than
 * event.timeStamp: synthesized touch streams (and some WebViews) stamp every
 * event with the same time. Overridable in tests without freezing motion's
 * own frame loop.
 */
export const sheetClock = { now: () => performance.now() };

// ─── Shared module state (stack, scroll lock) ──────────────────────────────

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/** Open sheets, bottom → top. Only the top one traps focus / takes Escape. */
const openStack: string[] = [];
let sheetSeq = 0;

function isTop(id: string) {
  return openStack[openStack.length - 1] === id;
}

let lockCount = 0;
let lockSaved: { y: number; style: string } | null = null;

/** Phone body lock: position:fixed keeps iOS from scrolling the page under the sheet. */
function lockBody() {
  if (typeof document === "undefined") return;
  lockCount += 1;
  if (lockCount > 1) return;
  const body = document.body;
  const y = window.scrollY || 0;
  lockSaved = { y, style: body.getAttribute("style") ?? "" };
  body.style.position = "fixed";
  body.style.top = `-${y}px`;
  body.style.left = "0";
  body.style.right = "0";
  body.style.width = "100%";
  body.style.overflow = "hidden";
  document.documentElement.setAttribute("data-pq-sheet-open", "");
}

function unlockBody() {
  if (typeof document === "undefined" || lockCount === 0) return;
  lockCount -= 1;
  if (lockCount > 0) return;
  const saved = lockSaved;
  lockSaved = null;
  document.documentElement.removeAttribute("data-pq-sheet-open");
  if (!saved) return;
  if (saved.style) document.body.setAttribute("style", saved.style);
  else document.body.removeAttribute("style");
  if (saved.y) window.scrollTo({ top: saved.y, left: 0, behavior: "instant" as ScrollBehavior });
}

/** Desktop lock — the plain overflow:hidden the old ModalShell used. */
function useDesktopOverflowLock(active: boolean) {
  React.useEffect(() => {
    if (!active) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [active]);
}

function prefersFinePointer(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
  // A device with no fine pointer at all is a touch device.
  const mq = window.matchMedia("(pointer: fine)");
  return mq ? mq.matches : true;
}

function isTextEntry(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag === "INPUT") {
    const type = (el as HTMLInputElement).type;
    return !["button", "submit", "reset", "checkbox", "radio"].includes(type);
  }
  return (el as HTMLElement).isContentEditable === true;
}

/** Focus trap + Escape + initial focus + restore, scoped to the topmost sheet. */
function useSheetA11y({
  id,
  active,
  containerRef,
  onEscape,
  phone,
}: {
  id: string;
  active: boolean;
  containerRef: React.RefObject<HTMLElement | null>;
  onEscape: () => void;
  phone: boolean;
}) {
  const onEscapeRef = React.useRef(onEscape);
  React.useEffect(() => {
    onEscapeRef.current = onEscape;
  });

  React.useEffect(() => {
    if (!active) return;
    openStack.push(id);
    const trigger = document.activeElement as HTMLElement | null;

    const raf = requestAnimationFrame(() => {
      const node = containerRef.current;
      if (!node) return;
      const focusables = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      // Touch: never autofocus a text field (the keyboard would jump up).
      let target: HTMLElement | undefined = focusables[0];
      if (phone || !prefersFinePointer()) {
        target = prefersFinePointer() ? focusables.find((el) => !isTextEntry(el)) : undefined;
      }
      if (!target) {
        if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "-1");
        target = node;
      }
      target.focus({ preventScroll: true });
    });

    const onKeyDown = (e: KeyboardEvent) => {
      if (!isTop(id)) return;
      if (e.key === "Escape") {
        e.stopPropagation();
        onEscapeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const node = containerRef.current;
      if (!node) return;
      const focusables = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
        (el) => !el.hasAttribute("data-focus-skip"),
      );
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const current = document.activeElement as HTMLElement | null;
      const inside = !!current && node.contains(current);
      if (e.shiftKey) {
        if (!inside || current === first) {
          e.preventDefault();
          last.focus({ preventScroll: true });
        }
      } else if (!inside || current === last) {
        e.preventDefault();
        first.focus({ preventScroll: true });
      }
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("keydown", onKeyDown);
      const idx = openStack.lastIndexOf(id);
      if (idx !== -1) openStack.splice(idx, 1);
      if (trigger && typeof trigger.focus === "function" && document.contains(trigger)) {
        setTimeout(() => trigger.focus({ preventScroll: true }), 0);
      }
    };
    // containerRef is a stable ref object; phone is fixed for one open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, id]);
}

/** Keyboard / visual viewport: how far the visible area's bottom sits above the layout bottom. */
function useVisualViewportInset(active: boolean) {
  const [vv, setVv] = React.useState<{ inset: number; height: number } | null>(null);
  React.useEffect(() => {
    if (!active || typeof window === "undefined" || !window.visualViewport) return;
    const v = window.visualViewport;
    const update = () => {
      const inset = Math.max(0, Math.round(window.innerHeight - v.height - v.offsetTop));
      setVv(inset > 0 ? { inset, height: v.height } : null);
    };
    update();
    v.addEventListener("resize", update);
    v.addEventListener("scroll", update);
    return () => {
      v.removeEventListener("resize", update);
      v.removeEventListener("scroll", update);
    };
  }, [active]);
  return vv;
}

// ─── Context ───────────────────────────────────────────────────────────────

interface SheetContextValue {
  /** True when rendered as the phone bottom sheet. */
  phone: boolean;
  /** Close with the exit animation (desktop: immediate onClose). */
  dismiss: () => void;
  registerFooter: (on: boolean) => void;
}

const SheetContext = React.createContext<SheetContextValue | null>(null);

/** Inside a <Sheet>: whether it is the phone sheet, and an animated dismiss. */
export function useSheet(): SheetContextValue {
  return (
    React.useContext(SheetContext) ?? {
      phone: false,
      dismiss: () => {},
      registerFooter: () => {},
    }
  );
}

// ─── Public component ──────────────────────────────────────────────────────

export interface SheetHandle {
  /** Close with the exit animation, then call onClose (desktop: onClose now). */
  dismiss: () => void;
}

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  /**
   * false → no drag / backdrop / Escape / back dismissal (busy, mid-cycle).
   * Back presses are swallowed while false. Default true.
   */
  dismissible?: boolean;
  /** Backdrop tap/click closes (both presentations). Default true. */
  closeOnBackdrop?: boolean;
  /** Phone: push a history entry so Android/browser back closes. Default true. */
  closeOnBack?: boolean;
  /** Phone: show a close (X) button in the sheet header. Default false. */
  showClose?: boolean;
  /** Phone: accessible label for that button. */
  closeLabel?: string;
  /** Phone: z-index of the sheet layer. Default 1000. */
  zIndex?: number;
  /** Phone: extra classes on the scrolling body (padding etc.). */
  phoneBodyClassName?: string;
  /** Phone: fill to max height (e.g. a list sheet) instead of hugging content. */
  phoneFullHeight?: boolean;
  /** data-testid on the dialog element (both presentations). */
  testId?: string;

  // Desktop (md+) — the caller's existing markup, reproduced exactly.
  desktopOverlayClassName?: string;
  desktopOverlayStyle?: React.CSSProperties;
  desktopPanelClassName?: string;
  desktopPanelStyle?: React.CSSProperties;
  /** Which backdrop event closes on desktop (ModalShell used mousedown). */
  desktopBackdropEvent?: "click" | "mousedown";
  /** Desktop: lock body overflow while open (the old ModalShell did). */
  desktopScrollLock?: boolean;

  ref?: React.Ref<SheetHandle>;
}

export function Sheet(props: SheetProps) {
  const { open, onClose, ref } = props;
  const isPhoneNow = useIsPhone();
  const isClient = React.useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );

  // The presentation is fixed for one open — rotating a phone mid-form must
  // not remount the content (and drop what was typed).
  const [locked, setLocked] = React.useState<boolean | null>(null);
  if (open && locked === null) setLocked(isPhoneNow);
  if (!open && locked !== null) setLocked(null);
  const phone = open ? (locked ?? isPhoneNow) : isPhoneNow;

  const phoneDismissRef = React.useRef<(() => void) | null>(null);
  const dismiss = React.useCallback(() => {
    if (phone && phoneDismissRef.current) phoneDismissRef.current();
    else onClose();
  }, [phone, onClose]);
  React.useImperativeHandle(ref, () => ({ dismiss }), [dismiss]);

  if (!isClient) return null;

  return createPortal(
    phone ? (
      <AnimatePresence>
        {open && (
          <PhoneSheet key="pq-sheet" {...props} dismissRef={phoneDismissRef} />
        )}
      </AnimatePresence>
    ) : open ? (
      <DesktopModal {...props} dismiss={dismiss} />
    ) : null,
    document.body,
  );
}

function noopSubscribe() {
  return () => {};
}

// ─── Desktop presentation ──────────────────────────────────────────────────

function DesktopModal({
  onClose,
  children,
  ariaLabel,
  ariaLabelledBy,
  dismissible = true,
  closeOnBackdrop = true,
  testId,
  desktopOverlayClassName,
  desktopOverlayStyle,
  desktopPanelClassName,
  desktopPanelStyle,
  desktopBackdropEvent = "click",
  desktopScrollLock = false,
  dismiss,
}: SheetProps & { dismiss: () => void }) {
  const [id] = React.useState(() => `sheet${++sheetSeq}`);
  const panelRef = React.useRef<HTMLDivElement | null>(null);
  useDesktopOverflowLock(desktopScrollLock);
  useSheetA11y({
    id,
    active: true,
    containerRef: panelRef,
    onEscape: () => {
      if (dismissible) onClose();
    },
    phone: false,
  });

  const ctx = React.useMemo<SheetContextValue>(
    () => ({ phone: false, dismiss, registerFooter: () => {} }),
    [dismiss],
  );

  const backdrop = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!closeOnBackdrop || !dismissible) return;
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <SheetContext.Provider value={ctx}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabelledBy ? undefined : ariaLabel}
        aria-labelledby={ariaLabelledBy}
        data-testid={testId}
        data-sheet-presentation="desktop"
        className={desktopOverlayClassName}
        style={desktopOverlayStyle}
        onClick={desktopBackdropEvent === "click" ? backdrop : undefined}
        onMouseDown={desktopBackdropEvent === "mousedown" ? backdrop : undefined}
      >
        <div ref={panelRef} className={desktopPanelClassName} style={desktopPanelStyle}>
          {children}
        </div>
      </div>
    </SheetContext.Provider>
  );
}

// ─── Phone presentation ────────────────────────────────────────────────────

/** Elevated surface on Vantablack — same mix the top-bar popovers use. */
const SHEET_SURFACE = "color-mix(in srgb, var(--pq-ivory) 4%, var(--pq-ink))";

const ENTER = { type: "spring" as const, visualDuration: PQ_DUR_BASE + PQ_DUR_MICRO, bounce: 0 };
const SETTLE = { type: "spring" as const, visualDuration: PQ_DUR_BASE, bounce: 0 };
const EXIT = { type: "spring" as const, visualDuration: PQ_DUR_BASE, bounce: 0 };
const FADE = { duration: PQ_DUR_FAST, ease: PQ_EASE };

function PhoneSheet({
  onClose,
  children,
  ariaLabel,
  ariaLabelledBy,
  dismissible = true,
  closeOnBackdrop = true,
  closeOnBack = true,
  showClose = false,
  closeLabel = "닫기",
  zIndex = 1000,
  phoneBodyClassName,
  phoneFullHeight = false,
  testId,
  dismissRef,
}: SheetProps & { dismissRef: React.MutableRefObject<(() => void) | null> }) {
  const [id] = React.useState(() => `sheet${++sheetSeq}`);
  const reduced = useReducedMotion() ?? false;
  const [isPresent, safeToRemove] = usePresence();
  const panelRef = React.useRef<HTMLDivElement | null>(null);
  const bodyRef = React.useRef<HTMLDivElement | null>(null);
  const closingRef = React.useRef(false);
  const [closing, setClosing] = React.useState(false);
  const [hasFooter, setHasFooter] = React.useState(false);
  const dismissibleRef = React.useRef(dismissible);
  const onCloseRef = React.useRef(onClose);
  React.useEffect(() => {
    dismissibleRef.current = dismissible;
    onCloseRef.current = onClose;
  });

  const startY = typeof window !== "undefined" ? window.innerHeight : 1000;
  const y = useMotionValue(reduced ? 0 : startY);
  const height = useMotionValue(startY);
  const fade = useMotionValue(reduced ? 0 : 1);
  const backdropOpacity = useTransform(
    () => clamp01(1 - y.get() / Math.max(1, height.get())) * fade.get(),
  );

  // ── Close paths ──
  const requestClose = React.useCallback(
    (velocity = 0) => {
      if (closingRef.current) return;
      closingRef.current = true;
      setClosing(true);
      const done = () => onCloseRef.current();
      if (reduced) {
        animate(fade, 0, FADE).then(done);
        return;
      }
      animate(y, Math.max(height.get(), 1), { ...EXIT, velocity: velocity * 1000 }).then(done);
    },
    [reduced, y, height, fade],
  );
  React.useEffect(() => {
    dismissRef.current = () => requestClose(0);
    return () => {
      dismissRef.current = null;
    };
  }, [dismissRef, requestClose]);

  // Parent flipped open=false (or a dismiss already ran): finish the exit.
  React.useEffect(() => {
    if (isPresent) return;
    closingRef.current = true;
    const ctrl = reduced
      ? animate(fade, 0, FADE)
      : animate(y, Math.max(height.get(), 1), EXIT);
    ctrl.then(() => safeToRemove?.());
    return () => ctrl.stop();
  }, [isPresent, reduced, y, height, fade, safeToRemove]);

  // ── Enter + measure ──
  React.useLayoutEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const measure = () => height.set(panel.offsetHeight || window.innerHeight);
    measure();
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(measure);
      ro.observe(panel);
    }
    const ctrl = reduced ? animate(fade, 1, FADE) : animate(y, 0, ENTER);
    return () => {
      ro?.disconnect();
      ctrl.stop();
    };
    // mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Body lock, back button, a11y ──
  React.useEffect(() => {
    lockBody();
    return () => unlockBody();
  }, []);
  useBackDismiss(isPresent, () => requestClose(0), {
    enabled: closeOnBack,
    blocked: !dismissible,
  });
  useSheetA11y({
    id,
    active: true,
    containerRef: panelRef,
    onEscape: () => {
      if (dismissibleRef.current) requestClose(0);
    },
    phone: true,
  });

  // ── Keyboard awareness ──
  const vv = useVisualViewportInset(true);
  const keyboardOpen = !!vv && vv.inset > 120;
  React.useEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    const reveal = () => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || !body.contains(el) || !isTextEntry(el)) return;
      const bodyRect = body.getBoundingClientRect();
      const r = el.getBoundingClientRect();
      const footer = body.querySelector<HTMLElement>("[data-sheet-footer]");
      const bottomLimit = bodyRect.bottom - (footer?.offsetHeight ?? 0) - 12;
      if (r.bottom > bottomLimit) body.scrollTop += r.bottom - bottomLimit;
      else if (r.top < bodyRect.top + 12) body.scrollTop -= bodyRect.top + 12 - r.top;
    };
    reveal();
    const onFocusIn = () => {
      // Once now, once after the keyboard has finished sliding in.
      requestAnimationFrame(reveal);
      setTimeout(reveal, 320);
    };
    body.addEventListener("focusin", onFocusIn);
    return () => body.removeEventListener("focusin", onFocusIn);
  }, [vv?.inset, vv?.height]);

  // ── Drag gesture (touch + mouse on the grabber) ──
  React.useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const st = {
      tracking: false,
      engaged: false,
      fromHandle: false,
      target: null as Element | null,
      startX: 0,
      startY: 0,
      baseY: 0,
      origin: 0,
      samples: [] as DragSample[],
      lastY: 0,
    };

    const begin = (x: number, cy: number, target: Element | null) => {
      if (closingRef.current || !target) return false;
      if (isTextEntry(target) || target.closest("[data-sheet-no-drag]")) return false;
      st.tracking = true;
      st.engaged = false;
      st.fromHandle = !bodyRef.current?.contains(target);
      st.target = target;
      st.startX = x;
      st.startY = cy;
      st.samples = [];
      return true;
    };

    /** Returns true when the sheet took the gesture (caller cancels the native scroll). */
    const move = (x: number, cy: number, t: number): boolean => {
      if (!st.tracking) return false;
      const dx = x - st.startX;
      const dy = cy - st.startY;
      if (!st.engaged) {
        if (dx === 0 && dy === 0) return false;
        if (Math.abs(dx) > Math.abs(dy)) {
          st.tracking = false;
          return false;
        }
        if (!st.fromHandle) {
          // From the content: only a downward pull on content already at its top.
          if (dy <= 0 || scrolledWithin(st.target, bodyRef.current)) {
            st.tracking = false;
            return false;
          }
        }
        st.engaged = true;
        st.baseY = cy;
        st.origin = y.get();
        y.stop();
      }
      st.lastY = cy;
      const raw = st.origin + (cy - st.baseY);
      y.set(sheetDragOffset(raw, dismissibleRef.current));
      st.samples.push({ t, y: cy });
      if (st.samples.length > 12) st.samples.shift();
      return true;
    };

    const end = () => {
      if (!st.tracking) return;
      st.tracking = false;
      if (!st.engaged) return;
      st.engaged = false;
      const velocity = computeVelocity(st.samples);
      // Decide on the finger's travel, not the sheet's position: grabbing a
      // sheet that is still rising and letting go should finish presenting it.
      const offset = st.lastY - st.baseY;
      if (
        dismissibleRef.current &&
        shouldDismissSheet({ offset, velocity, height: height.get() })
      ) {
        requestClose(velocity);
      } else if (reduced) {
        y.set(0);
      } else {
        animate(y, 0, { ...SETTLE, velocity: velocity * 1000 });
      }
    };

    const onTouchStart = (e: TouchEvent) => {
      e.stopPropagation(); // keep page-level pull-to-refresh out of it
      if (e.touches.length !== 1) {
        st.tracking = false;
        return;
      }
      const t = e.touches[0];
      begin(t.clientX, t.clientY, e.target as Element);
    };
    const onTouchMove = (e: TouchEvent) => {
      e.stopPropagation();
      const t = e.touches[0];
      if (t && move(t.clientX, t.clientY, sheetClock.now()) && e.cancelable) e.preventDefault();
    };
    const onTouchEnd = (e: TouchEvent) => {
      e.stopPropagation();
      end();
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.pointerType === "touch" || e.button !== 0) return;
      const target = e.target as Element;
      // Mouse / pen: the grabber + header only (dragging text would select it).
      if (bodyRef.current?.contains(target)) return;
      if (target.closest("button, a")) return;
      if (!begin(e.clientX, e.clientY, target)) return;
      const onMove = (ev: PointerEvent) => {
        if (move(ev.clientX, ev.clientY, sheetClock.now())) ev.preventDefault();
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onUp);
        end();
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    };

    panel.addEventListener("touchstart", onTouchStart, { passive: true });
    panel.addEventListener("touchmove", onTouchMove, { passive: false });
    panel.addEventListener("touchend", onTouchEnd);
    panel.addEventListener("touchcancel", onTouchEnd);
    panel.addEventListener("pointerdown", onPointerDown);
    return () => {
      panel.removeEventListener("touchstart", onTouchStart);
      panel.removeEventListener("touchmove", onTouchMove);
      panel.removeEventListener("touchend", onTouchEnd);
      panel.removeEventListener("touchcancel", onTouchEnd);
      panel.removeEventListener("pointerdown", onPointerDown);
    };
  }, [y, height, reduced, requestClose]);

  const ctx = React.useMemo<SheetContextValue>(
    () => ({ phone: true, dismiss: () => requestClose(0), registerFooter: setHasFooter }),
    [requestClose],
  );

  const sheetMaxHeight = vv ? Math.max(200, vv.height - 8) : "92dvh";

  return (
    <SheetContext.Provider value={ctx}>
      <div
        className="fixed inset-0"
        style={{ zIndex }}
        data-pq-sheet-layer=""
        // Synthetic events from a portal still bubble through the React tree
        // (e.g. into a swipe pager on the page). Stop them at the sheet.
        onPointerDown={stopReact}
        onPointerMove={stopReact}
        onPointerUp={stopReact}
        onTouchStart={stopReact}
        onTouchMove={stopReact}
        onTouchEnd={stopReact}
      >
        <motion.div
          aria-hidden="true"
          data-testid={testId ? `${testId}-backdrop` : "sheet-backdrop"}
          className="absolute inset-0 touch-none bg-[rgba(var(--pq-ink-rgb),0.72)]"
          style={{ opacity: backdropOpacity }}
          onClick={() => {
            if (closeOnBackdrop && dismissibleRef.current) requestClose(0);
          }}
        />
        <motion.div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label={ariaLabelledBy ? undefined : ariaLabel}
          aria-labelledby={ariaLabelledBy}
          data-testid={testId}
          data-sheet-presentation="phone"
          data-keyboard={keyboardOpen ? "open" : undefined}
          tabIndex={-1}
          className={cn(
            "group/sheet absolute inset-x-0 mx-auto flex w-full max-w-[640px] flex-col overflow-hidden",
            "rounded-t-[12px] border-t border-[rgba(var(--pq-ivory-rgb),0.12)] text-[var(--pq-ivory)]",
            "shadow-[0_-12px_40px_rgba(0,0,0,0.55)] outline-none",
          )}
          style={{
            y,
            opacity: reduced ? fade : undefined,
            background: SHEET_SURFACE,
            bottom: vv ? vv.inset : 0,
            maxHeight: sheetMaxHeight,
            height: phoneFullHeight ? sheetMaxHeight : undefined,
            pointerEvents: closing ? "none" : undefined,
          }}
        >
          {/* Grabber (+ optional close). touch-none: always a drag surface. */}
          <div
            data-sheet-handle=""
            className={cn(
              "relative flex shrink-0 touch-none select-none justify-center",
              showClose ? "h-11 items-start pt-2" : "h-6 items-start pt-2",
            )}
          >
            <span
              aria-hidden="true"
              className="block h-[5px] w-9 rounded-full bg-[rgba(var(--pq-ivory-rgb),0.28)]"
            />
            {showClose && (
              <button
                type="button"
                onClick={() => requestClose(0)}
                aria-label={closeLabel}
                data-testid="sheet-close"
                className="absolute right-1 top-0 flex h-11 w-11 items-center justify-center rounded-sm text-[var(--pq-ivory-dim)] transition-colors active:bg-[var(--pq-ivory-line)]"
              >
                <X className="h-[18px] w-[18px]" strokeWidth={1.5} aria-hidden="true" />
              </button>
            )}
          </div>
          <div
            ref={bodyRef}
            data-sheet-body=""
            className={cn(
              "min-h-0 flex-1 overflow-y-auto overscroll-contain px-5",
              !hasFooter && "pb-[max(20px,env(safe-area-inset-bottom))] group-data-[keyboard=open]/sheet:pb-4",
              phoneBodyClassName,
            )}
          >
            {children}
          </div>
        </motion.div>
      </div>
    </SheetContext.Provider>
  );
}

function stopReact(e: React.SyntheticEvent) {
  e.stopPropagation();
}

function clamp01(v: number) {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

/** True when the touch started inside something (up to the sheet body) that is scrolled down. */
function scrolledWithin(target: Element | null, body: HTMLElement | null): boolean {
  let el: Element | null = target;
  while (el) {
    if (el instanceof HTMLElement && el.scrollTop > 0) return true;
    if (el === body) break;
    el = el.parentElement;
  }
  return false;
}

// ─── Footer ────────────────────────────────────────────────────────────────

/**
 * Action row. Desktop: exactly the caller's div (desktopStyle/ClassName).
 * Phone: pinned to the bottom of the sheet's scroll area, above the home
 * indicator, on the sheet surface with a hairline — the primary action is
 * always reachable however long the form is. Keep it inside the <form> so a
 * type=submit button still submits.
 */
export function SheetFooter({
  children,
  desktopStyle,
  desktopClassName,
  phoneClassName,
}: {
  children: React.ReactNode;
  desktopStyle?: React.CSSProperties;
  desktopClassName?: string;
  phoneClassName?: string;
}) {
  const { phone, registerFooter } = useSheet();
  React.useLayoutEffect(() => {
    if (!phone) return;
    registerFooter(true);
    return () => registerFooter(false);
  }, [phone, registerFooter]);

  if (!phone) {
    return (
      <div className={desktopClassName} style={desktopStyle}>
        {children}
      </div>
    );
  }
  // Keep the caller's layout (flex / gap / justify), drop its spacing chrome.
  const layout: React.CSSProperties = { ...desktopStyle };
  for (const k of [
    "margin",
    "marginTop",
    "marginBottom",
    "padding",
    "paddingTop",
    "paddingBottom",
    "borderTop",
    "border",
  ] as const) {
    delete layout[k];
  }
  return (
    <div
      data-sheet-footer=""
      className={cn(
        // Caller's layout first; the sheet's own spacing wins over it.
        desktopClassName,
        "sticky bottom-0 z-[1] -mx-5 mt-5 border-t border-[var(--pq-ivory-line)] px-5 pt-3",
        "pb-[max(14px,env(safe-area-inset-bottom))] group-data-[keyboard=open]/sheet:pb-3",
        phoneClassName,
      )}
      style={{ ...layout, background: SHEET_SURFACE }}
    >
      {children}
    </div>
  );
}

/** ModalShell's overlay classes — for callers moving from ModalShell to Sheet. */
export const MODAL_SHELL_OVERLAY_CLASS =
  "fixed inset-0 z-[60] flex items-end justify-center overflow-y-auto bg-black/40 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:items-center sm:p-4";
