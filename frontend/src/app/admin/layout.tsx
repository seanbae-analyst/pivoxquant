"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Lock } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

/**
 * Admin-area layout. Gates the entire `/admin/*` tree on an allow-list
 * check performed server-side: we try `/api/admin/artifacts/list` and
 * treat any 404 / 401 / 403 as "not an admin → 404".
 *
 * Spec: "일반 유저는 404". We intentionally show a blank not-found screen
 * rather than revealing the route exists.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [gate, setGate] = useState<"checking" | "allowed" | "denied">("checking");

  useEffect(() => {
    // Not logged in → punt to /login rather than showing admin chrome.
    if (!authLoading && !user) {
      router.replace("/login");
      return;
    }
    if (!user) return;
    let alive = true;
    apiFetch(API.admin.artifactsList)
      .then(() => alive && setGate("allowed"))
      .catch((err: unknown) => {
        if (!alive) return;
        // Any failure — 401/403/404/network — means "not an admin".
        const is404 = err instanceof ApiError && err.status === 404;
        void is404;
        setGate("denied");
      });
    return () => {
      alive = false;
    };
  }, [user, authLoading, router]);

  if (authLoading || gate === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-400">
        Loading…
      </div>
    );
  }

  if (gate === "denied") {
    // Mimic the global not-found look — no hint that the route exists.
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-200 text-slate-500">
          <Lock className="h-5 w-5" />
        </div>
        <h1 className="mt-4 text-2xl font-semibold text-slate-900">404</h1>
        <p className="mt-1 text-sm text-slate-500">This page could not be found.</p>
        <Link
          href="/"
          className="mt-6 text-xs font-medium text-slate-500 underline-offset-4 hover:text-slate-900 hover:underline"
        >
          Return home
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur md:px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/home"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
            aria-label="Back to app"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex items-baseline gap-2">
            <span className="text-[11px] font-bold uppercase tracking-widest text-slate-900">
              Admin
            </span>
            <span className="text-[11px] text-slate-400">·</span>
            <span className="text-xs text-slate-500">Artifact Preview</span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="hidden truncate sm:inline">{user?.email}</span>
          <Link
            href="/home"
            className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-100"
          >
            Exit
          </Link>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
