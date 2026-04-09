import type { Metadata, Viewport } from "next";
import { Geist, IBM_Plex_Mono } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import { SwInit } from "@/components/pwa/sw-init";
import { InAppBrowserGuard } from "@/components/pwa/in-app-browser-guard";
import "./globals.css";

const geist = Geist({
  variable: "--font-geist-heading",
  subsets: ["latin"],
});

const ibmMono = IBM_Plex_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const viewport: Viewport = {
  themeColor: "#050508",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: "StockPilot — AI Quant Advisor",
  description: "AI-powered quantitative investment advisor with adaptive quant engine",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "StockPilot",
  },
  formatDetection: {
    telephone: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${geist.variable} ${ibmMono.variable} h-full antialiased`}>
      <head>
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <link
          rel="stylesheet"
          as="style"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body
        className="min-h-full bg-background text-foreground"
        style={{ fontFamily: '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif' }}
      >
        <InAppBrowserGuard />
        <SwInit />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
