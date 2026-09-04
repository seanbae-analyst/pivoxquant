import { redirect } from "next/navigation";

/**
 * /beta → / redirect.
 *
 * The private-beta gate (/beta-gate + /api/beta-auth) was retired on
 * 2026-09-04 (CEO: free launch, no gate). /beta is still a common shorthand
 * people type or paste from old messages; keep it out of the global 404.
 * Backend `_safe_next()` maps /beta the same way.
 */
export default function BetaPage() {
  redirect("/");
}
