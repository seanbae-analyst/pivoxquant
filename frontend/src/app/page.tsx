"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";
import dynamic from "next/dynamic";
import { AppCover, isStandaloneDisplay } from "@/components/pwa/app-cover";
import { isDemoMode } from "@/lib/demo";
import { hadSession } from "@/lib/had-session";

// 2026-10-09 (perf): the landing (≈364KB gz with motion) and the welcome
// cards are split out of "/"'s first chunk. The landing keeps SSR — crawlers
// and link unfurlers still get the full HTML (see the 2026-09-02 note below)
// — while the installed app, which shows AppCover / AppWelcome and never the
// landing once it knows it is standalone, need not wait for that JS before
// its cover is interactive. The cover itself is static (app-cover.tsx).
const LandingV2 = dynamic(() => import("@/components/landing/landing-v2"));
const AppWelcome = dynamic(
  () => import("@/components/pwa/app-welcome").then((m) => m.AppWelcome),
  { loading: () => <AppCover /> },
);

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
  const { user, loading, waking } = useAuth();
  const router = useRouter();
  const demo = isDemoMode();
  // The server cannot know how the page was opened; its snapshot (false) keeps
  // hydration on the landing, and the client snapshot takes over after.
  const standalone = useSyncExternalStore(noopSubscribe, isStandaloneDisplay, () => false);
  const returning = useSyncExternalStore(noopSubscribe, hadSession, () => false);

  // Installed app, auth not known yet, and this device has held a session
  // (2026-10-10). Measured on a cold backend before this: a signed-in launch
  // at "/" held the bare cover for ~9 s, then — the unknown state read as a
  // guest — went to the welcome cards (or /login once they had been seen);
  // when the wake took longer than the auth poll's deadline nothing ever
  // re-checked, and the cover stayed up for good ("PIVOXQUANT 화면에서
  // 멈춤"). The home tab already handles an unknown state: (dashboard) holds
  // its skeleton with the "server is waking" line and a retry, and sends a
  // definite signed-out answer back here — which no longer matches (neither
  // loading nor waking), so this cannot loop.
  const openHome = standalone && !demo && returning && (loading || waking);
  useEffect(() => {
    if (openHome) router.replace("/mirror");
  }, [openHome, router]);

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
  // Installed app: hold the cover through the redirect to /mirror, so the
  // launch reads splash → cover → 거울 with no pulse-dot loading screen.
  if (user) return standalone ? <AppCover /> : <LoadingScreen />;

  // Opened from the home-screen icon: an app has no landing page (2026-10-07).
  // Still unknown (waking) for a returning user: hold the cover through the
  // redirect above. A first-time visitor gets the cards, which need no server.
  if (standalone) return openHome ? <AppCover /> : <AppWelcome />;

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
