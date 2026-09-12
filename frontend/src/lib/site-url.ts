/**
 * The site's canonical origin — one constant for metadata, sitemap and robots.
 *
 * 2026-09-10: three files each hardcoded their own origin. The root layout
 * read NEXT_PUBLIC_SITE_URL (www in production, so canonical tags were right),
 * while sitemap.ts and robots.ts hardcoded the apex. The apex answers 307 to
 * www, so every <loc> in the sitemap and the robots `sitemap:`/`host:` lines
 * pointed at a redirect. The fallback is www for the same reason.
 */
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.pivoxquant.com";
