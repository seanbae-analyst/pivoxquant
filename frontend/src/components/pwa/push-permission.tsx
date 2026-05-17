"use client";

import { useState, useEffect } from "react";
import { Bell, X } from "lucide-react";

const DISMISS_KEY = "pq-push-dismissed";
// Re-prompt after two weeks if the user said "later" — alerts are less
// critical than install, so we ask less often.
const DISMISS_WINDOW_MS = 14 * 24 * 60 * 60 * 1000;
// Wait for the user to settle into a session before surfacing the prompt.
const APPEAR_DELAY_MS = 30_000;

export function PushPermission() {
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (typeof Notification === "undefined") return;
    // If the user already granted/denied, we don't show the prompt.
    // "granted" is a no-op; "denied" means the permission UI is gone anyway.
    if (Notification.permission !== "default") return;

    const dismissedAt = localStorage.getItem(DISMISS_KEY);
    if (dismissedAt) {
      const age = Date.now() - Number(dismissedAt);
      if (Number.isFinite(age) && age < DISMISS_WINDOW_MS) return;
    }

    const timer = window.setTimeout(() => setVisible(true), APPEAR_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, []);

  const enable = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const permission = await Notification.requestPermission();
      if (permission === "granted") {
        try {
          const { subscribeToPush } = await import("@/lib/push");
          await subscribeToPush();
        } catch (err) {
          // F3-04 (2026-05-17): previously swallowed silently — the user
          // saw the prompt vanish and assumed push was enabled, but no
          // subscription was ever created (e.g. VAPID public key missing).
          // Log the failure so it shows up in Sentry / console. We do not
          // raise a toast here because the prompt UI itself is dismissing;
          // Settings page surfaces the actionable retry path.
          console.error("[pq-push] subscribe failed after permission grant:", err);
        }
      }
    } finally {
      setBusy(false);
      setVisible(false);
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    }
  };

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  };

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="pq-push-title"
      aria-describedby="pq-push-body"
      className="pointer-events-auto fixed right-4 top-20 z-50 w-[340px] max-w-[calc(100vw-2rem)] md:right-6"
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
          <div className="flex items-start gap-3">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[2px] border"
              style={{
                borderColor: "rgba(139, 111, 71, 0.5)",
                color: "var(--pq-bronze)",
              }}
            >
              <Bell className="h-4 w-4" />
            </div>
            <div>
              <div
                className="mb-1 text-pq-eyebrow font-medium uppercase tracking-[0.24em]"
                style={{ color: "var(--pq-bronze)" }}
              >
                Observation alerts
              </div>
              <h3
                id="pq-push-title"
                className="font-serif text-pq-deck leading-tight"
                style={{ color: "var(--pq-ivory)" }}
              >
                Be notified when the picture changes.
              </h3>
            </div>
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss notification prompt"
            className="-mr-1 -mt-1 rounded-full p-1"
            style={{ color: "rgba(245, 240, 232, 0.5)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p
          id="pq-push-body"
          className="mb-5 text-pq-body-sm leading-relaxed"
          style={{ color: "rgba(245, 240, 232, 0.68)" }}
        >
          Material signal shifts, risk threshold breaches, and weekly memo
          deliveries. No marketing, no noise.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={enable}
            disabled={busy}
            className="pq-ink-btn-bronze inline-flex flex-1 items-center justify-center gap-2 disabled:opacity-60"
          >
            <Bell className="h-3.5 w-3.5" />
            <span>{busy ? "Enabling…" : "Enable"}</span>
          </button>
          <button type="button" onClick={dismiss} className="pq-ink-btn-ghost">
            Later
          </button>
        </div>
      </div>
    </div>
  );
}
