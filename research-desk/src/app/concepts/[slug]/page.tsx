import Link from "next/link";
import { notFound } from "next/navigation";
import { AskInline } from "@/components/concepts/ask-inline";
import { ConceptMap } from "@/components/concepts/concept-map";
import { Interactive } from "@/components/concepts/interactive";
import { AREAS, CONCEPTS, conceptBySlug } from "@/lib/concepts/concepts";

export function generateStaticParams() {
  return CONCEPTS.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const c = conceptBySlug((await params).slug);
  return { title: c ? `${c.name} — 데이터 개념 지도` : "개념" };
}

function Block({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="mb-3 flex items-baseline gap-2 font-serif text-lg"><span className="font-mono text-xs text-faint">{n}</span>{title}</h2>
      {children}
    </section>
  );
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const c = conceptBySlug(slug);
  if (!c) notFound();
  const area = AREAS.find((a) => a.id === c.area)!;
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:py-10">
      <p className="text-xs text-faint"><Link href="/concepts" className="hover:text-ink">개념 지도</Link> / {area.label}</p>
      <h1 className="mt-1 font-serif text-3xl tracking-tight">{c.name} <span className="text-base text-faint">{c.en}</span></h1>

      <Block n={1} title="한 문장 정의">
        <p className="text-[15px] leading-relaxed text-ink">{c.definition}</p>
        <p className="mt-2 text-sm text-dim"><span className="text-faint">앵커 데이터셋에서는 — </span>{c.onAnchor}</p>
      </Block>

      {c.interactive && (
        <Block n={2} title="만져보기">
          <div className="rounded-lg border border-line bg-raised p-4"><Interactive id={c.interactive} slug={c.slug} /></div>
        </Block>
      )}

      <Block n={3} title="어디에 놓이나">
        <ConceptMap focus={c.slug} />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="text-xs uppercase tracking-widest text-faint">이웃</h3>
            <ul className="mt-1 space-y-1 text-sm">
              {c.neighbors.map((n) => {
                const nc = conceptBySlug(n.slug);
                return nc ? <li key={n.slug}><Link href={`/concepts/${n.slug}`} className="text-ink underline-offset-4 hover:underline">{nc.name}</Link><span className="text-dim"> — {n.relation}</span></li> : null;
              })}
            </ul>
          </div>
          <div>
            <h3 className="text-xs uppercase tracking-widest text-faint">자주 헷갈리는 것</h3>
            <ul className="mt-1 space-y-1 text-sm">
              {c.confusedWith.map((x) => {
                const xc = conceptBySlug(x.slug);
                return xc ? <li key={x.slug}><Link href={`/concepts/${x.slug}`} className="text-ink underline-offset-4 hover:underline">{xc.name}</Link><span className="text-dim"> — {x.howDiffer}</span></li> : null;
              })}
            </ul>
          </div>
        </div>
      </Block>

      <Block n={4} title="실무 장면">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-faint"><th className="pb-1 pr-3 font-normal">도구</th><th className="pb-1 font-normal">어디에 나타나나</th></tr></thead>
          <tbody>
            {c.practice.map((p) => (
              <tr key={p.tool} className="border-t border-line align-top">
                <td className="py-2 pr-3 text-ink">{p.tool}</td>
                <td className="py-2 text-dim">{p.where}{p.note && <span className="block text-xs text-faint">{p.note}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-faint">도구 화면과 기능은 버전마다 바뀐다. 최신 상태는 아래 근거(공식 문서 수집본)에서 확인한다.</p>
      </Block>

      <Block n={5} title="근거와 묻기">
        <AskInline question={c.askQuestion} />
        <p className="mt-2 text-xs text-faint">더 깊게 조사하려면 <Link href="/research" className="underline">리서치 데스크</Link>에서 브리프를 넣는다.</p>
      </Block>
    </div>
  );
}
