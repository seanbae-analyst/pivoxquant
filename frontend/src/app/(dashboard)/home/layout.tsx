import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home",
  description:
    "Your personalized investing dashboard — portfolio overview, equity curve, signals, and risk at a glance.",
  alternates: { canonical: "/home" },
  robots: { index: false, follow: false },
};

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return children;
}
