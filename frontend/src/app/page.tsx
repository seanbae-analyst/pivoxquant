"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import LandingPage from "@/components/landing/landing-page";

function LoadingScreen() {
  return (
    <div className="min-h-[100dvh] flex flex-col items-center justify-center bg-white">
      <div className="w-10 h-10 rounded-xl bg-primary-gradient flex items-center justify-center mb-4 animate-pulse">
        <svg
          className="w-5 h-5 text-white"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
          <polyline points="16 7 22 7 22 13" />
        </svg>
      </div>
      <div className="w-32 h-1 rounded-full overflow-hidden bg-slate-100">
        <div className="h-full w-1/2 rounded-full bg-primary-gradient animate-shimmer-slide" />
      </div>
    </div>
  );
}

export default function Page() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/home");
    }
  }, [user, loading, router]);

  if (loading) return <LoadingScreen />;
  if (user) return <LoadingScreen />;

  return <LandingPage />;
}
