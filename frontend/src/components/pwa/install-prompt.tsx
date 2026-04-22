"use client";

import { useState, useEffect } from "react";
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
      window.setTimeout(() => setVisible(true), APPEAR_DELAY_MS);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
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
        className="relative overflow-hidden rounded-[2px] border p-5 shadow-2xl backdrop-blur-md"
        style={{
          background: "rgba(10, 10, 10, 0.96)",
          borderColor: "rgba(139, 111, 71, 0.42)",
          color: "var(--pq-ivory)",
        }}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <div
              className="mb-1 text-[10px] font-medium uppercase tracking-[0.24em]"
              style={{ color: "var(--pq-bronze)" }}
            >
              Install
            </div>
            <h3
              id="pq-install-title"
              className="font-serif text-[18px] leading-tight"
              style={{ color: "var(--pq-ivory)" }}
            >
              Add PivoxQuant to your dock.
            </h3>
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss install prompt"
            className="-mr-1 -mt-1 rounded-full p-1 transition-colors"
            style={{ color: "rgba(245, 240, 232, 0.5)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p
          id="pq-install-body"
          className="mb-5 text-[13px] leading-relaxed"
          style={{ color: "rgba(245, 240, 232, 0.68)" }}
        >
          Observe your portfolio from any window — installed, offline-ready,
          with push alerts for material changes.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={install}
            className="pq-ink-btn-bronze inline-flex flex-1 items-center justify-center gap-2"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Install</span>
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="pq-ink-btn-ghost"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
