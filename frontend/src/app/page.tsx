"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";
import LandingV2 from "@/components/landing/landing-v2";
import { AppCover, AppWelcome, isStandaloneDisplay } from "@/components/pwa/app-welcome";
import { isDemoMode } from "@/lib/demo";

/**
 * Root LoadingScreen — Vantablack editorial treatment.
 *
 * Mirrors /loading.tsx (root Next.js suspense boundary) so the first paint
 * stays consistent whether Next.js's loading.tsx or this auth-gated screen
 * renders. No "icon-in-colored-box" AI slop frame — pure wordmark + bronze
 * pulse dot + hairline shimmer per design system v3 §9 (AI slop ban).
 */
function LoadingScreen() {
  return (
    <div
      className="min-h-[100dvh] flex flex-col items-center justify-center"
      role="status"
      aria-live="polite"
      aria-label="Loading PivoxQuant"
      style={{ backgroundColor: "var(--pq-ink)" }}
    >
      {/* Bronze pulse dot — brand mark, no surrounding frame */}
      <div
        className="rounded-full mb-6 animate-pulse"
        style={{
          width: "10px",
          height: "10px",
          background: "var(--pq-bronze)",
        }}
      />

      {/* Wordmark — italic serif, mirrors /loading.tsx */}
      <div
        className="font-serif text-lg tracking-tight mb-8"
        style={{ color: "rgba(245,240,232,0.6)" }}
      >
        PivoxQuant
      </div>

      {/* Shimmer skeleton bar — hairline only */}
      <div
        className="rounded-full overflow-hidden"
        style={{
          width: "120px",
          height: "2px",
          background: "var(--pq-ivory-line)",
        }}
      >
        <div className="h-full pq-skeleton-dark" />
      </div>

      <span className="sr-only">Loading…</span>
    </div>
  );
}

const noopSubscribe = () => () => {};

export default function Page() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const demo = isDemoMode();
  // The server cannot know how the page was opened; its snapshot (false) keeps
  // hydration on the landing, and the client snapshot takes over after.
  const standalone = useSyncExternalStore(noopSubscribe, isStandaloneDisplay, () => false);

  useEffect(() => {
    // Real app: send a logged-in user straight to /home. In DEMO the demo user
    // is always "logged in", so skipping this keeps the landing as the public
    // entry — its CTAs (/signup, /login) then redirect onward to /home.
    if (!demo && !loading && user) {
      router.replace("/mirror");
    }
  }, [demo, user, loading, router]);

  // DEMO (portfolio showcase): landing IS the front door. Render it the same on
  // SSR + client (independent of user) so there's no redirect and no hydration
  // divergence.
  if (demo) return <LandingV2 />;

  // ⚠️ 2026-09-02: this used to be `if (loading) return <LoadingScreen/>`.
  //
  // `useAuth().loading` starts true on the server and on the first client
  // paint, so the server-rendered HTML for "/" was the LoadingScreen — the
  // entire public landing existed only after hydration. Measured against prod:
  //
  //   curl -s https://www.pivoxquant.com/ | (strip tags)
  //   → "PivoxQuant — … Skip to main content PivoxQuant Loading…"
  //
  // That is everything a non-JS reader saw: search crawlers, and — the part
  // that actually costs users — KakaoTalk / Slack / LinkedIn link unfurlers,
  // which are the main way a Korean closed beta gets passed around. The OG
  // card survived (metadata is rendered in layout.tsx) but the page behind it
  // was blank.
  //
  // Rendering LandingV2 while `loading` fixes it and stays hydration-safe:
  // server and first client paint now agree on LandingV2. A logged-in visitor
  // sees the landing for the one tick before `loading` resolves, then gets the
  // LoadingScreen while the effect above redirects to /mirror. Costing signed-in
  // users a single frame is the right trade for a landing that is legible to
  // every crawler and chat preview.
  if (loading) return standalone ? <AppCover /> : <LandingOrAppSplash />;
  if (user) return <LoadingScreen />;

  // Opened from the home-screen icon: an app has no landing page (2026-10-07).
  if (standalone) return <AppWelcome />;

  return <LandingOrAppSplash />;
}

/**
 * The landing for a browser — but the server (and the first client paint)
 * can't tell a browser from the home-screen app, so the installed app used to
 * flash the whole web landing before swapping to the app screen (2026-10-09).
 * CSS knows before any JS runs (`display-mode: standalone`, plus the
 * `.pwa-standalone` class layout.tsx sets at boot): it hides the landing and
 * shows the splash there, keeping the HTML identical for hydration and for
 * crawlers / link unfurlers.
 */
function LandingOrAppSplash() {
  return (
    <>
      <div className="pq-browser-only">
        <LandingV2 />
      </div>
      <div className="pq-standalone-only" aria-hidden>
        <AppCover />
      </div>
    </>
  );
}
