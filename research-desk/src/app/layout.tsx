import type { Metadata, Viewport } from "next";
import { getDomain } from "@/lib/research/domains";
import "./globals.css";

const domain = getDomain(undefined);

export const metadata: Metadata = {
  title: `${domain.label} 리서치 데스크`,
  description: domain.tagline,
};

export const viewport: Viewport = {
  themeColor: "#0c0b0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
