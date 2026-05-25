"use client";

import { useState, useEffect, useRef } from "react";
import { X, Download, Share } from "lucide-react";

// Chromium ships BeforeInstallPromptEvent; TS lib.dom doesn't type it yet.
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISS_KEY = "pq-install-dismissed";
// Re-prompt after one week so dismissal isn't permanent but also isn't naggy.
const DISMISS_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
// Delay appearance so the prompt arrives after the user has seen value,
// not the second the page loads.
const APPEAR_DELAY_MS = 8000;

// 2026-05-17 wave 11 PWA P2 (PR #430): iOS Safari never fires
// beforeinstallprompt, so the Chromium-only flow above silently leaves
// iPhone users with no install guidance. Detect Safari on iPhone/iPad
// (incl. iPadOS desktop UA quirk) and render a static "Share → Add to
// Home Screen" card instead of the Chromium installer button.
function isIosSafariBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  // iPhone / iPod = explicit iOS UA. iPad on iPadOS 13+ reports a Mac
  // UA but exposes `maxTouchPoints > 1`; the Safari token still
  // appears. Exclude Chrome/Firefox/Edge on iOS (they all route
  // through WebKit but expose CriOS/FxiOS/EdgiOS tokens) since they
  // share the same A2HS limitation but have a different in-browser
  // share affordance.
  const isIosDevice =
    /iPhone|iPod/.test(ua) ||
    (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  if (!isIosDevice) return false;
  return /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);
  // Branch state — drives which body copy + CTA renders.
  const [variant, setVariant] = useState<"chromium" | "ios" | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Register the PWA service worker in production only (dev HMR conflicts).
    if (
      typeof window !== "undefined" &&
      "serviceWorker" in navigator &&
      process.env.NODE_ENV === "production"
    ) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .catch((err) => console.warn("[PWA] SW register failed:", err));

      // Auto-reload once when a NEW service worker takes control, so a fresh
      // deploy's JS bundle loads without a manual hard-refresh. The SW already
      // calls skipWaiting() + clients.claim(), but an already-open page keeps
      // running the OLD bundle until it reloads — which is why shipped fixes
      // appeared "not deployed" until a manual Cmd+Shift+R (CEO 2026-05-24).
      // Only attach when a controller already exists (returning visitor) so a
      // first-ever install doesn't trigger a spurious reload; `refreshing`
      // guards against reload loops.
      if (navigator.serviceWorker.controller) {
        let refreshing = false;
        navigator.serviceWorker.addEventListener("controllerchange", () => {
          if (refreshing) return;
          refreshing = true;
          window.location.reload();
        });
      }
    }

    if (typeof window === "undefined") return;

    // Already installed (standalone display) — never prompt.
    if (window.matchMedia("(display-mode: standalone)").matches) return;
    // iOS Safari has a separate `navigator.standalone` flag for the
    // "added to home screen" mode. Don't prompt those users either.
    const navStandalone =
      (window.navigator as Navigator & { standalone?: boolean }).standalone;
    if (navStandalone === true) return;

    // Respect recent dismissal within the 7-day window.
    const dismissedAt = localStorage.getItem(DISMISS_KEY);
    if (dismissedAt) {
      const age = Date.now() - Number(dismissedAt);
      if (Number.isFinite(age) && age < DISMISS_WINDOW_MS) return;
    }

    // iOS Safari branch: schedule the static A2HS card immediately.
    if (isIosSafariBrowser()) {
      timerRef.current = setTimeout(() => {
        setVariant("ios");
        setVisible(true);
      }, APPEAR_DELAY_MS);
      return () => {
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
      };
    }

    // Chromium branch — listen for the native event.
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setVariant("chromium");
      timerRef.current = setTimeout(() => setVisible(true), APPEAR_DELAY_MS);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const install = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    setDeferredPrompt(null);
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  };

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  };

  // Render guard: visible + at least one supported variant. iOS branch has
  // no deferredPrompt (Apple doesn't expose one); Chromium needs it.
  if (!visible) return null;
  if (variant === "chromium" && !deferredPrompt) return null;
  if (!variant) return null;

  return (
    // 2026-05-17 wave C-3 P1: mobile BottomNav is h-16 (64px) + safe-area
    // and sits at z-50. Previous `bottom-4` placed this card directly under
    // (or fully behind) the nav on every <md viewport — buttons untappable
    // on phones. Lift the mobile variant clear with bottom-[80px] (64px
    // nav + 16px gap). Desktop keeps md:bottom-6 (BottomNav hidden ≥md).
    <div
      role="dialog"
      aria-labelledby="pq-install-title"
      aria-describedby="pq-install-body"
      className="pointer-events-auto fixed bottom-[80px] left-4 right-4 z-50 md:bottom-6 md:left-auto md:right-6 md:w-[360px]"
    >
      <div
        className="relative overflow-hidden p-5"
        style={{
          background: "#050505",
          border: "1px solid rgba(245, 240, 232, 0.10)",
          borderRadius: 2,
          color: "var(--pq-ivory)",
        }}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div
              className="mb-2 inline-flex items-center gap-2.5 font-mono uppercase"
              style={{
                color: "var(--pq-bronze)",
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.22em",
                fontWeight: 500,
              }}
            >
              <span
                aria-hidden="true"
                className="inline-block h-px w-6"
                style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
              />
              <span>Install · 0.0KB</span>
            </div>
            <h3
              id="pq-install-title"
              className="font-display italic"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-h4)",
                lineHeight: 1.2,
                letterSpacing: "-0.018em",
                color: "var(--pq-ivory)",
              }}
            >
              데스크에 PivoxQuant를 더하세요.
            </h3>
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss install prompt"
            className="-mr-1 -mt-1 p-1 transition-colors"
            style={{ color: "rgba(245, 240, 232, 0.5)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p
          id="pq-install-body"
          className="mb-5 font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245, 240, 232, 0.65)",
            letterSpacing: "-0.003em",
          }}
        >
          {variant === "ios" ? (
            <>
              어느 창에서든 포트폴리오를 관찰하세요. iOS Safari 에선
              하단의 <Share className="inline h-3.5 w-3.5 align-text-bottom" />
              {" "}공유 아이콘 → &ldquo;홈 화면에 추가&rdquo; 를 눌러주세요.
            </>
          ) : (
            <>
              어느 창에서든 포트폴리오를 관찰하세요 — 설치형, 오프라인 지원,
              중요한 변화 발생 시 푸시 알림.
            </>
          )}
        </p>
        <div className="flex gap-2">
          {variant === "chromium" ? (
            <button
              type="button"
              onClick={install}
              className="pq-ink-btn-bronze inline-flex flex-1 items-center justify-center gap-2"
            >
              <Download className="h-3.5 w-3.5" />
              <span>설치</span>
            </button>
          ) : (
            // iOS — no programmatic install; just acknowledge.
            <button
              type="button"
              onClick={dismiss}
              className="pq-ink-btn-bronze inline-flex flex-1 items-center justify-center gap-2"
            >
              <Share className="h-3.5 w-3.5" />
              <span>알겠습니다</span>
            </button>
          )}
          <button
            type="button"
            onClick={dismiss}
            className="pq-ink-btn-ghost"
          >
            나중에
          </button>
        </div>
      </div>
    </div>
  );
}
