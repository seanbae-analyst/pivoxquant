/**
 * Vendor market-data DISPLAY flag — `NEXT_PUBLIC_MARKET_DATA_DISPLAY`.
 *
 * Why
 * ---
 * 2026-09-19 terms review: no source — domestic or US — lets us show vendor
 * closing prices to a user for free and legally. FMP §2.2.2 forbids display
 * without a Data Display Agreement, and that clause does not exempt a free
 * beta. The three core surfaces (멈춤 · 기록 · 거울) never call a quote feed;
 * the only places that did are `/portfolio`'s valuation and the 52-week
 * alert. CEO decision: turn the DISPLAY off and run `/portfolio` on cost
 * basis until an FMP agreement lands.
 *
 * This is a flag, NOT a deletion. Turning it back on must restore the
 * previous screens byte-for-byte, so every call site here is a branch, never
 * a rewrite of the enabled path.
 *
 * Two signals, AND-ed
 * -------------------
 * The backend carries its own `MARKET_DATA_DISPLAY_ENABLED` and, when it is
 * off, stamps `market_data_display: false` on the payload and nulls / omits
 * the price fields. The frontend must hide a market figure when EITHER
 * signal is off:
 *
 *   - frontend flag off → hide, even if the backend still sends prices
 *     (this is what makes the flag deployable ahead of the backend);
 *   - backend says false → hide, even if the frontend flag is on, because
 *     the numbers arriving are null and `?? 0` would print a false "USD 0"
 *     — the same class of bug as the NAV loading flash fixed in bcd45e02.
 *
 * A backend that predates the contract sends no field at all. `undefined` is
 * NOT treated as off: that deploy is still sending real prices, and the
 * frontend flag alone decides.
 *
 * Reading the env var
 * -------------------
 * Same shape as `isDemoMode()` (lib/demo.ts): a function, not a module-level
 * constant, so `vi.stubEnv` works in tests and so Next's build-time inlining
 * of `process.env.NEXT_PUBLIC_*` happens at the call site. Unset === off.
 */

/** Frontend half of the gate. Unset / anything but "1" === off. */
export function isMarketDataDisplayEnabled(): boolean {
  return process.env.NEXT_PUBLIC_MARKET_DATA_DISPLAY === "1";
}

/**
 * Both halves of the gate.
 *
 * @param backendSignal `market_data_display` as received. `undefined` / null
 *   means the backend has not been taught the contract yet — only the
 *   frontend flag decides. Explicit `false` forces off.
 */
export function resolveMarketDataDisplay(
  backendSignal?: boolean | null,
): boolean {
  if (!isMarketDataDisplayEnabled()) return false;
  return backendSignal !== false;
}

/**
 * Dashboard routes that actually render vendor market data, and may
 * therefore surface a vendor-feed staleness warning.
 *
 * QA finding P3 (2026-09-19): the "시세 데이터가 지연되고 있어요" banner is
 * mounted in the (dashboard) layout, so it appeared on `/pre-trade` and
 * `/settings` — screens that never read a price. The banner is only ever
 * true about a screen that shows prices, so it is scoped here.
 *
 * `/portfolio` is the whole list: `/journal` and `/mirror` compute from the
 * user's own records (services/behavior/* import no quote service), and
 * `/settings` shows none.
 */
export const MARKET_DATA_ROUTES: readonly string[] = ["/portfolio"];

/** True when `pathname` is a route that renders vendor market data. */
export function routeUsesMarketData(pathname: string | null): boolean {
  if (!pathname) return false;
  return MARKET_DATA_ROUTES.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

/**
 * Notification event ids whose producer needs a vendor quote.
 *
 * `price_52w` is swept by `app.py::_scheduled_price_alerts` against the
 * 52-week range, which is vendor data. With display off the alert cannot
 * fire, so offering its toggle would be a dead switch — exactly the wart
 * the 2026-09-01 notification prune removed.
 */
export const MARKET_DATA_NOTIFICATION_EVENTS: readonly string[] = ["price_52w"];
