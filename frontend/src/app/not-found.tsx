import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-white text-center p-8">
      <h1 className="text-7xl font-bold text-slate-900 mb-2 tabular-nums">
        404
      </h1>
      <p className="text-xl text-slate-500 mb-8">
        페이지를 찾을 수 없습니다
      </p>
      <Link
        href="/"
        className="px-6 py-3 rounded-full bg-slate-900 text-white font-semibold text-sm transition-all duration-200 hover:bg-slate-800 active:scale-[0.97]"
      >
        홈으로 이동
      </Link>
    </div>
  );
}
