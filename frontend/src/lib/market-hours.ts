/**
 * market-hours.ts — Client-side market session detection.
 *
 * Used to pace SWR refresh intervals. Market open → aggressive polling
 * (5-10s). Market closed → relaxed polling (60-120s) to conserve requests
 * and API budget when nothing moves.
 *
 * Session windows are read in each exchange's own clock (no holiday awareness):
 *   US: 09:30-16:00 America/New_York, Mon-Fri — DST-aware. The old fixed
 *       13:30-20:00 UTC was the EDT window; from November (EST) the last hour
 *       of the session (20:00-21:00 UTC) fell back to the 60 s "closed" poll
 *       (2026-10-22).
 *   KR: 09:00-15:30 Asia/Seoul, Mon-Fri
 *
 * For a stricter check, plug in a server-provided calendar. For now the
 * client just needs "is it plausibly live right now" to decide cadence.
 */

export type MarketStatus = "us-open" | "kr-open" | "both-open" | "closed";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Weekday (0 Sun … 6 Sat) and minutes since local midnight in `timeZone`. */
function localClock(now: Date, timeZone: string): { day: number; minutes: number } {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return {
    day: WEEKDAYS.indexOf(get("weekday")),
    minutes: Number(get("hour")) * 60 + Number(get("minute")),
  };
}

function inSession(now: Date, timeZone: string, open: number, close: number): boolean {
  const { day, minutes } = localClock(now, timeZone);
  return day >= 1 && day <= 5 && minutes >= open && minutes < close;
}

export function getMarketStatus(now: Date = new Date()): MarketStatus {
  // US regular session 09:30-16:00 ET, KR 09:00-15:30 KST (closing auction included).
  const usOpen = inSession(now, "America/New_York", 9 * 60 + 30, 16 * 60);
  const krOpen = inSession(now, "Asia/Seoul", 9 * 60, 15 * 60 + 31);

  if (usOpen && krOpen) return "both-open";
  if (usOpen) return "us-open";
  if (krOpen) return "kr-open";
  return "closed";
}

export function isMarketOpen(): boolean {
  return getMarketStatus() !== "closed";
}

/**
 * Market-aware SWR refresh interval (ms).
 *
 * Pass to `refreshInterval` as `() => liveRefresh(openMs, closedMs)` so it
 * is re-evaluated on every revalidation — the cadence shifts automatically
 * when a market opens or closes without a page reload.
 */
export function liveRefresh(openMs = 5_000, closedMs = 60_000): number {
  return isMarketOpen() ? openMs : closedMs;
}
