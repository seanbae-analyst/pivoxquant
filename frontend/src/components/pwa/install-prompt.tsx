"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);

  useEffect(() => {
    // Already installed as PWA
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as unknown as { standalone?: boolean }).standalone === true;
    setIsStandalone(standalone);
    if (standalone) return;

    // Check if dismissed before
    if (localStorage.getItem("sp-install-dismissed") === "true") return;

    // iOS detection
    const ua = navigator.userAgent;
    const ios = /iPad|iPhone|iPod/.test(ua);
    setIsIOS(ios);

    // Track page views for engagement threshold
    const views = parseInt(localStorage.getItem("sp-page-views") || "0") + 1;
    localStorage.setItem("sp-page-views", views.toString());

    // Show after 3+ page views
    if (views < 3) return;

    if (ios) {
      setShowPrompt(true);
      return;
    }

    // Chrome/Samsung/Edge: capture beforeinstallprompt
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setShowPrompt(true);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (isStandalone || !showPrompt) return null;

  const handleInstall = async () => {
    if (deferredPrompt) {
      await deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        setShowPrompt(false);
      }
      setDeferredPrompt(null);
    }
  };

  const handleDismiss = () => {
    localStorage.setItem("sp-install-dismissed", "true");
    setShowPrompt(false);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-zinc-800 bg-zinc-900/95 px-4 py-3 backdrop-blur-sm">
      <div className="mx-auto flex max-w-lg items-center gap-3">
        <img
          src="/icons/icon-96x96.png"
          alt="StockPilot"
          className="h-10 w-10 rounded-lg"
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-zinc-100">
            StockPilot 앱 설치
          </p>
          {isIOS ? (
            <p className="text-xs text-zinc-400">
              공유 버튼 → &quot;홈 화면에 추가&quot;를 눌러주세요
            </p>
          ) : (
            <p className="text-xs text-zinc-400">
              홈 화면에 추가하면 더 빠르게 접근할 수 있어요
            </p>
          )}
        </div>
        {!isIOS && (
          <button
            onClick={handleInstall}
            className="shrink-0 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-zinc-900 transition-opacity hover:opacity-85"
          >
            설치
          </button>
        )}
        <button
          onClick={handleDismiss}
          className="shrink-0 text-xs text-zinc-500 hover:text-zinc-300"
        >
          닫기
        </button>
      </div>
    </div>
  );
}
