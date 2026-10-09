"use client";

/**
 * AppCover — PIVOXQUANT alone on Vantablack: the first picture of the
 * installed app (the iOS launch images in public/splash are drawn from the
 * same outlines). Split out of app-welcome.tsx (2026-10-09, perf) so the
 * root page can show it without loading the welcome cards or the landing.
 */

/**
 * The landing's page 0 (landing/splash-page.tsx) — PIVOXQUANT alone on
 * Vantablack. The app opens on it (2026-10-09, CEO: "웹페이지처럼 딱 아무것도
 * 없이 … 그거 두고 넘기는 식"), and the "/" splash uses the same cover so
 * launch → cover → first card never changes picture.
 */
export function AppCover({ hint }: { hint?: string }) {
  return (
    <div
      className="relative flex h-full min-h-[100dvh] w-full items-center justify-center px-6"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
      data-pq-chrome
      data-testid="app-cover"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 80% at 50% 50%, rgba(245,240,232,0.03) 0%, rgba(245,240,232,0.012) 40%, transparent 75%)",
        }}
      />
      <span
        className="pq-splash-wordmark font-serif"
        style={{
          fontSize: "min(var(--pq-text-display), 10vw)",
          letterSpacing: "0.22em",
          lineHeight: 1,
          fontWeight: 500,
          textTransform: "uppercase",
          textAlign: "center",
        }}
      >
        PIVOXQUANT
      </span>
      {hint && (
        <span
          className="pointer-events-none absolute left-0 right-0 text-center font-serif"
          style={{
            bottom: "clamp(28px, 5vh, 56px)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.24em",
            color: "rgba(var(--pq-bronze-rgb), 0.80)",
          }}
        >
          {hint}
        </span>
      )}
    </div>
  );
}

/** True when launched from the home-screen icon (Android standalone or iOS). */
export function isStandaloneDisplay(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  return Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);
}

