"""코더 간 일치도 — Cohen's kappa (비가중·선형가중).

외부 의존 없이 순수 파이썬. 두 코더가 모두 null 아닌 셀만 쓴다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Hashable, Sequence

from .schema import LAYERS, Control, Document, cell_score, coding_version, layer_view


@dataclass
class KappaResult:
    n: int
    observed_agreement: float | None  # n=0 이면 None (0.000 이 아니라 n/a)
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
        return KappaResult(0, None, None, None, [])
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
        doc = docs.get(doc_id)
        if doc is None or doc.binding == 0:
            continue
        for c in controls:
            ca = (items_a[doc_id] or {}).get(c.id)
            cb = (items_b[doc_id] or {}).get(c.id)
            if not isinstance(ca, dict) or not isinstance(cb, dict):
                continue
            va, vb = ca.get("covered"), cb.get("covered")
            if not isinstance(va, bool) or not isinstance(vb, bool):
                continue
            keys.append((doc_id, c.id))
            cov_a.append(va)
            cov_b.append(vb)
            sa, sb = cell_score(doc, va, ca.get("names_agent")), cell_score(doc, vb, cb.get("names_agent"))
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
        # 방향: (문서, 통제, a 의 값) — a 가 true 면 'a 만 다룸'
        "directions": [(k[0], k[1], x) for k, x, y in zip(keys, cov_a, cov_b) if x != y],
        "n_true_a": sum(cov_a), "n_true_b": sum(cov_b),
        "n_both_true": sum(1 for x, y in zip(cov_a, cov_b) if x and y),
    }


VIEW_KO = {"": "커버 여부", "analog": "일반 통제 층", "agent": "AI·에이전트 층",
           "either": "둘 중 하나 (일반 ∨ AI) — v1 의 covered 와 견주는 값"}


def compare(
    coding_a: dict[str, Any], coding_b: dict[str, Any], docs: dict[str, Document], controls: list[Control]
) -> dict[str, Any]:
    """두 코딩을 견줄 수 있는 모든 단위로 비교한다.
    둘 다 두 층(v2) → analog · agent · either / 한쪽만 v2 → either(v2) vs covered(v1) / 둘 다 v1 → covered."""
    va, vb = coding_version(coding_a), coding_version(coding_b)
    if va == 2 and vb == 2:
        labels = list(LAYERS) + ["either"]
    elif va == 2 or vb == 2:
        labels = ["either"]
    else:
        labels = [""]
    views: dict[str, dict[str, Any]] = {}
    for lab in labels:
        a = layer_view(coding_a, lab) if lab else coding_a
        b = layer_view(coding_b, lab) if lab else coding_b
        views[lab] = compare_coders(a, b, docs, controls)
    out: dict[str, Any] = {"coder_a": coding_a.get("coder"), "coder_b": coding_b.get("coder"),
                           "versions": (va, vb), "views": views}
    if va == 2 and vb == 2:
        out["subject"] = _subject_agreement(coding_a, coding_b, docs, controls)
    return out


def _subject_agreement(a: dict[str, Any], b: dict[str, Any], docs: dict[str, Document], controls: list[Control]) -> dict[str, Any]:
    """둘 다 agent 층을 true 로 본 칸에서 subject(agent / ai)가 같은가."""
    same = 0
    diff: list[tuple[str, str, Any, Any]] = []
    ia, ib = a.get("items") or {}, b.get("items") or {}
    for doc_id in sorted(set(ia) & set(ib)):
        doc = docs.get(doc_id)
        if doc is None or doc.binding == 0:
            continue
        for c in controls:
            ga = ((ia[doc_id] or {}).get(c.id) or {}).get("agent") or {}
            gb = ((ib[doc_id] or {}).get(c.id) or {}).get("agent") or {}
            if ga.get("covered") is True and gb.get("covered") is True:
                if ga.get("subject") == gb.get("subject"):
                    same += 1
                else:
                    diff.append((doc_id, c.id, ga.get("subject"), gb.get("subject")))
    return {"n": same + len(diff), "same": same, "diff": diff}


def render_compare(result: dict[str, Any]) -> str:
    a, b = result["coder_a"], result["coder_b"]

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [f"# 코더 간 일치도 — `{a}` vs `{b}`", "", f"A = `{a}` · B = `{b}`", ""]
    va, vb = result["versions"]
    if va != vb:
        lines += ["한쪽은 한 칸(v1 covered), 한쪽은 두 층(v2) 코딩이다 — v2 는 '일반 또는 AI 중 하나라도 다룸' 으로 접어 견준다. "
                  "기준이 다른 두 코딩의 비교라 κ 는 참고용이다.", ""]
    lines += ["| 단위 | 칸 | A 참 | B 참 | 둘 다 참 | 관측 일치율 | κ | 점수 κ (가중) | Landis–Koch |",
              "|---|---|---|---|---|---|---|---|---|"]
    for lab, r in result["views"].items():
        cov, sc = r["coverage"], r["score"]
        lines.append(f"| {VIEW_KO[lab]} | {r['n_cells']} | {r['n_true_a']} | {r['n_true_b']} | {r['n_both_true']} | "
                     f"{f(cov.observed_agreement)} | **{f(cov.kappa)}** | {f(sc.kappa)} ({f(sc.weighted_kappa)}) | {cov.landis_koch()} |")
    lines += ["", "칸 = 둘 다 true/false 로 코딩한 문서 × 통제. 점수 κ 는 문서의 binding 이 같아 커버 κ 보다 높게 나온다 — 커버 κ 가 재현성 지표다.", ""]
    subj = result.get("subject")
    if subj:
        lines += [f"AI·에이전트 층을 둘 다 true 로 본 {subj['n']}칸 중 대상(agent / ai)이 같은 칸 **{subj['same']}**"
                  + (" · 다른 칸: " + ", ".join(f"`{d}`×{c} ({x}/{y})" for d, c, x, y in subj["diff"]) if subj["diff"] else "") + ".", ""]
    for lab, r in result["views"].items():
        if lab == "either" and len(result["views"]) > 1:
            continue  # 층별 목록이 이미 있다
        title = VIEW_KO[lab].split(" — ")[0]
        if not r["directions"]:
            lines += [f"## 불일치 — {title}", "", "없음.", ""]
            continue
        lines += [f"## 불일치 {len(r['directions'])}칸 — {title}", ""]
        for doc_id, cid, a_true in r["directions"]:
            lines.append(f"- `{doc_id}` × `{cid}` — {'A 만 다룸' if a_true else 'B 만 다룸'}")
        lines.append("")
    return "\n".join(lines)


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
