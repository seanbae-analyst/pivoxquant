"use client";

import { useState, useEffect } from "react";
import { Bell, X } from "lucide-react";

export function PushPermission() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (typeof Notification === "undefined") return;
    if (Notification.permission !== "default") return;
    if (localStorage.getItem("push_prompt_dismissed")) return;

    const timer = setTimeout(() => setShow(true), 30000);
    return () => clearTimeout(timer);
  }, []);

  const enable = async () => {
    const permission = await Notification.requestPermission();
    if (permission === "granted") {
      try {
        const { subscribeToPush } = await import("@/lib/push");
        await subscribeToPush();
      } catch {
        // Subscription may fail if service worker is not ready
      }
    }
    setShow(false);
    localStorage.setItem("push_prompt_dismissed", "1");
  };

  const dismiss = () => {
    setShow(false);
    localStorage.setItem("push_prompt_dismissed", "1");
  };

  if (!show) return null;

  return (
    <div className="fixed top-20 right-4 z-50 w-80 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl md:right-6">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10">
          <Bell className="h-5 w-5 text-accent" />
        </div>
        <div className="flex-1">
          <h3 className="mb-1 text-sm font-bold text-slate-900">
            Enable Notifications
          </h3>
          <p className="mb-3 text-xs text-slate-500">
            Get alerts when signals change, risk events occur, or your portfolio
            needs attention.
          </p>
          <div className="flex gap-2">
            <button
              onClick={enable}
              className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
            >
              Enable
            </button>
            <button
              onClick={dismiss}
              className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-500"
            >
              Later
            </button>
          </div>
        </div>
        <button
          onClick={dismiss}
          className="text-slate-400 hover:text-slate-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
