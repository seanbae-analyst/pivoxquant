"use client";

/** 개념 페이지의 "묻기" — 지식 베이스에 개념 질문을 던진다. 비어 있으면 안내만. */
import { useCallback, useState } from "react";
import { Markdown } from "@/components/markdown";
import { askStream } from "@/lib/ask-client";
import type { AnswerSource } from "@/lib/kb/types";

export function AskInline({ question }: { question: string }) {
  const [q, setQ] = useState(question);
  const [text, setText] = useState("");
  const [sources, setSources] = useState<AnswerSource[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const run = useCallback(async () => {
    if (!q.trim() || running) return;
    setRunning(true);
    setText("");
    setSources(null);
    setError(null);
    try {
      await askStream(q, (ev) => {
        if (ev.type === "token") setText((t) => t + ev.text);
        else if (ev.type === "citation") setText((t) => t + ` [${ev.n}]`);
        else if (ev.type === "done") setSources(ev.sources);
        else if (ev.type === "error") setError(ev.message);
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [q, running]);

  return (
    <div className="rounded-lg border border-line bg-raised p-3">
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 bg-transparent text-sm outline-none" aria-label="지식 베이스에 묻기" />
        <button type="button" onClick={() => void run()} disabled={running || !q.trim()} className="rounded bg-accent px-3 py-1 text-xs font-medium text-bg disabled:opacity-40">{running ? "…" : "묻기"}</button>
      </div>
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      {text && <div className="mt-3 text-sm"><Markdown text={text} /></div>}
      {sources && sources.length > 0 && (
        <ol className="mt-3 space-y-1 text-xs text-dim">
          {sources.filter((s) => s.cited.length).map((s) => (
            <li key={s.n}><span className="font-mono text-faint">[{s.n}]</span> <a href={s.url} target="_blank" rel="noreferrer noopener" className="text-accent underline">{s.title}</a>{s.heading && ` — ${s.heading}`}</li>
          ))}
        </ol>
      )}
      {!text && !error && <p className="mt-2 text-xs text-faint">답은 수집해 둔 문서 안에서만 나오고 문장마다 출처가 붙는다. 지식 베이스가 비어 있으면 먼저 수집해야 한다.</p>}
    </div>
  );
}
