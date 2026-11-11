"""코더 간 일치도 — Cohen's kappa (비가중·선형가중).

외부 의존 없이 순수 파이썬. 두 코더가 모두 null 아닌 셀만 쓴다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Hashable, Sequence

from .schema import Control, Document, cell_score


@dataclass
class KappaResult:
    n: int
    observed_agreement: float
    kappa: float | None          # 비가중
    weighted_kappa: float | None  # 선형가중 (서열 점수용). 범주형엔 None
    categories: list[Any]

    def landis_koch(self) -> str:
        k = self.kappa
        if k is None:
            return "n/a"
        if k < 0:
            return "poor"
        if k < 0.21:
            return "slight"
        if k < 0.41:
            return "fair"
        if k < 0.61:
            return "moderate"
        if k < 0.81:
            return "substantial"
        return "almost perfect"


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> KappaResult:
    if len(a) != len(b):
        raise ValueError("길이가 다름")
    n = len(a)
    if n == 0:
        return KappaResult(0, 0.0, None, None, [])
    cats = sorted(set(a) | set(b), key=lambda x: (x is None, x))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    kappa = None if pe == 1.0 else (po - pe) / (1 - pe)

    weighted = None
    if all(isinstance(c, (int, float)) for c in cats) and len(cats) > 1:
        lo, hi = min(cats), max(cats)
        span = hi - lo
        # 가중 불일치: |i-j| / span
        obs = sum(abs(x - y) / span for x, y in zip(a, b)) / n  # type: ignore[operator]
        exp = sum(
            (ca[i] / n) * (cb[j] / n) * abs(i - j) / span  # type: ignore[operator]
            for i in cats for j in cats
        )
        weighted = None if exp == 0 else 1 - obs / exp
    return KappaResult(n, po, kappa, weighted, cats)


def paired_cells(
    coding_a: dict[str, Any],
    coding_b: dict[str, Any],
    docs: dict[str, Document],
    controls: list[Control],
) -> tuple[list[tuple[str, str]], list[bool], list[bool], list[int], list[int]]:
    """두 코딩에서 공통으로 (null 아닌) 코딩된 셀.

    반환: keys, covered_a, covered_b, score_a, score_b
    """
    keys: list[tuple[str, str]] = []
    cov_a: list[bool] = []
    cov_b: list[bool] = []
    sc_a: list[int] = []
    sc_b: list[int] = []
    items_a = coding_a.get("items") or {}
    items_b = coding_b.get("items") or {}
    for doc_id in sorted(set(items_a) & set(items_b)):
        doc = docs[doc_id]
        if doc.binding == 0:
            continue
        for c in controls:
            ca = (items_a[doc_id] or {}).get(c.id)
            cb = (items_b[doc_id] or {}).get(c.id)
            if not ca or not cb:
                continue
            va, vb = ca.get("covered"), cb.get("covered")
            if va is None or vb is None:
                continue
            keys.append((doc_id, c.id))
            cov_a.append(bool(va))
            cov_b.append(bool(vb))
            sa, sb = cell_score(doc, va), cell_score(doc, vb)
            assert sa is not None and sb is not None
            sc_a.append(sa)
            sc_b.append(sb)
    return keys, cov_a, cov_b, sc_a, sc_b


def compare_coders(
    coding_a: dict[str, Any],
    coding_b: dict[str, Any],
    docs: dict[str, Document],
    controls: list[Control],
) -> dict[str, Any]:
    keys, cov_a, cov_b, sc_a, sc_b = paired_cells(coding_a, coding_b, docs, controls)
    disagreements = [k for k, x, y in zip(keys, cov_a, cov_b) if x != y]
    return {
        "coder_a": coding_a.get("coder"),
        "coder_b": coding_b.get("coder"),
        "n_cells": len(keys),
        "coverage": cohen_kappa(cov_a, cov_b),
        "score": cohen_kappa(sc_a, sc_b),
        "disagreements": disagreements,
    }


def render_markdown(result: dict[str, Any]) -> str:
    cov: KappaResult = result["coverage"]
    sc: KappaResult = result["score"]

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [
        f"# 코더 간 일치도 — `{result['coder_a']}` vs `{result['coder_b']}`",
        "",
        f"공통 코딩 셀: **{result['n_cells']}** (둘 다 null 이 아닌 문서 × 통제)",
        "",
        "| 지표 | 관측 일치율 | κ (비가중) | κ (선형가중) | Landis–Koch |",
        "|---|---|---|---|---|",
        f"| 커버 여부 (true/false) | {f(cov.observed_agreement)} | {f(cov.kappa)} | – | {cov.landis_koch()} |",
        f"| 셀 점수 (0–3) | {f(sc.observed_agreement)} | {f(sc.kappa)} | {f(sc.weighted_kappa)} | {sc.landis_koch()} |",
        "",
        "점수 κ 는 문서의 binding·names_agents 가 같으므로 커버 여부 κ 와 같거나 가깝다. 두 값이 벌어지면 코딩 범위가 달라서다.",
        "",
    ]
    if result["disagreements"]:
        lines += ["## 불일치 셀", ""]
        for doc_id, cid in result["disagreements"]:
            lines.append(f"- `{doc_id}` × `{cid}`")
    else:
        lines.append("불일치 셀 없음.")
    return "\n".join(lines) + "\n"
