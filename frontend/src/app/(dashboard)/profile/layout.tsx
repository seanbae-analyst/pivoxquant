import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Profile",
  description:
    "Your identity, declared persona, observed rolling window, and Living CFO controls.",
  alternates: { canonical: "/profile" },
  robots: { index: false, follow: false },
};

export default function ProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
