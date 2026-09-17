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

function Block({ n, title, children, wide }: { n: number; title: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <section className="mt-16 border-t border-line pt-8">
      <h2 className="mb-5 flex items-center gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line font-mono text-[11px] text-accent">{n}</span>
        <span className="font-serif text-xl tracking-tight">{title}</span>
      </h2>
      <div className={wide ? "" : "max-w-3xl"}>{children}</div>
    </section>
  );
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const c = conceptBySlug(slug);
  if (!c) notFound();
  const area = AREAS.find((a) => a.id === c.area)!;
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
      <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-faint">
        <Link href="/concepts" className="hover:text-ink">개념 지도</Link> <span className="mx-1.5">/</span> {area.label}
      </p>
      <h1 className="mt-3 font-serif text-4xl leading-tight tracking-tight sm:text-5xl">{c.name}</h1>
      <p className="mt-1.5 font-mono text-sm text-faint">{c.en}</p>

      <Block n={1} title="한 문장 정의">
        <p className="text-lg leading-relaxed text-ink">{c.definition}</p>
        <p className="mt-4 border-l-2 border-accent/50 pl-4 text-[15px] leading-relaxed text-dim">
          <span className="text-faint">앵커 데이터셋에서는 — </span>
          {c.onAnchor}
        </p>
      </Block>

      {c.interactive && (
        <Block n={2} title="만져보기" wide>
          <div className="rounded-xl border border-line bg-raised p-4 sm:p-5">
            <Interactive id={c.interactive} slug={c.slug} />
          </div>
        </Block>
      )}

      <Block n={3} title="어디에 놓이나" wide>
        <ConceptMap focus={c.slug} />
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.2em] text-faint">이웃</h3>
            <ul className="mt-2 space-y-2 text-[15px] leading-relaxed">
              {c.neighbors.map((n) => {
                const nc = conceptBySlug(n.slug);
                return nc ? <li key={n.slug}><Link href={`/concepts/${n.slug}`} className="text-ink underline-offset-4 hover:underline">{nc.name}</Link><span className="text-dim"> — {n.relation}</span></li> : null;
              })}
            </ul>
          </div>
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.2em] text-faint">자주 헷갈리는 것</h3>
            <ul className="mt-2 space-y-2 text-[15px] leading-relaxed">
              {c.confusedWith.map((x) => {
                const xc = conceptBySlug(x.slug);
                return xc ? <li key={x.slug}><Link href={`/concepts/${x.slug}`} className="text-ink underline-offset-4 hover:underline">{xc.name}</Link><span className="text-dim"> — {x.howDiffer}</span></li> : null;
              })}
            </ul>
          </div>
        </div>
      </Block>

      <Block n={4} title="실무 장면" wide>
        <table className="w-full max-w-3xl text-[15px]">
          <thead>
            <tr className="text-left font-mono text-[11px] uppercase tracking-[0.18em] text-faint">
              <th className="pb-2 pr-6 font-normal">도구</th>
              <th className="pb-2 font-normal">어디에 나타나나</th>
            </tr>
          </thead>
          <tbody>
            {c.practice.map((p) => (
              <tr key={p.tool} className="border-t border-line align-top">
                <td className="whitespace-nowrap py-3 pr-6 text-ink">{p.tool}</td>
                <td className="py-3 leading-relaxed text-dim">
                  {p.where}
                  {p.note && <span className="mt-0.5 block text-[13px] text-faint">{p.note}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-[13px] text-faint">도구 화면과 기능은 버전마다 바뀐다. 최신 상태는 아래 근거(공식 문서 수집본)에서 확인한다.</p>
      </Block>

      <Block n={5} title="근거와 묻기">
        <AskInline question={c.askQuestion} />
        <p className="mt-3 text-[13px] text-faint">
          더 깊게 조사하려면 <Link href="/research" className="text-accent underline underline-offset-4">리서치 데스크</Link>에서 브리프를 넣는다.
        </p>
      </Block>
    </div>
  );
}
