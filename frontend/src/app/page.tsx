"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import LandingV2 from "@/components/landing/landing-v2";
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

export default function Page() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const demo = isDemoMode();

  useEffect(() => {
    // Real app: send a logged-in user straight to /home. In DEMO the demo user
    // is always "logged in", so skipping this keeps the landing as the public
    // entry — its CTAs (/signup, /login) then redirect onward to /home.
    if (!demo && !loading && user) {
      router.replace("/home");
    }
  }, [demo, user, loading, router]);

  // DEMO (portfolio showcase): landing IS the front door. Render it the same on
  // SSR + client (independent of user) so there's no redirect and no hydration
  // divergence.
  if (demo) return <LandingV2 />;
  if (loading) return <LoadingScreen />;
  if (user) return <LoadingScreen />;

  return <LandingV2 />;
}
