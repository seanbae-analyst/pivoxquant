import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Assistant",
  description:
    "Chat with the PivoxQuant AI Assistant — analyze stocks, explain market data, and review your portfolio metrics.",
  alternates: { canonical: "/ai-chat" },
  robots: { index: false, follow: false },
};

export default function AiChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
