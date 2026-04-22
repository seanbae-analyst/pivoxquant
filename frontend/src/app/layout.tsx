import type { Metadata, Viewport } from "next";
import { Geist, JetBrains_Mono, Source_Serif_4 } from "next/font/google";
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

// Heading font = Geist (same family, tighter usage)
const geistHeading = Geist({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
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
  icons: {
    icon: [
      { url: "/icons/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: { url: "/icons/apple-touch-icon.png", sizes: "180x180" },
  },
  manifest: "/manifest.webmanifest",
  category: "finance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${geist.variable} ${geistHeading.variable} ${mono.variable} ${serif.variable} h-full antialiased`}
    >
      <head>
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <script
          dangerouslySetInnerHTML={{
            __html: `if(window.matchMedia('(display-mode: standalone)').matches){document.documentElement.classList.add('pwa-standalone');}`,
          }}
        />
        <link
          rel="stylesheet"
          as="style"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body className="min-h-full bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              fontFamily:
                'var(--font-sans), "Pretendard Variable", Pretendard, system-ui, sans-serif',
            },
          }}
        />
        <CookieConsent />
        <InstallPrompt />
      </body>
    </html>
  );
}
