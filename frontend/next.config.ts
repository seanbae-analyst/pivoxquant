import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

// Backend API URL: Railway production or local development.
// NEXT_PUBLIC_API_URL is evaluated in next.config.ts at build time.
// On Vercel set NEXT_PUBLIC_API_URL (or RAILWAY_BACKEND_URL) to the Railway hostname.
// Local dev falls back to localhost:5050.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.VERCEL ? (process.env.RAILWAY_BACKEND_URL || "") : "http://localhost:5050");

const nextConfig: NextConfig = {
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 86400, // 24 h
    remotePatterns: [
      // FMP press release images, etc.
      { protocol: "https", hostname: "financialmodelingprep.com" },
      { protocol: "https", hostname: "**.financialmodelingprep.com" },
    ],
  },
  // Pin Turbopack workspace root to this dir so Hangul chars in parent path
  // (`취준/`) don't break char-boundary slicing in turbopack-core/ident.rs.
  // Also disambiguates against sibling /pivoxquant/frontend lockfile.
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
  async redirects() {
    // E2E P1 #3 (W6.3): `/dashboard` and `/dashboard/*` previously hit the
    // 404 page ("Nothing to observe here"). The Next.js App Router uses a
    // route group `(dashboard)/` whose URL segment is the empty string, so
    // the real paths are `/home`, `/market`, etc. — there is no literal
    // `/dashboard` route.
    //
    // External backlinks, ad campaigns, and SEO crawlers may still hit
    // `/dashboard` (or `/dashboard/home`, mirroring how most SaaS apps
    // structure their app shell). Issue a 308 permanent redirect at the
    // edge so we never serve a 404 for these paths.
    return [
      { source: "/dashboard", destination: "/mirror", permanent: true },
      // /home rendered <MirrorHome /> behind NEXT_PUBLIC_MIRROR_HOME=true — a
      // second door into the same room. The flag, the route and the unused
      // gallery surface behind it are all gone; /mirror is the single home.
      { source: "/home", destination: "/mirror", permanent: true },
      { source: "/dashboard/:path*", destination: "/:path*", permanent: true },
      // 2026-08-31 prune: 아래 표면들은 페이지가 물리적으로 삭제됐다. 북마크
      // ·외부링크·검색결과는 남아 있으므로 404 대신 살아있는 목적지로 보낸다.
      // (`/ai-chat` → `/ai` 였던 §101③ 격리 리다이렉트는 `/ai` 자체가 사라져
      //  목적지가 404 였다 — 아래 규칙이 그걸 대체한다.)
      //
      // 종목·분석 성격 → /home, 기록·행동 성격 → /mirror.
      { source: "/ai", destination: "/mirror", permanent: true },
      { source: "/ai/:path*", destination: "/mirror", permanent: true },
      { source: "/ai-chat", destination: "/mirror", permanent: true },
      { source: "/ai-chat/:path*", destination: "/mirror", permanent: true },
      { source: "/signals", destination: "/mirror", permanent: true },
      { source: "/signals/:path*", destination: "/mirror", permanent: true },
      { source: "/discover", destination: "/mirror", permanent: true },
      { source: "/discover/:path*", destination: "/mirror", permanent: true },
      { source: "/market", destination: "/mirror", permanent: true },
      { source: "/market/:path*", destination: "/mirror", permanent: true },
      // 2026-09-01 — 지원 챗봇 제거. 문의 접수가 유일한 지원 경로가 됐다.
      { source: "/support/chat", destination: "/support/contact", permanent: true },
      { source: "/watchlist", destination: "/portfolio", permanent: true },
      { source: "/watchlist/:path*", destination: "/portfolio", permanent: true },
      { source: "/detail/:path*", destination: "/portfolio", permanent: true },
      { source: "/risk", destination: "/mirror", permanent: true },
      { source: "/risk/:path*", destination: "/mirror", permanent: true },
      { source: "/growth", destination: "/mirror", permanent: true },
      { source: "/growth/:path*", destination: "/mirror", permanent: true },
      { source: "/companion", destination: "/journal", permanent: true },
      { source: "/companion/:path*", destination: "/journal", permanent: true },
      { source: "/reports", destination: "/journal", permanent: true },
      { source: "/reports/:path*", destination: "/journal", permanent: true },
      { source: "/alerts", destination: "/mirror", permanent: true },
      { source: "/alerts/:path*", destination: "/mirror", permanent: true },
      // 공개 마케팅 표면 — 랜딩으로.
      { source: "/features", destination: "/", permanent: true },
      { source: "/features/:path*", destination: "/", permanent: true },
      { source: "/methodology", destination: "/", permanent: true },
      { source: "/sample-reports", destination: "/", permanent: true },
      { source: "/sample-reports/:path*", destination: "/", permanent: true },
      { source: "/simulator/:path*", destination: "/", permanent: true },
      { source: "/mirror-preview", destination: "/", permanent: true },
      // 무료 출시 (DECISIONS.md ✅확정 2026-05-30: Stage 0 무료, 월구독
      // ⬛superseded). `/pricing` 결제/플랜 비교 페이지는 코드를 보존하되
      // URL 직접접근을 `/home` 으로 차단한다. 진입점 링크(nav/footer/dropdown/
      // upsell)는 별도로 hidden 처리. 백엔드 routes/billing.py 는 이미
      // require_business_registration 503 게이트로 보존됨.
      //
      // ⚠️ permanent:false (307) — ai-chat 격리(§101 법적 영구차단)와 달리
      // pricing 은 Stage 1 유료화 부활 가능성이 있어 브라우저 영구캐시(308)를
      // 피한다. 부활 = 이 두 줄 + sitemap/진입점 hidden 을 되돌리면 된다.
      { source: "/pricing", destination: "/mirror", permanent: false },
      { source: "/pricing/:path*", destination: "/mirror", permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          // 2026-05-02: Vercel CDN was caching /sw.js despite no-store
          // (observed `x-vercel-cache: HIT`, `age: 264`). Browser-level
          // Cache-Control alone doesn't reach the edge layer, so version
          // bumps (sp-v5 → sp-v6) took 5-10 min to propagate to
          // PWA-installed users. The CDN-Cache-Control + the explicit
          // Vercel variant tell the edge to skip its own cache while
          // s-maxage=0 covers any other shared cache between Vercel and
          // the user.
          {
            key: "Cache-Control",
            value: "public, max-age=0, s-maxage=0, must-revalidate",
          },
          { key: "CDN-Cache-Control", value: "no-store" },
          { key: "Vercel-CDN-Cache-Control", value: "no-store" },
          {
            key: "Content-Type",
            value: "application/javascript; charset=utf-8",
          },
        ],
      },
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            // 2026-05-10 (L4): added `interest-cohort=()` to opt out of
            // FLoC for any Chromium fork that still ships the cohort API.
            // Kept aligned with backend Permissions-Policy in security.py.
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), payment=(self), usb=(), magnetometer=(), gyroscope=(), accelerometer=(), interest-cohort=()",
          },
          {
            // 2026-05-15 (P1 verify-security finding): Vercel HTML
            // responses shipped no Content-Security-Policy header,
            // leaving the browser unable to enforce script/style/
            // connect-src restrictions. The Railway backend has its own
            // CSP (security.py) but the static HTML the user actually
            // loads from Vercel was unguarded — a real XSS guard gap on
            // the public landing surface. Added here so every Vercel
            // response carries CSP.
            //
            // Directive notes:
            // - `script-src` allows `'unsafe-inline'` for Next.js
            //   hydration markers and Sentry browser SDK boot snippet.
            //   Strict-CSP with nonces is a future refinement; current
            //   priority is closing the no-CSP gap before launch.
            // - `connect-src` covers Sentry ingest (event reporting)
            //   and `'self'` (Next.js rewrites proxy /api → Railway).
            // - `img-src` allows Google + Kakao avatar CDNs (OAuth
            //   profile photos render in the top-nav and profile page).
            // - `frame-ancestors 'none'` mirrors X-Frame-Options DENY.
            // - `object-src 'none'` blocks the Flash/PDF embed vector.
            // - `base-uri 'self'` blocks <base> tag injection redirect.
            // - `form-action 'self'` blocks form hijack to attacker URL.
            // - `upgrade-insecure-requests` forces https on any mixed
            //   resource.
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.ingest.sentry.io https://*.ingest.us.sentry.io",
              // jsdelivr MUST be allowed for the Pretendard Korean webfont
              // (layout.tsx <link>). Both this CSP and middleware.ts emit a
              // CSP header → the browser enforces the INTERSECTION, so a
              // missing jsdelivr here silently blocked Pretendard and dropped
              // Korean text to the system font (launch hardening 2026-05-24).
              "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
              "img-src 'self' data: blob: https://*.googleusercontent.com https://*.kakaocdn.net https://k.kakaocdn.net https://t1.kakaocdn.net",
              "font-src 'self' data: https://cdn.jsdelivr.net",
              "connect-src 'self' https://*.ingest.sentry.io https://*.ingest.us.sentry.io",
              // Stripe checkout iframe domains removed at Stage 0 (무료 출시 —
              // billing fully gated, no Stripe.js loads). Re-add
              // https://js.stripe.com + https://hooks.stripe.com here AND in
              // middleware.ts connect/frame-src to revive paid checkout (Stage 1).
              "frame-src 'self'",
              "frame-ancestors 'none'",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "upgrade-insecure-requests",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

// Source-map upload is opt-in via SENTRY_AUTH_TOKEN; without it the build
// still succeeds without symbol uploads. `silent: true` suppresses the
// "no auth token" notice on local builds. Runtime DSN gating still
// happens inside each sentry.*.config.ts.
export default withSentryConfig(nextConfig, {
  silent: true,
  sourcemaps: {
    deleteSourcemapsAfterUpload: true,
  },
});
