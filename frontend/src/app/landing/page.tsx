import { redirect } from "next/navigation";

/**
 * /landing — fallback redirect to /mirror (the signed-in home; /home 308s there too).
 *
 * Some OAuth callback flows (and historical bookmarks) point at /landing,
 * which never had a real page in the App Router. Without this route, users
 * landed on the global 404 ("Nothing to observe here") immediately after
 * Google/Kakao login. The backend `_safe_next()` already maps /landing
 * away, so this is the second layer of defense for direct navigation
 * (typed URL, bookmark, external link).
 *
 * Server-side redirect is preferred over client-side useEffect to avoid
 * a flash of empty content.
 */
export default function LandingPage() {
  redirect("/mirror");
}
