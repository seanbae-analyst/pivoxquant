import Link from "next/link";
import { ConceptMap } from "@/components/concepts/concept-map";
import { Scene3D } from "@/components/concepts/three/scene-frame";
import { AREAS, conceptsInArea } from "@/lib/concepts/concepts";

export const metadata = { title: "데이터 개념 지도" };

export default function Page() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-16">
      <header className="mb-8 max-w-3xl">
        <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">데이터 개념 지도</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-dim">개념 하나를 글로만 읽으면 추상적이다. 여기서는 같은 데이터셋(온라인 쇼핑몰의 고객·주문 테이블) 위에서 모든 개념을 직접 만져 본다. 끌어서 돌려 보고, 막대를 눌러 보라.</p>
      </header>
      <Scene3D kind="galaxy" label="개념 12개와 그 사이의 관계" flat={<ConceptMap />} />
      <div className="mt-12 grid gap-8 border-t border-line pt-8 sm:grid-cols-2 lg:grid-cols-3">
        {AREAS.map((a) => (
          <section key={a.id}>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-faint">{a.label}</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-dim">{a.blurb}</p>
            <ul className="mt-3 space-y-2">
              {conceptsInArea(a.id).map((c) => (
                <li key={c.slug} className="leading-snug">
                  <Link href={`/concepts/${c.slug}`} className="text-[15px] text-ink underline-offset-4 hover:underline">{c.name}</Link>
                  <span className="ml-2 font-mono text-[11px] text-faint">{c.en}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      <section className="mt-12 rounded-xl border border-line bg-raised p-5">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-faint">앵커 데이터셋</h2>
        <p className="mt-2 text-[15px] leading-relaxed text-dim">customers_raw(고객, 이메일 평문) → orders_raw(주문, 통화 혼재) → stg_orders(KRW 환산) → fct_orders(취소 제외·지역 조인) → daily_revenue(일별 매출) → 매출 대시보드. 사이트의 모든 개념이 이 여섯 테이블 위에서 설명된다.</p>
      </section>
    </div>
  );
}
