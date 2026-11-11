"""관할 × 통제 점수 매트릭스."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import Control, Document, JURISDICTIONS, cell_score


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
        doc = docs[doc_id]
        if doc.binding == 0:
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
            s = cell_score(doc, covered)
            assert s is not None
            if covered and doc.binding == 1 and doc.names_agents:
                target.agent_specific_voluntary.append(doc_id)
            if target.score is None or s > target.score:
                target.score = s
                target.top_docs = [doc_id]
                target.names_agents = bool(doc.names_agents) and covered
            elif s == target.score and s > 0:
                target.top_docs.append(doc_id)
                target.names_agents = target.names_agents or (bool(doc.names_agents) and covered)
    return matrix


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


def render_markdown(matrix: dict[str, dict[str, Cell]], controls: list[Control], coder: str, docs: dict[str, Document]) -> str:
    lines = [
        f"# 통제 × 관할 구속력 매트릭스 — 코더 `{coder}`",
        "",
        "점수: 0 다루지 않음 · 1 자율 · 2 구속력(에이전트 미명시) · 3 구속력+에이전트 명시 · `–` 평가 문서 없음 · `?` 코딩 필요",
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
