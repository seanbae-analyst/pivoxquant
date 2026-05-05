"use client";

import { useState, useEffect, useRef } from "react";
import { X, Download } from "lucide-react";

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

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);
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
    }

    if (typeof window === "undefined") return;

    // Already installed — nothing to prompt.
    if (window.matchMedia("(display-mode: standalone)").matches) return;

    // Respect recent dismissal within the 7-day window.
    const dismissedAt = localStorage.getItem(DISMISS_KEY);
    if (dismissedAt) {
      const age = Date.now() - Number(dismissedAt);
      if (Number.isFinite(age) && age < DISMISS_WINDOW_MS) return;
    }

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
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

  if (!visible || !deferredPrompt) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="pq-install-title"
      aria-describedby="pq-install-body"
      className="pointer-events-auto fixed bottom-4 left-4 right-4 z-50 md:bottom-6 md:left-auto md:right-6 md:w-[360px]"
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
                fontSize: "10px",
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
              className="font-serif italic"
              style={{
                fontFamily:
                  '"Playfair Display","Source Serif 4",Georgia,serif',
                fontWeight: 500,
                fontSize: "20px",
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
            fontFamily: '"Source Serif 4", Georgia, serif',
            fontSize: "13px",
            lineHeight: 1.55,
            color: "rgba(245, 240, 232, 0.65)",
            letterSpacing: "-0.003em",
          }}
        >
          어느 창에서든 포트폴리오를 관찰하세요 — 설치형, 오프라인 지원,
          중요한 변화 발생 시 푸시 알림.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={install}
            className="pq-ink-btn-bronze inline-flex flex-1 items-center justify-center gap-2"
          >
            <Download className="h-3.5 w-3.5" />
            <span>설치</span>
          </button>
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
