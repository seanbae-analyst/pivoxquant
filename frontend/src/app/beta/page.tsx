import { redirect } from "next/navigation";

/**
 * /beta → /beta-gate redirect.
 *
 * The actual private-beta gate lives at /beta-gate; /beta is a common
 * shorthand users type or paste. Without this route, /beta hit the global
 * 404. Backend `_safe_next()` also maps /beta → /beta-gate; this page
 * covers direct navigation.
 */
export default function BetaPage() {
  redirect("/beta-gate");
}
