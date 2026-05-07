/**
 * Sentry edge config — runs in the Vercel Edge runtime (middleware,
 * Edge route handlers).
 *
 * Edge has no Node APIs, so the @sentry/nextjs edge transport is a smaller
 * surface than the server one. DSN is read from `SENTRY_DSN` (same env as
 * server config) — Vercel exposes server-only env to Edge.
 */
import * as Sentry from "@sentry/nextjs";

const DSN = process.env.SENTRY_DSN;

if (DSN) {
  Sentry.init({
    dsn: DSN,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    environment: process.env.VERCEL_ENV || "development",
  });
}
