import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-24 sm:px-6">
      <p className="font-mono text-xs tracking-[0.3em] text-faint">404</p>
      <h1 className="mt-4 font-serif text-4xl tracking-tight">여기엔 아무것도 없다</h1>
      <p className="mt-4 max-w-xl leading-relaxed text-dim">
        주소가 바뀌었거나, 아직 쓰지 않은 개념일 수 있다. 개념 지도에서 찾아보라.
      </p>
      <div className="mt-8 flex gap-3 text-sm">
        <Link href="/concepts" className="rounded border border-line px-3 py-1.5 text-ink hover:border-accent hover:text-accent">
          개념 지도
        </Link>
        <Link href="/" className="rounded border border-line px-3 py-1.5 text-dim hover:border-accent hover:text-accent">
          질의응답
        </Link>
      </div>
    </main>
  );
}
