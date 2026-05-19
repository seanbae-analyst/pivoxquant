/**
 * Root loading UI.
 *
 * Shown by Next.js while any route segment below the root suspends (initial
 * render, loading.js fallback chain, data-fetching boundaries). Matches the
 * PivoxQuant Vantablack Luxe palette — no gradient buttons, warm-gold accent.
 */
export default function Loading() {
  return (
    <div
      className="min-h-[100dvh] flex flex-col items-center justify-center"
      role="status"
      aria-live="polite"
      aria-label="Loading PivoxQuant"
      style={{ background: "#050505" }}
    >
      {/* Warm-gold pulse dot — brand mark */}
      <div
        className="rounded-full mb-6 animate-pulse"
        style={{
          width: "10px",
          height: "10px",
          background: "#B8956A",
        }}
      />

      {/* Wordmark */}
      <div
        className="font-serif italic text-lg tracking-tight mb-8"
        style={{ color: "rgba(245,240,232,0.6)" }}
      >
        PivoxQuant
      </div>

      {/* Shimmer skeleton bar */}
      <div
        className="rounded-full overflow-hidden"
        style={{
          width: "120px",
          height: "2px",
          background: "rgba(245,240,232,0.08)",
        }}
      >
        <div className="h-full pq-skeleton-dark" />
      </div>

      <span className="sr-only">Loading…</span>
    </div>
  );
}
