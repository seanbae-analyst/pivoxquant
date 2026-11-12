"""민감도 — 관할 점수가 칸 하나의 판정에 얼마나 기대는가.

두 층(v2) 코딩에서 문서 × 통제 × 층 칸을 하나씩 뒤집어(true ↔ false) 관할 × 통제 점수가 바뀌는지 본다.
- 아래로: 지금 true 인 칸 하나를 false 로 하면 관할 점수가 내려간다 = 그 점수를 받치는 문서가 그 칸 하나뿐.
- 위로:   지금 false 인 칸 하나를 true 로 하면 관할 점수가 올라간다 = 판정 하나로 결론이 달라질 수 있는 자리.
note 에 'borderline:' 이 있는 칸(어느 코더의 note 든)은 따로 표시한다 — 결론이 '애매하다고 적힌 판정' 에 기대는 곳.
뒤집을 때 agent 층의 subject 는 'ai' 로 둔다(점수 3 은 따로 '에이전트 명시' 판정이 필요해서 세지 않는다).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from . import matrix as matrix_mod
from .schema import LAYERS, Control, Document, coding_version


_BORDERLINE = re.compile(r"borderline\s*(\([^)]*\))?\s*(for \w+\s*)?:")   # 코드북 G7 의 'borderline:' 표시 ('borderline 아님' 은 아님)


@dataclass
class Flip:
    layer: str
    jurisdiction: str
    control: str
    document: str
    before: bool          # 지금 판정
    score_from: int | None
    score_to: int | None
    borderline: bool


def _notes(codings: list[dict[str, Any]], doc: str, cid: str) -> str:
    out = []
    for c in codings:
        cell = ((c.get("items") or {}).get(doc) or {}).get(cid) or {}
        out.append(str(cell.get("note") or ""))
    return " ".join(out)


def flips(docs: dict[str, Document], controls: list[Control], coding: dict[str, Any],
          note_sources: list[dict[str, Any]] | None = None) -> list[Flip]:
    """관할 점수를 바꾸는 칸 뒤집기 전부. note_sources = borderline 표시를 찾을 코딩들(기본: coding 자신)."""
    if coding_version(coding) != 2:
        raise ValueError("민감도는 두 층(v2) 코딩만")
    srcs = note_sources if note_sources is not None else [coding]
    base = matrix_mod.layer_matrices(docs, controls, coding)
    out: list[Flip] = []
    for doc_id, cells in (coding.get("items") or {}).items():
        doc = docs.get(doc_id)
        if doc is None or doc.binding == 0:
            continue
        for cid, cell in (cells or {}).items():
            for layer in LAYERS:
                v = (cell.get(layer) or {}).get("covered")
                if v is None:
                    continue
                x = copy.deepcopy(coding)
                lay = x["items"][doc_id][cid][layer]
                lay["covered"] = not v
                if layer == "agent":
                    lay["subject"] = "ai" if not v else None
                m = matrix_mod.layer_matrices(docs, controls, x)[layer]
                for j in base[layer]:
                    s0, s1 = base[layer][j][cid].score, m[j][cid].score
                    if s0 != s1:
                        out.append(Flip(layer, j, cid, doc_id, v, s0, s1,
                                        bool(_BORDERLINE.search(_notes(srcs, doc_id, cid)))))
    return out


def render(flist: list[Flip], controls: list[Control], coder: str) -> str:
    names = {c.id: f"{c.num} {c.name_ko}" for c in controls}
    lay_ko = {"analog": "일반 통제", "agent": "AI·에이전트"}
    down = [f for f in flist if f.before]
    up = [f for f in flist if not f.before]
    lines = [f"# 민감도 — 칸 하나로 바뀌는 관할 점수 (코더 `{coder}`)", "",
             "문서 × 통제 × 층 칸을 하나씩 뒤집어 관할 × 통제 점수가 바뀌는 경우만 적었다. "
             "**◆ = 코더 note 에 borderline** — 결론이 애매하다고 적힌 판정에 기댄다.", "",
             f"- 아래로(그 칸 하나가 점수를 받침): **{len(down)}** · 그중 ◆ {sum(f.borderline for f in down)}",
             f"- 위로(그 칸 하나가 true 가 되면 점수가 오름): **{len(up)}** · 그중 ◆ {sum(f.borderline for f in up)}",
             "", "## 아래로 — 점수를 받치는 문서가 하나뿐", "",
             "| 층 | 관할 | 통제 | 점수 | 빼면 | 받치는 칸 | |", "|---|---|---|---|---|---|---|"]
    key = lambda f: (f.layer, f.jurisdiction, [c.id for c in controls].index(f.control))  # noqa: E731
    for f in sorted(down, key=key):
        lines.append(f"| {lay_ko[f.layer]} | {f.jurisdiction} | {names[f.control]} | {f.score_from} | {f.score_to} | "
                     f"`{f.document}` | {'◆' if f.borderline else ''} |")
    lines += ["", "## 위로 — 판정 하나로 점수가 오를 자리", "",
              "| 층 | 관할 | 통제 | 점수 | true 면 | 뒤집을 칸 | |", "|---|---|---|---|---|---|---|"]
    for f in sorted(up, key=key):
        lines.append(f"| {lay_ko[f.layer]} | {f.jurisdiction} | {names[f.control]} | {f.score_from} | {f.score_to} | "
                     f"`{f.document}` | {'◆' if f.borderline else ''} |")
    lines.append("")
    return "\n".join(lines)
