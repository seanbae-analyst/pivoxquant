import type { Metadata, Viewport } from "next";
import {
  Geist,
  JetBrains_Mono,
  Source_Serif_4,
  Playfair_Display,
} from "next/font/google";
import { headers } from "next/headers";
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

// Editorial serif for report surfaces (Morning Brief, Weekly Memo, 10-K Personal)
const serif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
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

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://pivoxquant.com";
const SITE_NAME = "PivoxQuant";
// Korean-first positioning — the CFO framing is the marketing spear, so the
// default title + OG card speak in that voice. English sub-copy kept in the
// description for US previews (LinkedIn, Slack).
const SITE_TITLE_KR = `${SITE_NAME} — 당신은 당신 포트폴리오의 CFO`;
const SITE_DESCRIPTION_KR =
  "ChatGPT는 물어야 답한다. PivoxQuant는 자는 동안 만든다. 매주 일요일 당신의 포트폴리오 리포트가 도착합니다.";
const SITE_DESCRIPTION_OG =
  "전속 리서치 데스크가 매주 당신의 투자 리포트를 씁니다.";
const SITE_DESCRIPTION_TWITTER =
  "당신은 당신 포트폴리오의 CFO. 리포트는 저희가 씁니다.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE_KR,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION_KR,
  applicationName: SITE_NAME,
  keywords: [
    "AI 주식",
    "AI 퀀트",
    "주식 분석",
    "포트폴리오 관리",
    "AI 리서치 툴",
    "퀀트 투자",
    "리스크 분석",
    "VaR",
    "코스피",
    "코스닥",
    "stock analysis",
    "AI investing",
    "quantitative finance",
    "portfolio risk",
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
  return (
    <html
      lang="ko"
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
        <link
          rel="preload"
          as="style"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
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
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:bg-[var(--pq-bronze)] focus:text-[var(--pq-ink)] focus:px-3 focus:py-2 focus:rounded-sm focus:font-mono focus:text-[11px] focus:uppercase focus:tracking-[0.18em] focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-[var(--pq-bronze)]"
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
