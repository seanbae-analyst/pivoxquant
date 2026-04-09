"use client";

import { useEffect, useState } from "react";

type InAppBrowser = "kakaotalk" | "naver" | "line" | "instagram" | "facebook";

function detectInAppBrowser(ua: string): InAppBrowser | null {
  if (/KAKAOTALK/i.test(ua)) return "kakaotalk";
  if (/NAVER\(inapp/i.test(ua)) return "naver";
  if (/Line\//i.test(ua)) return "line";
  if (/Instagram/i.test(ua)) return "instagram";
  if (/FBAN|FBAV/i.test(ua)) return "facebook";
  return null;
}

function isAndroid(): boolean {
  return /Android/i.test(navigator.userAgent);
}

function isIOS(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

function openExternalBrowser(url: string, browser: InAppBrowser) {
  // KakaoTalk
  if (browser === "kakaotalk") {
    if (isIOS()) {
      window.location.href = `kakaotalk://web/openExternal?url=${encodeURIComponent(url)}`;
      return;
    }
    if (isAndroid()) {
      window.location.href = `intent://${url.replace(/^https?:\/\//, "")}#Intent;scheme=https;package=com.android.chrome;end`;
      return;
    }
  }

  // Naver
  if (browser === "naver") {
    if (isAndroid()) {
      window.location.href = `intent://${url.replace(/^https?:\/\//, "")}#Intent;scheme=https;package=com.android.chrome;end`;
      return;
    }
    // iOS Naver: open in Safari
    window.open(url, "_blank");
    return;
  }

  // Generic fallback: try window.open
  window.open(url, "_blank");
}

export function InAppBrowserGuard() {
  const [browser, setBrowser] = useState<InAppBrowser | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const detected = detectInAppBrowser(navigator.userAgent);
    setBrowser(detected);

    // Auto-redirect attempt
    if (detected) {
      const timer = setTimeout(() => {
        openExternalBrowser(window.location.href, detected);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!browser) return null;

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const input = document.createElement("input");
      input.value = window.location.href;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const browserNames: Record<InAppBrowser, string> = {
    kakaotalk: "카카오톡",
    naver: "네이버",
    line: "라인",
    instagram: "인스타그램",
    facebook: "페이스북",
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#050508] p-6">
      <div className="max-w-sm text-center">
        <img
          src="/icons/icon-192x192.png"
          alt="StockPilot"
          className="mx-auto mb-6 h-20 w-20 rounded-2xl"
        />
        <h1 className="mb-3 text-xl font-semibold text-zinc-100">
          외부 브라우저에서 열어주세요
        </h1>
        <p className="mb-6 text-sm leading-relaxed text-zinc-400">
          {browserNames[browser] || "인앱"} 브라우저에서는 StockPilot의 모든
          기능을 사용할 수 없습니다.
          <br />
          Chrome 또는 Safari에서 열어주세요.
        </p>

        <button
          onClick={() =>
            openExternalBrowser(window.location.href, browser)
          }
          className="mb-3 w-full rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-zinc-900 transition-opacity hover:opacity-85"
        >
          외부 브라우저로 열기
        </button>

        <button
          onClick={handleCopyUrl}
          className="w-full rounded-xl border border-zinc-700 px-6 py-3 text-sm text-zinc-300 transition-colors hover:border-zinc-500"
        >
          {copied ? "복사됨!" : "URL 복사하기"}
        </button>

        <p className="mt-4 text-xs text-zinc-600">
          복사한 URL을 Chrome 또는 Safari에 붙여넣기 하세요
        </p>
      </div>
    </div>
  );
}
