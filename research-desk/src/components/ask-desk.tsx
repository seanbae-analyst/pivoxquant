"use client";

/**
 * 질의응답 화면 — 질문 하나, 인용 달린 답, 출처 목록, 지식 베이스 현황.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { askStream } from "@/lib/ask-client";
import type { AnswerSource, AskEvent } from "@/lib/kb/types";

interface Stats {
  ok: boolean;
  configured?: { ok: boolean; missing: string[] };
  backend?: string;
  docs?: number;
  chunks?: number;
  sources?: Array<{ sourceId: string; docs: number; chunks: number; lastFetchedAt: string | null }>;
  error?: string;
}

interface Run {
  status: string;
  retrieved: number | null;
  text: string;
  sources: AnswerSource[] | null;
  grounded: boolean | null;
  error: string | null;
}
const EMPTY: Run = { status: "", retrieved: null, text: "", sources: null, grounded: null, error: null };

function reduce(r: Run, ev: AskEvent): Run {
  switch (ev.type) {
    case "status":
      return { ...r, status: ev.message };
    case "retrieved":
      return { ...r, retrieved: ev.count };
    case "token":
      return { ...r, text: r.text + ev.text };
    case "citation":
      return { ...r, text: r.text + ` [${ev.n}]` };
    case "done":
      return { ...r, sources: ev.sources, grounded: ev.grounded, status: "" };
    case "error":
      return { ...r, error: ev.message, status: "" };
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" });
}

const EXAMPLES = [
  "OpenMetadata 와 DataHub 의 컬럼 수준 리니지는 각각 어디까지 자동으로 뽑히나?",
  "dbt 테스트와 Great Expectations 를 같이 쓸 때 품질 규칙은 어디에 두는 게 맞나?",
  "Iceberg 와 Delta Lake 의 스키마 진화 지원 범위 차이는?",
  "AI 학습용으로 데이터를 준비할 때 데이터 계약(data contract)은 어떤 역할을 하나?",
];

export function AskDesk() {
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<Run>(EMPTY);
  const [stats, setStats] = useState<Stats | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/kb/stats")
      .then((r) => r.json())
      .then((s: Stats) => {
        if (alive) setStats(s);
      })
      .catch(() => {
        if (alive) setStats({ ok: false, error: "현황을 못 읽었다." });
      });
    return () => {
      alive = false;
    };
  }, []);

  const ask = useCallback(
    async (q?: string) => {
      const text = (q ?? question).trim();
      if (!text || running) return;
      if (q) setQuestion(q);
      const controller = new AbortController();
      abortRef.current = controller;
      setRunning(true);
      setRun({ ...EMPTY, status: "연결 중" });
      try {
        await askStream(text, (ev) => setRun((r) => reduce(r, ev)), controller.signal);
      } catch (err) {
        setRun((r) => ({ ...r, error: controller.signal.aborted ? "중단했다." : err instanceof Error ? err.message : String(err), status: "" }));
      } finally {
        setRunning(false);
        abortRef.current = null;
      }
    },
    [question, running],
  );

  const empty = stats?.ok && (stats.chunks ?? 0) === 0;
  const lastFetched = useMemo(() => {
    const dates = (stats?.sources ?? []).map((s) => s.lastFetchedAt).filter((d): d is string => !!d).sort();
    return dates.length ? dates[dates.length - 1] : null;
  }, [stats]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:py-10">
      <header className="mb-6">
        <h1 className="font-serif text-2xl tracking-tight">데이터 지식 베이스에 묻기</h1>
        <p className="mt-1 text-sm text-dim">수집해 둔 공식 문서·표준·엔지니어링 블로그 안에서만 답하고, 문장마다 출처를 단다. 없으면 없다고 말한다.</p>
        <p className="mt-2 text-xs text-faint">
          {stats === null
            ? "현황 읽는 중"
            : !stats.ok
              ? `현황 오류: ${stats.error}`
              : `문서 ${stats.docs} · 조각 ${stats.chunks} · 출처 ${stats.sources?.length ?? 0} · 최근 수집 ${fmtDate(lastFetched)} · 저장소 ${stats.backend}`}
          {stats?.configured && !stats.configured.ok && ` · 서버 키 없음: ${stats.configured.missing.join(", ")}`}
        </p>
      </header>

      {empty && (
        <div className="mb-6 rounded-lg border border-line bg-raised p-4 text-sm">
          <p className="text-ink">아직 수집된 문서가 없다.</p>
          <p className="mt-1 text-dim">
            수집 대상은 <code className="font-mono text-xs">kb/sources.yaml</code> 에 있다. 터미널에서 아래를 돌리면 문서를 긁어 조각내고 임베딩해 저장한다.
          </p>
          <pre className="mt-2 overflow-x-auto rounded bg-bg p-2 font-mono text-xs text-dim">npm run ingest -- --dry-run{"\n"}npm run ingest</pre>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
        className="rounded-lg border border-line bg-raised p-3"
      >
        <label htmlFor="q" className="sr-only">
          질문
        </label>
        <textarea
          id="q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void ask();
          }}
          rows={2}
          maxLength={1000}
          disabled={running}
          placeholder="예: 데이터 카탈로그에서 리니지를 자동으로 뽑으려면 어떤 커넥터가 필요한가?"
          className="w-full resize-y bg-transparent text-[15px] leading-relaxed outline-none placeholder:text-faint disabled:opacity-60"
        />
        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="text-xs text-faint">⌘/Ctrl + Enter</span>
          {running ? (
            <button type="button" onClick={() => abortRef.current?.abort()} className="rounded border border-line px-3 py-1.5 text-sm text-dim hover:text-ink">
              중단
            </button>
          ) : (
            <button type="submit" disabled={!question.trim()} className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-bg disabled:opacity-40">
              묻기
            </button>
          )}
        </div>
      </form>

      {!run.text && !running && (
        <ul className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <li key={ex}>
              <button type="button" onClick={() => void ask(ex)} className="rounded-full border border-line px-3 py-1 text-xs text-dim hover:text-ink">
                {ex}
              </button>
            </li>
          ))}
        </ul>
      )}

      {(run.status || run.error || run.text) && (
        <section className="mt-6" aria-live="polite">
          {run.status && <p className="text-xs text-dim">{run.status}{run.retrieved !== null ? ` · 조각 ${run.retrieved}건` : ""}</p>}
          {run.error && <p className="mt-2 rounded border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{run.error}</p>}
          {run.text && (
            <article className="mt-3">
              <Markdown text={run.text} />
              {running && <span className="inline-block h-4 w-1.5 animate-pulse bg-accent align-text-bottom" aria-hidden />}
              {run.grounded === false && run.sources && (
                <p className="mt-3 text-xs text-open">이 답에는 인용이 없다. 지식 베이스에 근거가 부족하다는 뜻이니 <a href="/research" className="underline">리서치 데스크</a>로 웹에서 조사하라.</p>
              )}
            </article>
          )}
          {run.sources && run.sources.length > 0 && (
            <div className="mt-6 border-t border-line pt-4">
              <h2 className="mb-2 text-xs uppercase tracking-widest text-faint">출처</h2>
              <ol className="space-y-2 text-sm">
                {run.sources.map((s) => (
                  <li key={s.n} className={s.cited.length ? "" : "opacity-60"}>
                    <span className="mr-2 font-mono text-xs text-faint">[{s.n}]</span>
                    <a href={s.url} target="_blank" rel="noreferrer noopener" className="text-accent underline underline-offset-4">
                      {s.title}
                    </a>
                    {s.heading && <span className="text-dim"> — {s.heading}</span>}
                    <span className="ml-2 text-xs text-faint">{s.sourceId} · 수집 {fmtDate(s.fetchedAt)}{s.cited.length ? "" : " · 인용 안 됨"}</span>
                    {s.cited.length > 0 && (
                      <ul className="mt-1 space-y-1 pl-6 text-xs text-dim">
                        {s.cited.slice(0, 3).map((c, i) => (
                          <li key={i} className="border-l-2 border-line pl-2">{c.length > 240 ? c.slice(0, 240) + "…" : c}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
