/**
 * Server-safe half of lib/early-wake.ts: the inline <head> wake script.
 *
 * No imports on purpose — the root layout is a server component, and a value
 * imported from a "use client" module (lib/backend-wake) would arrive there
 * as a client reference, not a string. The literal path is pinned to
 * `HEALTH_PATH` by src/lib/__tests__/early-wake.test.ts.
 *
 * Render it with the CSP nonce:
 *   <script nonce={nonce} dangerouslySetInnerHTML={{ __html: EARLY_WAKE_INLINE_SCRIPT }} />
 * It runs before any bundle downloads; the bundle's wakeBackendEarly() then
 * sees the window flag and does not send a second request.
 */

/** Window flag set by the inline script once it has sent the request. */
export const EARLY_WAKE_WINDOW_FLAG = "__pqWakeSent";

export const EARLY_WAKE_INLINE_PATH = "/api/health";

export const EARLY_WAKE_INLINE_SCRIPT =
  `try{window.${EARLY_WAKE_WINDOW_FLAG}=1;` +
  `fetch("${EARLY_WAKE_INLINE_PATH}",{method:"GET",cache:"no-store",credentials:"omit",keepalive:true})` +
  `.catch(function(){})}catch(e){}`;
