import type { Metadata } from "next";

/* /pre-trade/door has `"use client"` in page.tsx, blocking metadata export —
 * same split as /pre-trade/layout.tsx. */
export const metadata: Metadata = {
  title: "문 앞",
  description: "증권 앱을 열 때 뭘 하러 왔는지 한 줄 남깁니다.",
  robots: { index: false, follow: false },
};

export default function DoorLayout({ children }: { children: React.ReactNode }) {
  return children;
}
