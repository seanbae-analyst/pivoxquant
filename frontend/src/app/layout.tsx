import type { Metadata, Viewport } from "next";
import {
  Geist,
  JetBrains_Mono,
  Source_Serif_4,
  Playfair_Display,
} from "next/font/google";
import { cookies, headers } from "next/headers";
import { Toaster } from "sonner";
import "./globals.css";
import { Providers } from "./providers";
import { CookieConsent } from "@/components/ui/cookie-consent";
import { InstallPrompt } from "@/components/pwa/install-prompt";

// Geist — latin UI/headings. Pretendard (CDN link below) handles Korean.
const geist = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

// Tabular-nums mono for prices, ratios, tickers
const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

// Editorial serif for long-form reading surfaces (landing, /docs, terms, privacy).
// Was "report surfaces (Morning Brief, Weekly Memo, 10-K Personal)" — those
// artifacts were deleted in the 2026-08-31 prune; the font is still in use.
// Design audit 2026-06-10 (P2): 75 call sites use `font-serif italic`, but
// only the normal style was loaded — every editorial italic (brand wordmark,
// deposition quotes, rationale pull-quotes) rendered as a browser-synthesized
// oblique. Load the real italic cuts (build-time fetch, ~tens of KB).
const serif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

// Display serif — high-contrast Didone-adjacent face used only on the
// landing hero H1, splash wordmark, and persona hero name. Kept to three
// weights (500/600/700) + italic to keep the font payload small; Next.js
// fetches at build time so unused weights never reach the client.
const display = Playfair_Display({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

// Vantablack theme-color matches manifest + avoids the iOS Safari white
// notch flash when launched from the home screen. viewportFit="cover" is
// required so env(safe-area-inset-*) is non-zero on iPhone notch/Dynamic Island.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#050505" },
    { media: "(prefers-color-scheme: dark)", color: "#050505" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
};

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://pivoxquant.com";
const SITE_NAME = "PivoxQuant";
// Korean-first positioning.
//
// ⚠️ 2026-09-02: this block used to read "당신은 당신 포트폴리오의 CFO / 리포트는
// 저희가 씁니다 / 매주 일요일 리포트가 도착합니다 / 자는 동안 만든다". Every one of
// those sentences described the artifact-report pipeline and the AI writer, and
// BOTH were deleted (artifacts in the 8-31 prune, `services/ai/` on 2026-09-01).
// It was the most-seen copy on the product — the browser tab title and the OG
// card on every share — and it promised a product that no longer exists.
//
// 2026-09-10 (CEO): the CFO concept comes back as the umbrella, but only the
// true half of it. What was deleted in 2026-09-02 was never the metaphor — it
// was "리포트는 저희가 씁니다 / 매주 일요일 리포트가 도착합니다", which described
// an artifact pipeline that no longer exists. That stays deleted.
//
// The half that is true is the one that actually describes a CFO: a CFO does
// not pick the investments. A CFO keeps the books, closes the period, and puts
// the numbers back in front of whoever decides. That is exactly 멈춤 → 기록 →
// 거울, so the concept sits above the loop rather than replacing it.
//
// Nothing is generated for the user; the user's own record is the material.
// Keep it that way — the moment this copy promises output, it is false again.
const SITE_TITLE_KR = `${SITE_NAME} — 당신 포트폴리오의 CFO`;
const SITE_DESCRIPTION_KR =
  // The sentence DENIES giving the thing FORBIDDEN_DIRECTIVE_TERMS bans, which
  // means it has to quote that word in the negative. The marker is the
  // documented escape (.githooks/pre-commit) — the guard scans added lines and
  // cannot read a negation.
  "CFO 는 종목을 고르지 않습니다. 장부를 지키고, 결산해서, 숫자를 결정권자 앞에 돌려놓습니다. 사기 전에 한 번 멈춰 이유를 적고, 그 기록이 몇 주 뒤 당신의 실제 매매 습관을 되비춥니다. 점수도 추천도 없습니다. 클로즈드 베타 무료."; // legal-ok
const SITE_DESCRIPTION_OG =
  "당신 포트폴리오의 CFO. 스스로 선언한 투자자와, 거래가 말해주는 투자자 사이의 간극을 봅니다.";
const SITE_DESCRIPTION_TWITTER =
  "당신 포트폴리오의 CFO. 멈춤 · 기록 · 거울.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE_KR,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION_KR,
  applicationName: SITE_NAME,
  // 2026-09-02: "AI 주식 / AI 퀀트 / AI 리서치 툴 / 퀀트 투자 / VaR" 를 뺐다.
  // 런타임에 AI 호출이 0회이고(`services/ai/` 삭제) `services/quant/` 도 없다 —
  // 검색 키워드는 마케팅 희망이 아니라 제품 설명이어야 한다. 남긴 것은 실제로
  // 하는 일(기록·회고·습관)과 시장 범위(코스피/코스닥/미국주식)뿐.
  keywords: [
    "매매일지",
    "투자 기록",
    "투자 회고",
    "매매 습관",
    "포트폴리오 기록",
    "투자 심리",
    "코스피",
    "코스닥",
    "미국주식",
    "trading journal",
    "investment reflection",
    "trading habits",
    "portfolio journal",
  ],
  authors: [{ name: "PivoxQuant" }],
  creator: "PivoxQuant",
  publisher: "PivoxQuant",
  appleWebApp: {
    capable: true,
    // black-translucent lets the Vantablack background extend under the
    // iOS status bar when installed, matching the editorial dark vibe.
    statusBarStyle: "black-translucent",
    title: SITE_NAME,
  },
  other: {
    "mobile-web-app-capable": "yes",
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "apple-mobile-web-app-title": SITE_NAME,
  },
  formatDetection: {
    telephone: false,
    email: false,
    address: false,
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    alternateLocale: ["en_US"],
    url: SITE_URL,
    siteName: SITE_NAME,
    title: SITE_TITLE_KR,
    description: SITE_DESCRIPTION_OG,
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: SITE_NAME,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: SITE_DESCRIPTION_TWITTER,
    images: ["/opengraph-image"],
  },
  alternates: {
    canonical: SITE_URL,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  // P0 fix (2026-05-09 release-prep audit): icon URLs previously pointed at
  // /icons/icon-32.png and /icons/icon-192.png — neither file existed in
  // public/icons/ so every browser tab fetched a 404 for the favicon. The
  // actual files on disk are favicon-48x48.png + icon-192x192.png; aligned
  // the metadata to the real filenames.
  icons: {
    icon: [
      { url: "/icons/favicon-48x48.png", sizes: "48x48", type: "image/png" },
      { url: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512x512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: { url: "/icons/apple-touch-icon.png", sizes: "180x180" },
  },
  manifest: "/manifest.webmanifest",
  category: "finance",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // CSP nonce — injected by middleware.ts as `x-nonce`. Manually authored
  // inline <script> tags must carry this nonce so the strict-dynamic CSP
  // (no 'unsafe-inline' in prod) doesn't block them.
  //
  // Defense-in-depth (2026-05-03 P0 fix): wrap `headers()` in try/catch.
  // Next.js may invoke this server component in contexts where the dynamic
  // headers() API throws (e.g. RSC prefetch render before middleware ran,
  // edge cases during static optimisation). A throw here propagates as a
  // production-wide 500 across every page that mounts the root layout.
  // Falling back to `undefined` is safe: the nonce is only consumed by the
  // inline standalone-mode detection script below, which is non-critical
  // (CSP simply blocks it without the nonce — display-mode class won't be
  // applied, but the rest of the page renders).
  let nonce: string | undefined;
  try {
    nonce = (await headers()).get("x-nonce") ?? undefined;
  } catch {
    nonce = undefined;
  }
  // SSR locale — read sp_locale cookie so <html lang> matches the user's
  // active language (SEO + screen-reader correctness). LocaleProvider on
  // the client honours the same cookie, so SSR and CSR stay in lockstep.
  let htmlLang: "ko" | "en" = "ko";
  try {
    const cookieStore = await cookies();
    const value = cookieStore.get("sp_locale")?.value;
    if (value === "en") htmlLang = "en";
  } catch {
    htmlLang = "ko";
  }
  return (
    <html
      lang={htmlLang}
      className={`${geist.variable} ${mono.variable} ${serif.variable} ${display.variable} h-full antialiased`}
    >
      <head>
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        {/* Preconnect to the Pretendard CDN so the font CSS + woff2 fetches
            start their TCP + TLS handshakes in parallel with the HTML parse.
            Saves ~300-500 ms on first load (measured via Lighthouse mobile 3G).
            `dns-prefetch` is a cheap fallback for browsers that ignore
            preconnect (older Safari, some bots). */}
        <link
          rel="preconnect"
          href="https://cdn.jsdelivr.net"
          crossOrigin="anonymous"
        />
        <link rel="dns-prefetch" href="https://cdn.jsdelivr.net" />
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: `if(window.matchMedia('(display-mode: standalone)').matches){document.documentElement.classList.add('pwa-standalone');}`,
          }}
        />
        {/* SEO/Performance audit (2026-05-09): the previous link was just a
            stylesheet (`as="style"` without `rel="preload"` does nothing).
            Hint the browser to preload the CSS in parallel with the rest
            of the head, then load it as a regular stylesheet. The KR woff2
            payload then starts its handshake earlier — measurably shorter
            FOIT on the first paint of any page above the fold. */}
        {/* 2026-05-17 perf P1: the preload + stylesheet pair MUST share
            the same CORS mode or the browser treats them as distinct
            resources, discards the preload, and re-fetches the CSS on
            every first paint (double network round-trip → render-blocking
            delay). Adding `crossOrigin="anonymous"` to the stylesheet
            link so the preload is actually reused. */}
        <link
          rel="preload"
          as="style"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
          crossOrigin="anonymous"
        />
        {/* SEO audit (2026-05-09): JSON-LD Organization structured data so
            Google Knowledge Graph can resolve the brand entity. The site
            isn't yet listed; declaring this gives the crawler the canonical
            wordmark when it's indexed. sameAs (GitHub) intentionally omitted
            during private beta — see FINDING-LAND-006. */}
        {/*
         * Wave C-2 SEO (2026-05-17): JSON-LD url/logo previously hard-coded
         * to https://pivoxquant.com — created a mismatch risk if SITE_URL
         * env (e.g. www.pivoxquant.com or preview domains) ever diverged.
         * Switched to SITE_URL so the Organization entity always matches the
         * site's actual canonical (mirrors metadataBase + alternates.canonical
         * + sitemap host + robots.host — single source of truth).
         */}
        <script
          type="application/ld+json"
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Organization",
              name: SITE_NAME,
              url: SITE_URL,
              logo: `${SITE_URL}/icons/icon-512x512.png`,
              description:
                "Observational quant research tool. Informational only — not investment advice.",
            }),
          }}
        />
      </head>
      <body className="min-h-full bg-background text-foreground antialiased">
        {/*
         * Skip link — WCAG 2.4.1 (Bypass Blocks, Level A). Visually hidden
         * until keyboard-focused, then jumps to <main id="main-content">
         * mounted by DashboardLayout / page-level <main> elements.
         * Bronze chip on Vantablack matches design system v3 tokens.
         */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:bg-[var(--pq-bronze)] focus:text-[var(--pq-ink)] focus:px-3 focus:py-2 focus:rounded-sm focus:font-mono focus:text-pq-mono-sm focus:uppercase focus:tracking-[0.18em] focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-[var(--pq-bronze)]"
        >
          Skip to main content
        </a>
        {/* CookieConsent / InstallPrompt sit INSIDE <Providers> so that
            useT() / useLocale() resolve against LocaleProvider. If mounted
            as body-level siblings they fell back to the default context
            value (t = identity), causing raw i18n keys like
            "cookieConsent.message" to render in the cookie banner. */}
        <Providers>
          {children}
          <CookieConsent />
          <InstallPrompt />
        </Providers>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              fontFamily:
                'var(--font-sans), "Pretendard Variable", Pretendard, system-ui, sans-serif',
            },
          }}
        />
      </body>
    </html>
  );
}
