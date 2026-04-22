/**
 * market-hours.ts — Client-side market session detection.
 *
 * Used to pace SWR refresh intervals. Market open → aggressive polling
 * (5-10s). Market closed → relaxed polling (60-120s) to conserve requests
 * and API budget when nothing moves.
 *
 * Session windows are approximations (UTC based, no holiday awareness):
 *   US: 13:30-20:00 UTC, Mon-Fri (09:30-16:00 ET)
 *   KR: 00:00-06:30 UTC, Mon-Fri (09:00-15:30 KST)
 *
 * For a stricter check, plug in a server-provided calendar. For now the
 * client just needs "is it plausibly live right now" to decide cadence.
 */

export type MarketStatus = "us-open" | "kr-open" | "both-open" | "closed";

export function getMarketStatus(): MarketStatus {
  const now = new Date();
  const utcHour = now.getUTCHours();
  const utcMin = now.getUTCMinutes();
  const day = now.getUTCDay(); // 0 Sun, 1 Mon ... 6 Sat
  const isWeekday = day >= 1 && day <= 5;

  // US markets: 13:30-20:00 UTC (09:30am-4pm ET)
  const usOpen =
    isWeekday &&
    ((utcHour === 13 && utcMin >= 30) || (utcHour >= 14 && utcHour < 20));

  // KR markets: 00:00-06:30 UTC (9am-3:30pm KST)
  const krOpen =
    isWeekday && (utcHour < 6 || (utcHour === 6 && utcMin <= 30));

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
