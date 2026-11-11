"""평가 채점 — 기관별 프로필(단일 등급 금지)과 기관 간 비교, 평가자 간 kappa.

핵심 규칙(rubric.yaml scoring_rules):
- 차원 레벨을 하나의 등급으로 합산하지 않는다. 그룹별 분포와 "검증(3)/증거없음(0) 차원 수" 로 보여 준다.
- unknown(level null) 은 0 과 구분해 분모에서 뺀다.
- press 증거만으로 레벨 3 을 허용하지 않는다(rubric.validate_assessment 에서 막음).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from . import kappa as kappa_mod
from .rubric import GROUPS, Rubric


@dataclass
class Profile:
    subject: str
    period: str
    assessor: str
    provisional: bool
    cells: dict[str, dict[str, Any]]          # dim_id -> {level, evidence, source_url, evidence_level}

    def level(self, did: str) -> int | None:
        c = self.cells.get(did)
        return c.get("level") if c else None

    def group_distribution(self, rubric: Rubric) -> dict[str, dict[str, int]]:
        """그룹 -> {level_str: count}. unknown 은 'unknown' 키."""
        out: dict[str, dict[str, int]] = {}
        for g, dims in rubric.groups().items():
            c: Counter = Counter()
            for d in dims:
                lv = self.level(d.id)
                c["unknown" if lv is None else str(lv)] += 1
            out[g] = dict(c)
        return out

    def verified_count(self, rubric: Rubric) -> tuple[int, int, int]:
        """(검증 3 차원 수, 증거없음 0 차원 수, 코딩된 차원 수=분모)."""
        v = z = coded = 0
        for d in rubric.dimensions:
            lv = self.level(d.id)
            if lv is None:
                continue
            coded += 1
            if lv == 3:
                v += 1
            if lv == 0:
                z += 1
        return v, z, coded


def build_profile(assessment: dict[str, Any]) -> Profile:
    return Profile(
        subject=assessment.get("subject", "?"),
        period=assessment.get("period", "?"),
        assessor=assessment.get("assessor", "?"),
        provisional=bool(assessment.get("provisional")),
        cells=dict(assessment.get("scores") or {}),
    )


# ── 평가자 간 일치도 (같은 기관·같은 기간을 두 사람이 평가) ──

def compare_assessors(a: dict[str, Any], b: dict[str, Any], rubric: Rubric) -> dict[str, Any]:
    pa, pb = build_profile(a), build_profile(b)
    la: list[int] = []
    lb: list[int] = []
    disagreements: list[tuple[str, int, int]] = []
    for d in rubric.dimensions:
        va, vb = pa.level(d.id), pb.level(d.id)
        if va is None or vb is None:
            continue
        la.append(va)
        lb.append(vb)
        if va != vb:
            disagreements.append((d.id, va, vb))
    return {
        "subject": pa.subject,
        "assessor_a": pa.assessor,
        "assessor_b": pb.assessor,
        "n": len(la),
        "kappa": kappa_mod.cohen_kappa(la, lb),
        "disagreements": disagreements,
    }


# ── 렌더링 ──

_LEVEL_MARK = {0: "0", 1: "1", 2: "2", 3: "3", None: "?"}


def render_profile(profile: Profile, rubric: Rubric) -> str:
    v, z, coded = profile.verified_count(rubric)
    lines = [
        f"# 내부통제 평가 프로필 — {profile.subject} ({profile.period})",
        "",
        f"평가자 `{profile.assessor}`"
        + (" · provisional (잠정)" if profile.provisional else ""),
        "",
        "레벨: 0 증거 없음 · 1 언급 · 2 구체 · 3 검증 · `?` 미평가. **레벨은 '공개 증거 수준' 이지 '통제 유무' 가 아니다.**",
        "",
        f"코딩된 {coded} 차원 중 — 검증(3) **{v}** · 증거없음(0) **{z}** · 미평가 {len(rubric.dimensions) - coded}",
        "",
        "| 그룹 | # | 차원 | 레벨 | 증거수준 | 근거 |",
        "|---|---|---|---|---|---|",
    ]
    for g, dims in rubric.groups().items():
        for d in dims:
            cell = profile.cells.get(d.id) or {}
            lv = cell.get("level")
            mark = _LEVEL_MARK.get(lv, "?")
            el = cell.get("evidence_level", "") if lv else ""
            ev = (cell.get("evidence", "") or "")[:70]
            lines.append(f"| {g} | {d.num} | {d.name_ko} | **{mark}** | {el} | {ev} |")
    dist = profile.group_distribution(rubric)
    lines += ["", "## 그룹별 분포", ""]
    for g in GROUPS:
        d = dist[g]
        parts = " · ".join(f"L{k} {d[k]}" for k in ("3", "2", "1", "0", "unknown") if k in d)
        lines.append(f"- **{g}**: {parts}")
    return "\n".join(lines) + "\n"


_HEAT = {None: "–", 0: "0", 1: "1", 2: "2", 3: "3"}


def render_comparison(profiles: list[Profile], rubric: Rubric) -> str:
    """기관 × 차원 히트 격자. 단일 등급 없음 — 차원별 레벨만."""
    if not profiles:
        return "평가 없음.\n"
    header = "| # | 차원 | " + " | ".join(p.subject for p in profiles) + " |"
    sep = "|---|---|" + "|".join(["---"] * len(profiles)) + "|"
    lines = [
        "# 기관 간 비교 — 차원별 증거 수준 (단일 등급 없음)",
        "",
        "`–` 미평가. 국가·공시체계가 다르면 레벨을 직접 비교하지 말 것(pitfalls).",
        "",
        header, sep,
    ]
    for d in rubric.dimensions:
        row = [str(d.num), d.name_ko]
        for p in profiles:
            row.append(_HEAT.get(p.level(d.id), "–"))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def render_kappa(result: dict[str, Any]) -> str:
    k: kappa_mod.KappaResult = result["kappa"]

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [
        f"# 평가자 간 일치도 — {result['subject']}: `{result['assessor_a']}` vs `{result['assessor_b']}`",
        "",
        f"공통 평가 차원: **{result['n']}**",
        "",
        "| 지표 | 관측 일치율 | κ (비가중) | κ (선형가중) | Landis–Koch |",
        "|---|---|---|---|---|",
        f"| 차원 레벨 (0–3) | {f(k.observed_agreement)} | {f(k.kappa)} | {f(k.weighted_kappa)} | {k.landis_koch()} |",
        "",
    ]
    if result["disagreements"]:
        lines.append("## 불일치 차원")
        for did, a, b in result["disagreements"]:
            lines.append(f"- `{did}`: {a} vs {b}")
    else:
        lines.append("불일치 없음.")
    return "\n".join(lines) + "\n"
