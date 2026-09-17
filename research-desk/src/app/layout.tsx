import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "컨설팅 리서치 데스크",
  description: "시장 규모·경쟁 환경·산업 구조·사례 벤치마크·규제를 이슈 트리로 쪼개 근거를 모으고, 반증한 뒤, 출처가 달린 리서치 노트를 쓴다.",
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
