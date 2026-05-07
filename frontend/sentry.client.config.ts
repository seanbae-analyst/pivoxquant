/**
 * Sentry client config — runs in the browser bundle.
 *
 * Init is gated on the user's analytics consent (lib/consent.ts). Without
 * consent, no DSN is wired up so the SDK becomes a no-op. The browser-side
 * SDK still ships in the bundle (required by withSentryConfig), it just
 * never opens a transport.
 *
 * DSN: NEXT_PUBLIC_SENTRY_DSN — exposed at build time. Leave unset on
 * staging or local dev to disable entirely.
 */
import * as Sentry from "@sentry/nextjs";
import { hasAnalyticsConsent } from "@/lib/consent";

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (DSN && hasAnalyticsConsent()) {
  Sentry.init({
    dsn: DSN,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    sendDefaultPii: false,
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV || "development",
  });
}
