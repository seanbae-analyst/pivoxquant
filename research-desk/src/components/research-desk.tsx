"use client";

/**
 * 리서치 데스크 화면 — 질문 하나, 진행 상황, 보고서, 보관함.
 * 상태는 서버 이벤트를 그대로 접은 것이다. 계산은 파이프라인이 하고 화면은 보여주기만 한다.
 */
import { useCallback, useMemo, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { reportFilename, verdictCounts, verdictLabel } from "@/lib/research/report";
import type { ClaimVerdict, Plan, Report, ResearchEvent, Stage } from "@/lib/research/types";
import { runResearchStream } from "@/lib/run-client";
import { dropReport, keepReport, useReports } from "@/lib/use-reports";

interface SubStatus {
  subQuestion: string;
  state: "pending" | "done" | "failed";
  claimCount: number;
  sourceCount: number;
  error: string | null;
}

interface RunState {
  stage: Stage | null;
  message: string;
  plan: Plan | null;
  subs: SubStatus[];
  verdicts: ClaimVerdict[] | null;
  draft: string;
  report: Report | null;
  error: string | null;
}

const EMPTY: RunState = { stage: null, message: "", plan: null, subs: [], verdicts: null, draft: "", report: null, error: null };

const STAGES: Array<{ key: Stage; label: string }> = [
  { key: "planning", label: "계획" },
  { key: "searching", label: "조사" },
  { key: "verifying", label: "반증" },
  { key: "writing", label: "집필" },
  { key: "done", label: "완료" },
];

function reduce(state: RunState, ev: ResearchEvent): RunState {
  switch (ev.type) {
    case "status":
      return { ...state, stage: ev.stage, message: ev.message };
    case "plan":
      return {
        ...state,
        plan: ev.plan,
        subs: ev.plan.subQuestions.map((q) => ({ subQuestion: q, state: "pending", claimCount: 0, sourceCount: 0, error: null })),
      };
    case "sub_done":
      return {
        ...state,
        subs: state.subs.map((s, i) =>
          i === ev.index ? { ...s, state: ev.error ? "failed" : "done", claimCount: ev.claimCount, sourceCount: ev.sourceCount, error: ev.error } : s,
        ),
      };
    case "verdicts":
      return { ...state, verdicts: ev.verdicts };
    case "token":
      return { ...state, draft: state.draft + ev.text };
    case "done":
      return { ...state, report: ev.report, stage: "done" };
    case "error":
      return { ...state, error: ev.message };
  }
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function download(report: Report) {
  const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = reportFilename(report);
  a.click();
  URL.revokeObjectURL(url);
}

export function ResearchDesk() {
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunState>(EMPTY);
  const history = useReports();
  const [showHistory, setShowHistory] = useState(false);
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    const q = question.trim();
    if (!q || running) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setRun({ ...EMPTY, stage: "planning", message: "연결 중" });
    try {
      await runResearchStream(
        q,
        (ev) => {
          setRun((s) => reduce(s, ev));
          if (ev.type === "done") keepReport(ev.report);
        },
        controller.signal,
      );
    } catch (err) {
      const message = controller.signal.aborted ? "중단했다." : err instanceof Error ? err.message : String(err);
      setRun((s) => ({ ...s, error: message }));
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [question, running]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const open = useCallback((r: Report) => {
    setQuestion(r.question);
    setRun({ ...EMPTY, stage: "done", plan: r.plan, verdicts: r.verdicts, report: r, subs: r.plan.subQuestions.map((q) => ({ subQuestion: q, state: "done", claimCount: r.claims.filter((c) => c.subQuestion === q).length, sourceCount: 0, error: null })) });
    setShowHistory(false);
  }, []);

  const copy = useCallback(async (r: Report) => {
    try {
      await navigator.clipboard.writeText(r.markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 클립보드 권한이 없으면 다운로드 버튼이 남아 있다 */
    }
  }, []);

  const counts = useMemo(() => (run.verdicts ? verdictCounts(run.verdicts) : null), [run.verdicts]);
  const stageIndex = run.stage ? STAGES.findIndex((s) => s.key === run.stage) : -1;
  const shownMarkdown = run.report?.markdown ?? run.draft;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
      <header className="mb-8 flex items-baseline justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl tracking-tight">리서치 데스크</h1>
          <p className="mt-1 text-sm text-dim">질문을 쪼개고, 찾고, 반박하고, 출처를 달아 쓴다.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowHistory((v) => !v)}
          className="text-sm text-dim underline-offset-4 hover:text-ink hover:underline lg:hidden"
        >
          보관함 {history.length}
        </button>
      </header>

      <div className="grid gap-8 lg:grid-cols-[240px_1fr]">
        <aside className={`${showHistory ? "block" : "hidden"} lg:block`}>
          <h2 className="mb-3 text-xs uppercase tracking-widest text-faint">보관함</h2>
          {history.length === 0 ? (
            <p className="text-sm text-faint">아직 없다. 첫 보고서는 이 브라우저에만 저장된다.</p>
          ) : (
            <ul className="space-y-1">
              {history.map((r) => (
                <li key={r.id} className="group flex items-start gap-2">
                  <button type="button" onClick={() => open(r)} className="flex-1 rounded px-2 py-1.5 text-left text-sm leading-snug hover:bg-raised">
                    <span className="line-clamp-2">{r.question}</span>
                    <span className="mt-0.5 block text-xs text-faint">{fmtDate(r.createdAt)}</span>
                  </button>
                  <button
                    type="button"
                    aria-label="삭제"
                    onClick={() => dropReport(r.id)}
                    className="px-1 pt-1.5 text-xs text-faint opacity-0 hover:text-bad group-hover:opacity-100 focus:opacity-100"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="min-w-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void start();
            }}
            className="rounded-lg border border-line bg-raised p-3"
          >
            <label htmlFor="question" className="sr-only">
              질문
            </label>
            <textarea
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void start();
              }}
              placeholder="예: 2026년 기준 한국 개인투자자 중 매매일지를 쓰는 비율은 얼마이고, 그 근거는 무엇인가?"
              rows={3}
              maxLength={2000}
              disabled={running}
              className="w-full resize-y bg-transparent text-[15px] leading-relaxed outline-none placeholder:text-faint disabled:opacity-60"
            />
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-xs text-faint">⌘/Ctrl + Enter · 4~5개 하위 질문을 병렬 조사하므로 수 분 걸린다</span>
              {running ? (
                <button type="button" onClick={stop} className="rounded border border-line px-3 py-1.5 text-sm text-dim hover:text-ink">
                  중단
                </button>
              ) : (
                <button type="submit" disabled={!question.trim()} className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-bg disabled:opacity-40">
                  조사 시작
                </button>
              )}
            </div>
          </form>

          {run.stage && (
            <section className="mt-6" aria-live="polite">
              <ol className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                {STAGES.map((s, i) => {
                  const state = i < stageIndex ? "past" : i === stageIndex ? "now" : "next";
                  return (
                    <li key={s.key} className={state === "now" ? "text-accent" : state === "past" ? "text-ink" : "text-faint"}>
                      {state === "past" ? "✓ " : state === "now" && running ? "● " : "○ "}
                      {s.label}
                    </li>
                  );
                })}
              </ol>
              {running && <p className="mt-1 text-xs text-dim">{run.message}</p>}
              {run.error && <p className="mt-2 rounded border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{run.error}</p>}

              {run.plan && (
                <div className="mt-4 rounded-lg border border-line p-3 text-sm">
                  <p className="text-dim">{run.plan.framing}</p>
                  <ol className="mt-2 space-y-1">
                    {run.subs.map((s, i) => (
                      <li key={i} className="flex items-baseline gap-2">
                        <span className={s.state === "done" ? "text-ok" : s.state === "failed" ? "text-bad" : running ? "text-accent" : "text-faint"}>
                          {s.state === "done" ? "✓" : s.state === "failed" ? "✕" : "…"}
                        </span>
                        <span className="flex-1">{s.subQuestion}</span>
                        <span className="shrink-0 text-xs text-faint">
                          {s.state === "done" ? `주장 ${s.claimCount} · 출처 ${s.sourceCount}` : s.state === "failed" ? "실패" : ""}
                        </span>
                      </li>
                    ))}
                  </ol>
                  {run.plan.killCriteria.length > 0 && (
                    <details className="mt-2 text-xs text-dim">
                      <summary className="cursor-pointer">무너뜨릴 조건 {run.plan.killCriteria.length}</summary>
                      <ul className="mt-1 list-disc pl-4">
                        {run.plan.killCriteria.map((k, i) => (
                          <li key={i}>{k}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {counts && (
                    <p className="mt-3 flex gap-3 text-xs">
                      <span className="text-ok">{verdictLabel("confirmed")} {counts.confirmed}</span>
                      <span className="text-bad">{verdictLabel("killed")} {counts.killed}</span>
                      <span className="text-open">{verdictLabel("open")} {counts.open}</span>
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          {shownMarkdown && (
            <article className="mt-8">
              {run.report && (
                <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-dim">
                  <span>출처 {run.report.sources.length}건 · {run.report.model}</span>
                  <button type="button" onClick={() => download(run.report!)} className="underline underline-offset-4 hover:text-ink">
                    .md 다운로드
                  </button>
                  <button type="button" onClick={() => void copy(run.report!)} className="underline underline-offset-4 hover:text-ink">
                    {copied ? "복사됨" : "복사"}
                  </button>
                </div>
              )}
              <Markdown text={shownMarkdown} />
              {running && run.stage === "writing" && <span className="inline-block h-4 w-1.5 animate-pulse bg-accent align-text-bottom" aria-hidden />}
            </article>
          )}
        </main>
      </div>
    </div>
  );
}
