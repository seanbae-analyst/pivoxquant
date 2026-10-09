import type { User } from "@/lib/auth";

/**
 * How many more times this user can re-answer the five onboarding questions
 * (설정 → "다섯 문항 다시 답하기" → PUT /api/profile), or `null` when there
 * is no cap to show.
 *
 * Mirrors the backend gate in `routes/profile.py::update_profile`: only an
 * `effective_tier` of free (or missing) is capped, by
 * `users.profile_changes_left`; any other tier never decrements it, so its
 * stored count means nothing and must not block. A missing count is also
 * `null` — the server stays the final word (403 PROFILE_CHANGE_LIMIT).
 */
export function retakeChangesLeft(
  user: Pick<User, "profile_changes_left" | "effective_tier" | "subscription_tier">,
): number | null {
  const tier = user.effective_tier || user.subscription_tier || "free";
  if (tier !== "free") return null;
  const left = user.profile_changes_left;
  if (typeof left !== "number" || !Number.isFinite(left)) return null;
  return Math.max(0, left);
}
