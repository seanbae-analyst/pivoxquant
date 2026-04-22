import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ background: "#050505", color: "#F7F5EF" }}
    >
      <div className="max-w-xl text-center">
        <div
          className="text-[11px] tracking-[0.22em] uppercase mb-4"
          style={{ color: "#E2B96F" }}
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
          style={{ color: "rgba(247,245,239,0.65)" }}
        >
          The page you requested does not exist, or has moved to a different
          location. Return to the desk and resume your observation.
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link
            href="/home"
            className="pq-ink-btn-bronze inline-flex items-center gap-2"
          >
            <Home className="h-3.5 w-3.5" />
            Back to desk
          </Link>
          <Link href="/" className="pq-ink-btn-ghost">
            Landing
          </Link>
        </div>
        <p
          className="mt-12 text-[11px] tracking-[0.14em]"
          style={{ color: "rgba(247,245,239,0.3)" }}
        >
          PivoxQuant · Observational research only
        </p>
      </div>
    </div>
  );
}
