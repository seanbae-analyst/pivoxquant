import Link from "next/link";
import { ConceptMap } from "@/components/concepts/concept-map";
import { AREAS, conceptsInArea } from "@/lib/concepts/concepts";

export const metadata = { title: "데이터 개념 지도" };

export default function Page() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
      <header className="mb-6">
        <h1 className="font-serif text-2xl tracking-tight">데이터 개념 지도</h1>
        <p className="mt-1 text-sm text-dim">개념 하나를 글로만 읽으면 추상적이다. 여기서는 같은 데이터셋(온라인 쇼핑몰의 고객·주문 테이블) 위에서 모든 개념을 직접 만져 본다.</p>
      </header>
      <ConceptMap />
      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {AREAS.map((a) => (
          <section key={a.id}>
            <h2 className="text-xs uppercase tracking-widest text-faint">{a.label}</h2>
            <p className="mt-0.5 text-xs text-dim">{a.blurb}</p>
            <ul className="mt-2 space-y-1">
              {conceptsInArea(a.id).map((c) => (
                <li key={c.slug}>
                  <Link href={`/concepts/${c.slug}`} className="text-sm text-ink underline-offset-4 hover:underline">{c.name}</Link>
                  <span className="ml-2 text-xs text-faint">{c.en}</span>
                </li>
              ))}
              {conceptsInArea(a.id).length === 0 && <li className="text-xs text-faint">준비 중</li>}
            </ul>
          </section>
        ))}
      </div>
      <section className="mt-10 rounded-lg border border-line p-4 text-sm">
        <h2 className="text-xs uppercase tracking-widest text-faint">앵커 데이터셋</h2>
        <p className="mt-1 text-dim">customers_raw(고객, 이메일 평문) → orders_raw(주문, 통화 혼재) → stg_orders(KRW 환산) → fct_orders(취소 제외·지역 조인) → daily_revenue(일별 매출) → 매출 대시보드. 사이트의 모든 개념이 이 여섯 테이블 위에서 설명된다.</p>
      </section>
    </div>
  );
}
