/**
 * /settings/profile — Legacy path, permanent redirect to /profile.
 *
 * 2026-04-24: profile/persona surface promoted to top-level /profile so
 * Settings can stay scoped to operational controls. This route stays
 * alive to catch old bookmarks and dropdown links rendered by stale clients.
 */

import { redirect } from "next/navigation";

export default function LegacySettingsProfilePage() {
  redirect("/profile");
}
