/**
 * Single source of truth for the weekly CFO memo delivery promise.
 *
 * Why this exists (P1-4, 2026-05-20 ux-flow fix): three surfaces shipped
 * three CONFLICTING promises —
 *   - today-memo-hero-v2.tsx   "Monday 07:00 KST"
 *   - latest-artifact-card.tsx "06:00 KST next trading day"
 *   - companion-archive-card   "Monday 07:00 KST"
 * None matched the backend. The real APScheduler job (`app.py`
 * `weekly_memo_sunday`, line ~1146) fires:
 *
 *     trigger="cron", day_of_week="sun", hour=8, minute=0,
 *     timezone="Asia/Seoul"
 *
 * → every Sunday 08:00 KST. All UI copy must read from these constants so
 * the promise can never drift from the scheduler again. If the cron ever
 * changes, update HERE only.
 */

/** Short label for inline use, e.g. eyebrows / dense rows. */
export const WEEKLY_MEMO_WHEN_SHORT = "Sundays 08:00 KST";

/**
 * Full empty-state sentence. Honest "first one is on its way" framing —
 * never implies a memo already exists.
 */
export const WEEKLY_MEMO_EMPTY_LINE =
  "Your first weekly memo lands Sunday 08:00 KST.";

/** Korean equivalent for KR-locale surfaces if needed later. */
export const WEEKLY_MEMO_WHEN_SHORT_KO = "매주 일요일 08:00 KST";
