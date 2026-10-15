"use client";

/**
 * <ResearchCard /> — one research note as written, plus its scoring.
 *
 * Scoring (<ResearchReview />) asks one thing per reason: 맞음 / 틀림 / 모름.
 * The result on the user's own fills is deliberately NOT shown while scoring
 * — seeing "판 뒤 이익" first pulls the answer toward "맞음" (judging the
 * reason by the money). It appears on the card only after the score is
 * saved, and a saved score cannot be changed (the backend refuses a second
 * one) — otherwise the second scoring would be made with that hindsight.
 * Counts and facts only; no grade, no verdict of ours.
 */
import * as React from "react";
import { ApiError } from "@/lib/api";
import { deleteResearchNote, reviewResearchNote } from "@/lib/hooks";
import { displayName } from "@/lib/format";
import {
  INFO_SOURCE_LABEL,
  OUTCOME_LABEL,
  RESEARCH_MAX_REVIEW_NOTE,
  VERDICT_LABEL,
  VERDICT_ORDER,
  kstDateOf,
  researchDate,
} from "@/lib/research";
import { Caption } from "@/components/ui/editorial";
import type { ResearchNote, ResearchVerdict } from "@/lib/types";

const LINE = "1px solid var(--pq-ivory-line)";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <div className="text-pq-caption text-[var(--pq-ivory-faint)]">{label}</div>
      <div className="mt-0.5 whitespace-pre-wrap text-pq-body-sm text-[var(--pq-ivory-strong)]" style={{ wordBreak: "keep-all" }}>
        {children}
      </div>
    </div>
  );
}

function VerdictTag({ v }: { v: ResearchVerdict }) {
  const on = v === "right";
  return (
    <span
      className="shrink-0 rounded-full px-2 py-0.5 text-pq-caption"
      style={{
        border: `1px solid ${on ? "rgba(var(--pq-bronze-rgb), 0.6)" : "var(--pq-ivory-line)"}`,
        color: on ? "var(--pq-bronze-light)" : "var(--pq-ivory-dim)",
      }}
    >
      {VERDICT_LABEL[v]}
    </span>
  );
}

/* ── scoring ─────────────────────────────────────────────────────────── */

