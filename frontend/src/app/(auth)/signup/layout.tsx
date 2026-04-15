import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign Up",
  description:
    "Create your PivoxQuant account — AI-powered quantitative investing for US and Korean stock markets.",
  alternates: { canonical: "/signup" },
};

export default function SignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
