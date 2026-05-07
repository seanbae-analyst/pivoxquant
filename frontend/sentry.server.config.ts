/**
 * Sentry server config — runs in the Node.js runtime (SSR, route handlers).
 *
 * No consent check here: server-side errors don't carry user PII unless we
 * pass it ourselves, and `sendDefaultPii: false` prevents the SDK from
 * attaching IP/cookies/headers automatically.
 *
 * DSN: SENTRY_DSN — server-only env var. Backend (Flask) reads the same
 * name from its own env (see .env.example:174).
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
