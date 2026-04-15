/**
 * Root loading UI.
 *
 * Shown by Next.js while any route segment below the root suspends (initial
 * render, `loading.js` fallback chain, data-fetching boundaries). Matches the
 * bespoke `LoadingScreen` used in `app/page.tsx` so transitions feel seamless.
 *
 * Mirrors the `.bg-primary-gradient` + `.animate-shimmer-slide` patterns from
 * the existing landing/auth loading states.
 */
export default function Loading() {
  return (
    <div
      className="min-h-[100dvh] flex flex-col items-center justify-center bg-white"
      role="status"
      aria-live="polite"
      aria-label="Loading PivoxQuant"
    >
      {/* Logo mark — identical to the one in app/page.tsx LoadingScreen */}
      <div className="w-10 h-10 rounded-xl bg-primary-gradient flex items-center justify-center mb-4 animate-pulse">
        <svg
          className="w-5 h-5 text-white"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
          <polyline points="16 7 22 7 22 13" />
        </svg>
      </div>

      {/* Shimmer progress bar */}
      <div className="w-32 h-1 rounded-full overflow-hidden bg-slate-100">
        <div className="h-full w-1/2 rounded-full bg-primary-gradient animate-shimmer-slide" />
      </div>

      <span className="sr-only">Loading…</span>
    </div>
  );
}