export function ResearchReview({
  note,
  onSaved,
  onCancel,
}: {
  note: ResearchNote;
  onSaved: (note: ResearchNote) => void;
  onCancel?: () => void;
}) {
  const [verdicts, setVerdicts] = React.useState<(ResearchVerdict | null)[]>(() =>
    note.theses.map((_, i) => note.verdicts[i] ?? null),
  );
  const [line, setLine] = React.useState(note.review_note ?? "");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const complete = verdicts.every((v) => v !== null);

  async function save() {
    if (!complete || saving) return;
    setSaving(true);
    setError(null);
    try {
      const res = await reviewResearchNote(note.id, {
        verdicts: verdicts as ResearchVerdict[],
        note: line.trim() || undefined,
      });
      onSaved(res.note);
    } catch (err) {
      setError(err instanceof ApiError && err.message ? err.message : "저장하지 못했어요.");
      setSaving(false);
    }
  }

  return (
    <div className="mt-4 rounded-[var(--pq-radius-card)] p-4" style={{ border: LINE }} data-testid="research-review">
      <div className="text-pq-body font-semibold text-[var(--pq-ivory)]">그때 적은 이유가 맞았나요?</div>
      <Caption className="mt-1">
        이유마다 골라 주세요. 본인 체결 손익은 채점한 뒤에 보여 드려요. 저장하면 고칠 수 없어요.
      </Caption>
      <ol className="mt-3 list-none space-y-3 p-0">
        {note.theses.map((t, i) => (
          <li key={i}>
            <p className="text-pq-body-sm text-[var(--pq-ivory-strong)]" style={{ wordBreak: "keep-all" }}>
              {t}
            </p>
            <div className="mt-2 inline-flex p-0.5" role="group" aria-label={`이유 ${i + 1} 채점`} style={{ border: LINE, borderRadius: "var(--pq-radius-cta)" }}>
              {VERDICT_ORDER.map((v) => {
                const on = verdicts[i] === v;
                return (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setVerdicts((cur) => cur.map((x, j) => (j === i ? v : x)))}
                    className="h-8 min-w-[3.5rem] px-3 text-pq-body-sm transition-colors"
                    style={{
                      borderRadius: "calc(var(--pq-radius-cta) - 2px)",
                      background: on ? "var(--pq-bronze)" : "transparent",
                      color: on ? "var(--pq-ink)" : "var(--pq-ivory-dim)",
                      fontWeight: on ? 600 : 400,
                    }}
                  >
                    {VERDICT_LABEL[v]}
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ol>
      <input
        aria-label="한 줄 (선택)"
        value={line}
        maxLength={RESEARCH_MAX_REVIEW_NOTE}
        onChange={(e) => setLine(e.target.value)}
        placeholder="한 줄 (선택)"
        className="mt-4 w-full rounded-[var(--pq-radius-card)] border border-[var(--pq-ivory-line)] bg-transparent px-3 py-2 text-pq-body-sm text-[var(--pq-ivory)] outline-none placeholder:text-[var(--pq-ivory-faint)] focus:border-[var(--pq-bronze)]"
      />
      {error && (
        <p role="alert" className="mt-2 text-pq-caption" style={{ color: "var(--pq-negative)" }}>
          {error}
        </p>
      )}
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={!complete || saving}
          className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm disabled:cursor-not-allowed disabled:opacity-30"
        >
          {saving ? "저장하는 중" : "채점 저장"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-pq-caption text-[var(--pq-ivory-dim)] hover:text-[var(--pq-ivory)]">
            취소
          </button>
        )}
      </div>
    </div>
  );
}

/* ── the card ────────────────────────────────────────────────────────── */

export function ResearchCard({
  note,
  onChanged,
  startOpen = false,
}: {
  note: ResearchNote;
  onChanged: () => void;
  /** Open the scoring right away (the due list). */
  startOpen?: boolean;
}) {
  const [reviewing, setReviewing] = React.useState(startOpen && !note.reviewed_at);
  const scored = Boolean(note.reviewed_at);
  const written = researchDate(kstDateOf(note.created_at));

  const remove = async () => {
    if (typeof window !== "undefined" && !window.confirm("이 리서치를 지울까요? 되돌릴 수 없어요.")) return;
    try {
      await deleteResearchNote(note.id);
      onChanged();
    } catch {
      /* the list refetch shows the truth either way */
      onChanged();
    }
  };

  const status = scored
    ? `채점함 · ${OUTCOME_LABEL[note.outcome]}`
    : note.due
      ? "다시 볼 날이 됐어요"
      : `${researchDate(note.review_on)}에 다시 봐요`;

  return (
    <article
      className="rounded-[var(--pq-radius-card)] p-4 md:p-5"
      style={{ border: LINE, background: "var(--pq-card-veil)" }}
      data-testid="research-card"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-pq-body font-semibold text-[var(--pq-ivory)]">{displayName(note.ticker, note.name)}</h3>
        <span
          className="text-pq-caption tabular-nums"
          style={{ color: note.due && !scored ? "var(--pq-bronze-light)" : "var(--pq-ivory-faint)" }}
        >
          {status}
        </span>
      </header>
      <Caption className="mt-0.5">
        {written}에 씀{note.info_source ? ` · ${INFO_SOURCE_LABEL[note.info_source]}에서 알게 됨` : ""}
      </Caption>

      <Field label="뭘로 돈을 버나">{note.business}</Field>
      <div className="mt-3">
        <div className="text-pq-caption text-[var(--pq-ivory-faint)]">내가 본 이유</div>
        <ol className="mt-1 list-none space-y-1.5 p-0">
          {note.theses.map((t, i) => (
            <li key={i} className="flex items-start justify-between gap-3">
              <span className="text-pq-body-sm text-[var(--pq-ivory-strong)]" style={{ wordBreak: "keep-all" }}>
                {t}
              </span>
              {scored && note.verdicts[i] && <VerdictTag v={note.verdicts[i]} />}
            </li>
          ))}
        </ol>
      </div>
      {scored && note.review_note && <Field label="채점 한 줄">{note.review_note}</Field>}

      <details className="mt-3">
        <summary className="cursor-pointer select-none text-pq-caption text-[var(--pq-ivory-dim)]">나머지 칸</summary>
        <Field label="이게 보이면 틀린 것">{note.invalidation ?? "적지 않음"}</Field>
        <Field label="가장 큰 위험">{note.risk ?? "적지 않음"}</Field>
        <Field label="직접 확인한 숫자">{note.numbers ?? "안 봄"}</Field>
      </details>

      {reviewing && !scored ? (
        <ResearchReview
          note={note}
          onSaved={() => {
            setReviewing(false);
            onChanged();
          }}
          onCancel={() => setReviewing(false)}
        />
      ) : (
        <div className="mt-4 flex items-center justify-between gap-3">
          {scored ? (
            <span />
          ) : (
            <button
              type="button"
              onClick={() => setReviewing(true)}
              className={
                note.due
                  ? "pq-ink-btn-bronze inline-flex items-center px-4 py-1.5 text-pq-mono-sm"
                  : "text-pq-caption text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
              }
            >
              {note.due ? "채점하기" : "지금 채점하기"}
            </button>
          )}
          <button type="button" onClick={remove} className="text-pq-caption text-[var(--pq-ivory-faint)] hover:text-[var(--pq-ivory)]">
            지우기
          </button>
        </div>
      )}
    </article>
  );
}

export default ResearchCard;
