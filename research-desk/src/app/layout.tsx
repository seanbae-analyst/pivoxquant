import type { Metadata, Viewport } from "next";
import Link from "next/link";
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
      <body>
        <nav className="mx-auto flex max-w-6xl items-center gap-5 px-4 pt-4 text-sm text-dim">
          <Link href="/" className="hover:text-ink">질의응답</Link>
          <Link href="/research" className="hover:text-ink">리서치 데스크</Link>
          <span className="ml-auto text-xs text-faint">데이터 지식 베이스</span>
        </nav>
        {children}
      </body>
    </html>
  );
}
