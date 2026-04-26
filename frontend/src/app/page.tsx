"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import LandingV2 from "@/components/landing/landing-v2";

function LoadingScreen() {
  return (
    <div
      className="min-h-[100dvh] flex flex-col items-center justify-center"
      style={{ backgroundColor: "var(--pq-ink)" }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 animate-pulse"
        style={{ backgroundColor: "var(--pq-bronze)" }}
      >
        <svg
          className="w-5 h-5"
          style={{ color: "var(--pq-ink)" }}
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
      <div
        className="w-32 h-1 rounded-full overflow-hidden"
        style={{ backgroundColor: "rgba(245, 240, 232, 0.08)" }}
      >
        <div
          className="h-full w-1/2 rounded-full animate-shimmer-slide"
          style={{ backgroundColor: "var(--pq-bronze-light)" }}
        />
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

  return <LandingV2 />;
}
