"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A11.96 11.96 0 0 0 1 12c0 1.94.46 3.77 1.18 5.07l3.66-2.98z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function KakaoIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3C6.48 3 2 6.58 2 10.94c0 2.8 1.86 5.27 4.66 6.67-.15.53-.96 3.41-.99 3.63 0 0-.02.16.08.22.1.06.23.01.23.01.3-.04 3.5-2.3 4.05-2.67.62.09 1.27.14 1.97.14 5.52 0 10-3.58 10-7.94S17.52 3 12 3z"
        fill="#191919"
      />
    </svg>
  );
}

export default function LoginPageV1() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/home");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex flex-col items-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-[var(--sp-accent)]" />
      </div>
    );
  }

  if (user) return null;

  return (
    <div className="flex flex-col items-center">
      {/* Logo */}
      <div className="mb-8 flex flex-col items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 border border-accent shadow-lg shadow-accent/20">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
            <polyline points="16 7 22 7 22 13" />
          </svg>
        </div>
        <span className="text-lg font-semibold text-slate-900">PivoxQuant</span>
      </div>

      {/* Heading */}
      <h1 className="text-center text-2xl font-bold tracking-tight text-slate-900">
        다시 오셨군요
      </h1>
      <p className="mt-2 text-center text-sm text-slate-500">
        계정에 로그인하세요
      </p>

      {/* OAuth Buttons */}
      <div className="mt-8 flex w-full flex-col gap-3">
        <a
          href={API.auth.google}
          className="flex w-full items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition-all duration-200 hover:border-slate-300 hover:bg-slate-50 hover:shadow-sm active:scale-[0.98]"
        >
          <GoogleIcon />
          Google로 계속하기
        </a>

        <a
          href={API.auth.kakao}
          className="flex w-full items-center justify-center gap-3 rounded-xl border border-[#FEE500]/20 bg-[#FEE500] px-4 py-3 text-sm font-medium text-[#191919] transition-all duration-200 hover:bg-[#FFEB3B] hover:shadow-sm active:scale-[0.98]"
        >
          <KakaoIcon />
          카카오로 계속하기
        </a>
      </div>

      {/* Divider */}
      <div className="my-6 flex w-full items-center gap-3">
        <div className="h-px flex-1 bg-slate-200" />
        <span className="text-xs text-slate-400">또는</span>
        <div className="h-px flex-1 bg-slate-200" />
      </div>

      {/* Switch to signup */}
      <p className="text-center text-sm text-slate-500">
        계정이 없으신가요?{" "}
        <Link
          href="/signup"
          className="font-medium text-[var(--sp-accent)] hover:text-[var(--sp-accent-hover)] transition-colors"
        >
          회원가입
        </Link>
      </p>

      {/* Legal footer */}
      <p className="mt-8 text-center text-xs leading-relaxed text-slate-400">
        계속하면{" "}
        <Link href="/terms" className="underline hover:text-slate-600 transition-colors">
          이용약관
        </Link>{" "}
        및{" "}
        <Link href="/privacy" className="underline hover:text-slate-600 transition-colors">
          개인정보처리방침
        </Link>
        에 동의하게 됩니다.
      </p>
    </div>
  );
}
