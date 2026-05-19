import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <div className="max-w-xl text-center">
        <div
          className="text-pq-mono-sm tracking-[0.22em] uppercase mb-4"
          style={{ color: "var(--pq-bronze)" }}
        >
          Error 404 · Page not found
        </div>
        <h1
          className="font-serif italic mb-6 leading-[1.05]"
          style={{ fontSize: "clamp(2.5rem,6vw,3.75rem)" }}
        >
          Nothing to observe here.
        </h1>
        <p
          className="text-sm leading-relaxed mb-8"
          style={{ color: "rgba(var(--pq-ivory-rgb),0.65)" }}
        >
          The page you requested does not exist, or has moved to a different
          location. Return to the desk and resume your observation.
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link
            href="/"
            className="pq-ink-btn-bronze inline-flex items-center gap-2"
          >
            <Home className="h-3.5 w-3.5" />
            Back to desk
          </Link>
        </div>
        <p
          className="mt-12 text-pq-mono-sm tracking-[0.14em]"
          style={{ color: "rgba(var(--pq-ivory-rgb),0.3)" }}
        >
          PivoxQuant · Observational research only
        </p>
      </div>
    </div>
  );
}
