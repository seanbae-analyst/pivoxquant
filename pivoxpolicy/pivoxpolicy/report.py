"""out/ 에 매트릭스·연표·공백 보고서를 쓴다."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import assess as assess_mod
from . import agreement as agreement_mod
from . import incidents as incidents_mod
from . import kappa as kappa_mod
from . import matrix as matrix_mod
from . import rubric as rubric_mod
from . import sensitivity as sens_mod
from .registry import OUT_DIR
from .schema import Control, Document, JURISDICTIONS, coding_version, is_adjudicated


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


def render_layer_gaps(ma: dict[str, dict[str, matrix_mod.Cell]], mg: dict[str, dict[str, matrix_mod.Cell]],
                      controls: list[Control], coder: str) -> str:
    """두 층 코딩의 공백 — AI·에이전트 층이 구속력 2 미만인 칸. 옆에 일반 층 점수를 둔다."""
    lines = [f"# 공백 — AI·에이전트 층이 구속력 2 미만인 칸 (코더 `{coder}`)", "",
             "| 관할 | # | 통제 | 일반 통제 층 | AI·에이전트 층 | 뜻 |", "|---|---|---|---|---|---|"]
    for j, cid, cell in matrix_mod.gaps(mg, controls):
        c = next(x for x in controls if x.id == cid)
        a = ma[j][cid]
        if cell.score is None:
            m = f"{cell.n_uncoded} 문서 코딩 필요" if cell.n_uncoded else "평가된 문서 없음"
        elif cell.score == 0:
            m = "AI 를 대상으로 한 요구가 없음"
        else:
            m = "자율 문서만" + (" (에이전트 명시)" if cell.agent_specific_voluntary else "")
        if (a.score or 0) >= 2:
            m += " — 일반 통제는 구속력 있음(간극)"
        lines.append(f"| {j} | {c.num} | {c.name_ko} | {matrix_mod._fmt_cell(a)} | {matrix_mod._fmt_cell(cell)} | {m} |")
    lines += ["", "INTL(FSB·ISO) 은 구속력 있는 발행 주체가 없어 설계상 최대 1 이다 — 공백이 아니라 기준점이다.", ""]
    return "\n".join(lines)


def render_kappa_summary(rows: list[tuple[str, str, str, dict[str, Any]]]) -> str:
    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = ["# 코더 간 일치도 — 한눈에", "",
             "| A | B | 단위 | 칸 | 관측 일치율 | κ | Landis–Koch | 불일치 |", "|---|---|---|---|---|---|---|---|"]
    for a, b, lab, r in rows:
        cov = r["coverage"]
        lines.append(f"| `{a}` | `{b}` | {kappa_mod.VIEW_KO[lab].split(' — ')[0]} | {r['n_cells']} | {f(cov.observed_agreement)} | "
                     f"**{f(cov.kappa)}** | {cov.landis_koch()} | {len(r['disagreements'])} |")
    lines += ["", "모양이 다른 코딩(v1 한 칸 ↔ v2 두 층)의 비교는 v2 를 '일반 또는 AI' 로 접은 것이라 참고용이다. 자세한 것은 각 kappa-*.md.", ""]
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


def render_adjudication(coder: str, coding: dict[str, Any]) -> str:
    """조정본의 판정 목록 — 칸마다 판정·따른 쪽·이유·코드북 보강."""
    a, b = coding.get("adjudicates") or ["?", "?"]
    rows = coding.get("adjudication") or []
    lines = [f"# 조정 — `{a}` + `{b}` → `{coder}`", "",
             f"두 코더가 갈린 칸 **{len(rows)}** 개의 판정. 나머지 칸은 두 코더가 같아 그대로 옮겼다 (`check` 가 검사한다).",
             "조정본은 독립 코더가 아니라 κ 에 넣지 않는다. 조정자도 AI 다 — 사람 코더가 들어오면 다시 본다.", "",
             "| 문서 | 통제 | 층 | 판정 | 따른 쪽 |", "|---|---|---|---|---|"]
    for d in rows:
        lines.append(f"| `{d.get('document')}` | {d.get('control')} | {d.get('layer')} | {d.get('decision')} | `{d.get('follows')}` |")
    lines.append("")
    for d in rows:
        lines += [f"## {d.get('document')} × {d.get('control')} ({d.get('layer')})", "", str(d.get("reason", ""))]
        if d.get("codebook"):
            lines += ["", f"코드북 보강: {d['codebook']}"]
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
        ms = matrix_mod.layer_matrices(docs, controls, coding)
        if "" in ms:  # v1 — 한 칸
            m = ms[""]
            w(f"matrix-{coder}.md", matrix_mod.render_markdown(m, controls, coder, docs))
            w(f"matrix-{coder}.csv", matrix_mod.render_csv(m, controls))
            w(f"gaps-{coder}.md", render_gaps(m, controls, coder))
        else:         # v2 — 두 층: 본 표(두 층 나란히) + 층별 표 + 간극
            w(f"matrix-{coder}.md", matrix_mod.render_layers(ms["analog"], ms["agent"], controls, coder))
            for layer, m in ms.items():
                w(f"matrix-{coder}-{layer}.md", matrix_mod.render_markdown(m, controls, coder, docs, layer))
                w(f"matrix-{coder}-{layer}.csv", matrix_mod.render_csv(m, controls))
            w(f"gaps-{coder}.md", render_layer_gaps(ms["analog"], ms["agent"], controls, coder))
    for coder, coding in codings.items():
        if coding_version(coding) == 2:
            srcs = [coding] + [codings[s] for s in (coding.get("adjudicates") or []) if s in codings]
            w(f"sensitivity-{coder}.md", sens_mod.render(sens_mod.flips(docs, controls, coding, srcs), controls, coder))
        if is_adjudicated(coding):
            w(f"adjudication-{coder}.md", render_adjudication(coder, coding))
    names = sorted(k for k, c in codings.items() if not is_adjudicated(c))  # 조정본은 독립 판단이 아니다 — κ 에서 뺀다
    summary: list[tuple[str, str, str, dict[str, Any]]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            res = kappa_mod.compare(codings[a], codings[b], docs, controls)
            w(f"kappa-{a}-vs-{b}.md", kappa_mod.render_compare(res))
            for lab, r in res["views"].items():
                summary.append((a, b, lab, r))
            ma, mb = matrix_mod.layer_matrices(docs, controls, codings[a]), matrix_mod.layer_matrices(docs, controls, codings[b])
            if set(ma) == set(mb):  # 같은 모양의 코딩끼리만 매트릭스를 견준다
                parts = [matrix_mod.render_diff(ma[k], mb[k], controls, a, b, k) for k in ma]
                w(f"matrix-diff-{a}-vs-{b}.md", "\n".join(parts))
    if summary:
        w("kappa-summary.md", render_kappa_summary(summary))

    # 내부통제 평가 루브릭·프로필
    try:
        rub = rubric_mod.load_rubric()
        asmts = rubric_mod.load_assessments()
    except FileNotFoundError:
        rub, asmts = None, {}
    if rub is not None:
        profiles = [assess_mod.build_profile(a, rub) for a in asmts.values()]
        if profiles:
            # 'assessments.md' — 평가 파일 이름(assessment-<stem>.md)과 겹치지 않는 이름 (stem 이 comparison 이어도)
            w("assessments.md", assess_mod.render_comparison(profiles, rub))
        for name, a in asmts.items():
            w(f"assessment-{name}.md", assess_mod.render_profile(assess_mod.build_profile(a, rub), rub))
        w("scoring-method.md", rubric_mod.render_codebook(rub))
    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    if incs:
        w("incidents.md", incidents_mod.render_markdown(incs, controls))
        first = {i.id: list(i.related_controls) for i in incs}
        for coder, raw in agreement_mod.load_incident_codings().items():
            second = agreement_mod.second_controls(raw, set(first))
            basis = {k: (v or {}).get("basis", "") for k, v in (raw.get("incidents") or {}).items()}
            w(f"incident-kappa-{coder}.md", agreement_mod.render_incident_agreement(first, second, coder, basis))
        raws = agreement_mod.load_incident_codings()
        v2 = [n for n in sorted(raws) if agreement_mod.is_incident_v2(raws[n])]
        if len(v2) >= 2:
            w(f"incident-kappa-{v2[0]}-vs-{v2[1]}.md",
              agreement_mod.render_incident_v2_agreement(raws[v2[0]], raws[v2[1]], v2[0], v2[1], set(first)))
    return written
