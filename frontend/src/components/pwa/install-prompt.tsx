"use client";

import { useState, useEffect } from "react";
import { X, Download } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Register the PWA service worker in production only (dev causes HMR conflicts)
    if (
      "serviceWorker" in navigator &&
      process.env.NODE_ENV === "production"
    ) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .catch((err) => console.warn("[PWA] SW register failed:", err));
    }

    if (localStorage.getItem("pwa_install_dismissed")) return;
    if (window.matchMedia("(display-mode: standalone)").matches) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);

      const views =
        parseInt(localStorage.getItem("page_views") || "0", 10) + 1;
      localStorage.setItem("page_views", String(views));
      if (views >= 3) setShow(true);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const install = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    setDeferredPrompt(null);
    setShow(false);
    localStorage.setItem("pwa_install_dismissed", "1");
  };

  const dismiss = () => {
    setShow(false);
    localStorage.setItem("pwa_install_dismissed", "1");
  };

  if (!show) return null;

  return (
    <div
      className="fixed bottom-20 left-4 right-4 z-50 flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl md:bottom-6 md:left-auto md:right-6 md:w-80"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-gradient">
        <Download className="h-5 w-5 text-white" />
      </div>
      <div className="flex-1">
        <h3 className="mb-1 text-sm font-bold text-slate-900">
          Install PivoxQuant
        </h3>
        <p className="mb-3 text-xs text-slate-500">
          Add to your home screen for the best experience.
        </p>
        <div className="flex gap-2">
          <button
            onClick={install}
            className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
          >
            Install
          </button>
          <button
            onClick={dismiss}
            className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-500"
          >
            Not Now
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
  );
}
