"""out/ 에 매트릭스·연표·공백 보고서를 쓴다."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import assess as assess_mod
from . import incidents as incidents_mod
from . import kappa as kappa_mod
from . import matrix as matrix_mod
from . import rubric as rubric_mod
from .registry import OUT_DIR
from .schema import Control, Document, JURISDICTIONS


def render_timeline(docs: dict[str, Document]) -> str:
    dated = sorted((d for d in docs.values() if d.date), key=lambda d: (d.date, d.id))  # type: ignore[arg-type]
    undated = sorted((d for d in docs.values() if not d.date), key=lambda d: d.id)
    lines = ["# 연표 — 발표일 순", "",
             "| 날짜 | 관할 | 발행 | 문서 | 유형 | 구속력 | 에이전트 명시 | 상태 |",
             "|---|---|---|---|---|---|---|---|"]
    for d in dated:
        na = {True: "예", False: "아니오", None: "확인 필요"}[d.names_agents]
        title = f"[{d.title}]({d.url})" if d.url else d.title
        lines.append(f"| {d.date} | {d.jurisdiction} | {d.issuer} | {title} | {d.doc_type} | {d.binding} | {na} | {d.status} |")
    if undated:
        lines += ["", "## 날짜 미확정", ""]
        for d in undated:
            lines.append(f"- `{d.id}` {d.title} — {d.url_note or ''}")
    return "\n".join(lines) + "\n"


def render_gaps(matrix: dict[str, dict[str, matrix_mod.Cell]], controls: list[Control], coder: str) -> str:
    lines = [f"# 공백 — 구속력 2 미만 또는 미코딩 셀 (코더 `{coder}`)", "",
             "| 관할 | # | 통제 | 현재 | 뜻 |", "|---|---|---|---|---|"]
    meaning = {None: "평가된 문서 없음", 0: "어떤 문서도 다루지 않음", 1: "자율 문서만 다룸"}
    for j, cid, cell in matrix_mod.gaps(matrix, controls):
        c = next(x for x in controls if x.id == cid)
        cur = matrix_mod._fmt_cell(cell)
        m = meaning.get(cell.score, "")
        if cell.score is None and cell.n_uncoded:
            m = f"{cell.n_uncoded} 문서 코딩 필요"
        lines.append(f"| {j} | {c.num} | {c.name_ko} | {cur} | {m} |")
    lines += ["", "INTL(FSB·ISO) 은 구속력 있는 발행 주체가 없어 설계상 최대 1 이다 — 공백이 아니라 기준점이다.",
              "", "구속력 3 (에이전트를 명시한 구속력 있는 규정) 인 셀이 하나도 없으면, 그것이 논문의 핵심 결과다.", ""]
    return "\n".join(lines)


def render_documents_index(docs: dict[str, Document]) -> str:
    lines = ["# 문서 색인", ""]
    for j in JURISDICTIONS:
        group = [d for d in docs.values() if d.jurisdiction == j]
        if not group:
            continue
        lines += [f"## {j} ({len(group)})", ""]
        for d in sorted(group, key=lambda d: (d.date or date.min, d.id)):
            url = f" — <{d.url}>" if d.url else f" — URL {d.url_note}"
            lines.append(f"- `{d.id}` **{d.title}** · {d.issuer} · {d.date or '날짜 미확정'} · binding {d.binding}{url}")
            if d.summary:
                lines.append(f"  - {d.summary}")
        lines.append("")
    return "\n".join(lines)


def write_all(
    docs: dict[str, Document],
    controls: list[Control],
    codings: dict[str, dict[str, Any]],
    out_dir: Path = OUT_DIR,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def w(name: str, text: str) -> None:
        p = out_dir / name
        p.write_text(text, encoding="utf-8")
        written.append(p)

    w("timeline.md", render_timeline(docs))
    w("documents.md", render_documents_index(docs))
    for coder, coding in codings.items():
        m = matrix_mod.build_matrix(docs, controls, coding)
        w(f"matrix-{coder}.md", matrix_mod.render_markdown(m, controls, coder, docs))
        w(f"matrix-{coder}.csv", matrix_mod.render_csv(m, controls))
        w(f"gaps-{coder}.md", render_gaps(m, controls, coder))
    names = sorted(codings)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            res = kappa_mod.compare_coders(codings[names[i]], codings[names[j]], docs, controls)
            w(f"kappa-{names[i]}-vs-{names[j]}.md", kappa_mod.render_markdown(res))

    # 내부통제 평가 루브릭·프로필
    try:
        rub = rubric_mod.load_rubric()
        asmts = rubric_mod.load_assessments()
    except FileNotFoundError:
        rub, asmts = None, {}
    if rub is not None:
        profiles = [assess_mod.build_profile(a, rub) for a in asmts.values()]
        if profiles:
            w("assessment-comparison.md", assess_mod.render_comparison(profiles, rub))
        for name, a in asmts.items():
            w(f"assessment-{name}.md", assess_mod.render_profile(assess_mod.build_profile(a, rub), rub))
        w("scoring-method.md", rubric_mod.render_codebook(rub))
    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    if incs:
        w("incidents.md", incidents_mod.render_markdown(incs, controls))
    return written
