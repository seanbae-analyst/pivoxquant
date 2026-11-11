"""관할 × 통제 점수 매트릭스."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import LAYERS, Control, Document, JURISDICTIONS, cell_score, coding_version, layer_view


@dataclass
class Cell:
    score: int | None            # 관할 최고 점수. None = 평가된 문서가 하나도 없음
    top_docs: list[str] = field(default_factory=list)   # 최고 점수를 낸 문서 id
    names_agents: bool = False   # 최고 점수 문서 중 에이전트를 명시한 것이 있는가
    agent_specific_voluntary: list[str] = field(default_factory=list)  # 자율이지만 에이전트 명시
    n_coded: int = 0             # covered 가 true/false 로 코딩된 문서 수
    n_uncoded: int = 0           # covered null 인 문서 수


def doc_cell_scores(doc: Document, cells: dict[str, Any]) -> dict[str, int | None]:
    """한 문서의 통제별 점수."""
    out: dict[str, int | None] = {}
    for cid, cell in (cells or {}).items():
        out[cid] = cell_score(doc, cell.get("covered"))
    return out


def build_matrix(
    docs: dict[str, Document],
    controls: list[Control],
    coding: dict[str, Any],
) -> dict[str, dict[str, Cell]]:
    """coding(한 코더) 기준 매트릭스: {jurisdiction: {control_id: Cell}}."""
    items = coding.get("items") or {}
    matrix: dict[str, dict[str, Cell]] = {
        j: {c.id: Cell(score=None) for c in controls} for j in JURISDICTIONS
    }
    for doc_id, cells in items.items():
        doc = docs.get(doc_id)
        if doc is None or doc.binding == 0:  # 모르는 문서는 `check` 가 보고한다 — 여기선 건너뛴다
            continue
        if doc.status == "superseded":  # 폐지·대체된 문서는 '지금의 규범' 매트릭스에 넣지 않는다
            continue
        if not isinstance(cells, dict):
            continue
        for c in controls:
            cell = (cells or {}).get(c.id)
            if cell is None:
                continue
            target = matrix[doc.jurisdiction][c.id]
            covered = cell.get("covered")
            if covered is None:
                target.n_uncoded += 1
                continue
            target.n_coded += 1
            # 칸 단위 '에이전트 명시'(v2 층 뷰가 싣는다)가 있으면 그것을, 없으면 문서 단위 names_agents 를 쓴다
            na = cell.get("names_agent")
            agentic = bool(doc.names_agents) if na is None else bool(na)
            s = cell_score(doc, covered, na)
            assert s is not None
            if covered and doc.binding == 1 and agentic:
                target.agent_specific_voluntary.append(doc_id)
            if target.score is None or s > target.score:
                target.score = s
                target.top_docs = [doc_id]
                target.names_agents = agentic and covered
            elif s == target.score:
                # 0 동점도 기록한다 — '어떤 문서도 다루지 않음' 의 근거 문서가 여럿이면 다 보여야 한다
                target.top_docs.append(doc_id)
                target.names_agents = target.names_agents or (agentic and covered)
    return matrix


def layer_matrices(
    docs: dict[str, Document], controls: list[Control], coding: dict[str, Any]
) -> dict[str, dict[str, dict[str, Cell]]]:
    """코딩 하나의 매트릭스들. v1 코딩 = {"": m} · v2 코딩 = {"analog": m, "agent": m}."""
    if coding_version(coding) != 2:
        return {"": build_matrix(docs, controls, coding)}
    return {layer: build_matrix(docs, controls, layer_view(coding, layer)) for layer in LAYERS}


LAYER_KO = {"": "", "analog": "일반 통제", "agent": "AI·에이전트 적용", "either": "일반 또는 AI"}


def gaps(matrix: dict[str, dict[str, Cell]], controls: list[Control], threshold: int = 2) -> list[tuple[str, str, Cell]]:
    """점수 < threshold 이거나 None 인 셀."""
    out = []
    for j in JURISDICTIONS:
        for c in controls:
            cell = matrix[j][c.id]
            if cell.score is None or cell.score < threshold:
                out.append((j, c.id, cell))
    return out


def _fmt_cell(cell: Cell) -> str:
    if cell.score is None:
        return "–" if cell.n_uncoded == 0 else f"? ({cell.n_uncoded} 코딩 필요)"
    s = str(cell.score)
    if cell.names_agents:
        s += "*"
    if cell.agent_specific_voluntary and not cell.names_agents:
        s += "†"
    return s


def render_markdown(matrix: dict[str, dict[str, Cell]], controls: list[Control], coder: str, docs: dict[str, Document],
                    layer: str = "") -> str:
    scale = {"analog": "점수: 0 다루지 않음 · 1 자율 · 2 구속력 · `–` 평가 문서 없음 · `?` 코딩 필요 (일반 통제 층엔 3 이 없다)",
             "agent": "점수: 0 다루지 않음 · 1 자율 · 2 구속력(AI 일반) · 3 구속력+에이전트 명시 · `–` 평가 문서 없음 · `?` 코딩 필요"}.get(
        layer, "점수: 0 다루지 않음 · 1 자율 · 2 구속력(에이전트 미명시) · 3 구속력+에이전트 명시 · `–` 평가 문서 없음 · `?` 코딩 필요")
    lines = [
        f"# 통제 × 관할 구속력 매트릭스 — 코더 `{coder}`" + (f" · {LAYER_KO[layer]} 층" if layer else ""),
        "",
        scale,
        "",
        "`*` 최고점 문서가 에이전트를 명시 · `†` 자율 문서 중 에이전트를 명시한 것이 따로 있음",
        "",
        "| # | 통제 | " + " | ".join(JURISDICTIONS) + " |",
        "|---|---|" + "|".join(["---"] * len(JURISDICTIONS)) + "|",
    ]
    for c in controls:
        row = [str(c.num), f"{c.name_ko} ({c.name_en})"]
        for j in JURISDICTIONS:
            row.append(_fmt_cell(matrix[j][c.id]))
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## 셀별 근거 문서", ""]
    for j in JURISDICTIONS:
        lines.append(f"### {j}")
        lines.append("")
        for c in controls:
            cell = matrix[j][c.id]
            if cell.score is None:
                continue
            refs = ", ".join(f"`{d}`" for d in cell.top_docs) if cell.top_docs else "(없음)"
            extra = ""
            if cell.agent_specific_voluntary:
                extra = " · 에이전트 명시 자율문서: " + ", ".join(f"`{d}`" for d in cell.agent_specific_voluntary)
            lines.append(f"- {c.num} {c.name_ko}: **{_fmt_cell(cell)}** ← {refs}{extra}")
        lines.append("")
    return "\n".join(lines)


def render_csv(matrix: dict[str, dict[str, Cell]], controls: list[Control]) -> str:
    lines = ["control_num,control_id," + ",".join(JURISDICTIONS)]
    for c in controls:
        vals = []
        for j in JURISDICTIONS:
            s = matrix[j][c.id].score
            vals.append("" if s is None else str(s))
        lines.append(f"{c.num},{c.id}," + ",".join(vals))
    return "\n".join(lines) + "\n"


def diff(
    a: dict[str, dict[str, Cell]], b: dict[str, dict[str, Cell]], controls: list[Control]
) -> list[tuple[str, str, int | None, int | None]]:
    """두 코더 매트릭스에서 관할 점수가 다른 칸 (관할, 통제, a 점수, b 점수)."""
    out: list[tuple[str, str, int | None, int | None]] = []
    for j in JURISDICTIONS:
        for c in controls:
            sa, sb = a[j][c.id].score, b[j][c.id].score
            if sa != sb:
                out.append((j, c.id, sa, sb))
    return out


def render_diff(
    a: dict[str, dict[str, Cell]], b: dict[str, dict[str, Cell]], controls: list[Control], name_a: str, name_b: str,
    layer: str = "",
) -> str:
    rows = diff(a, b, controls)
    n = len(JURISDICTIONS) * len(controls)
    judged = [r for r in rows if r[2] is not None and r[3] is not None]
    lines = [
        f"# 매트릭스 민감도 — `{name_a}` vs `{name_b}`" + (f" · {LAYER_KO[layer]} 층" if layer else ""),
        "",
        f"관할 × 통제 {n}칸 중 점수가 다른 칸 **{len(rows)}** — 둘 다 코딩했는데 판단이 갈린 칸 **{len(judged)}** · "
        f"한쪽만 코딩한 칸(?) {len(rows) - len(judged)}. "
        "판단이 갈린 칸의 결론(예: '미국은 사람 승인 0')은 코더 한 명의 판단에 기대고 있으니 논문에서는 둘을 함께 쓰거나 판정 규칙을 먼저 정한다.",
        "",
        f"| 관할 | 통제 | {name_a} | {name_b} | {name_a} 최고 문서 | {name_b} 최고 문서 |",
        "|---|---|---|---|---|---|",
    ]
    fmt = lambda x: "?" if x is None else str(x)  # noqa: E731
    for j, cid, sa, sb in rows:
        ta = ", ".join(f"`{d}`" for d in a[j][cid].top_docs[:3]) or "–"
        tb = ", ".join(f"`{d}`" for d in b[j][cid].top_docs[:3]) or "–"
        lines.append(f"| {j} | {cid} | {fmt(sa)} | {fmt(sb)} | {ta} | {tb} |")
    if not rows:
        lines.append("| – | – | – | – | – | – |")
    return "\n".join(lines) + "\n"


def render_layers(
    ma: dict[str, dict[str, Cell]], mg: dict[str, dict[str, Cell]], controls: list[Control], coder: str
) -> str:
    """두 층을 한 표에. 칸 = '일반 층 점수 / AI·에이전트 층 점수'. 논문의 본 표."""
    lines = [
        f"# 통제 × 관할 — 두 층 (코더 `{coder}`)",
        "",
        "칸 = **일반 통제 층 / AI·에이전트 층**. 일반 층 0~2 (0 다루지 않음 · 1 자율 · 2 구속력), "
        "AI·에이전트 층 0~3 (2 = 구속력 있고 AI 일반 대상 · 3 = 구속력 있고 에이전트 명시). "
        "`*` 최고점 문서의 근거 조항이 에이전트를 명시 · `†` 에이전트를 명시한 자율 문서가 따로 있음 · `–` 평가 문서 없음.",
        "",
        "| # | 통제 | " + " | ".join(JURISDICTIONS) + " |",
        "|---|---|" + "|".join(["---"] * len(JURISDICTIONS)) + "|",
    ]
    for c in controls:
        row = [str(c.num), f"{c.name_ko} ({c.name_en})"]
        for j in JURISDICTIONS:
            row.append(f"{_fmt_cell(ma[j][c.id])} / {_fmt_cell(mg[j][c.id])}")
        lines.append("| " + " | ".join(row) + " |")
    gap = [(j, c) for j in JURISDICTIONS for c in controls
           if (ma[j][c.id].score or 0) >= 2 and (mg[j][c.id].score or 0) < 2]
    lines += ["", f"## 간극 — 일반 통제는 구속력(2)인데 AI·에이전트 층은 2 미만: {len(gap)}칸", ""]
    for j, c in gap:
        a, g = ma[j][c.id], mg[j][c.id]
        ga = ", ".join(f"`{d}`" for d in a.top_docs[:3]) or "–"
        gg = ", ".join(f"`{d}`" for d in (g.top_docs if (g.score or 0) > 0 else g.agent_specific_voluntary)[:3]) or "–"
        lines.append(f"- {j} · {c.num} {c.name_ko}: 일반 **{_fmt_cell(a)}** ← {ga} · AI·에이전트 **{_fmt_cell(g)}** ← {gg}")
    if not gap:
        lines.append("- 없음")
    threes = [(j, c) for j in JURISDICTIONS for c in controls if mg[j][c.id].score == 3]
    lines += ["", f"구속력 있는 문서가 에이전트를 명시해 요구하는 칸(점수 3): **{len(threes)}**"
              + ("" if not threes else " — " + ", ".join(f"{j}·{c.name_ko}" for j, c in threes)), ""]
    return "\n".join(lines)
