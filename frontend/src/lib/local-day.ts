/**
 * Local calendar day "YYYY-MM-DD" of `d` (default now) — no UTC shift, so it
 * matches a date input's value and compares as a string.
 *
 * `new Date().toISOString().slice(0, 10)` is the UTC day: in Korea it is
 * still yesterday until 09:00, so a trade recorded before then defaulted to
 * the previous date (TradeModalV2, 2026-10-13 bug hunt).
 */
export function localDayStr(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
