"""평가 채점 — 신호에서 레벨을 도출하고, 기관별 프로필(단일 등급 금지)·비교·평가자 간 kappa.

레벨은 rubric.derive_level 이 신호 응답에서 도출한다(여기서 다시 계산하지 않는다).
kappa 는 두 수준에서 잰다:
  - 신호 단위: 두 평가자가 모두 true/false 로 적은 (차원,신호) 의 관찰 일치 → 더 엄격한 재현성 지표.
  - 도출 레벨: 차원별 레벨 수열의 선형가중 κ.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from . import kappa as kappa_mod
from .rubric import GROUPS, Derivation, Rubric, derive_level


@dataclass
class Profile:
    subject: str
    period: str
    assessor: str
    provisional: bool
    scores: dict[str, dict[str, Any]]           # dim_id -> {signal_id -> {observed, evidence, ...}}
    derivations: dict[str, Derivation]          # dim_id -> Derivation (도출 결과)

    def level(self, did: str) -> int | None:
        d = self.derivations.get(did)
        return d.level if d else None

    def group_distribution(self, rubric: Rubric) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for g, dims in rubric.groups().items():
            c: Counter = Counter()
            for d in dims:
                lv = self.level(d.id)
                c["unknown" if lv is None else str(lv)] += 1
            out[g] = dict(c)
        return out

    def verified_count(self, rubric: Rubric) -> tuple[int, int, int]:
        """(검증 3, 증거없음 0, 코딩된 차원 수=분모)."""
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


def build_profile(assessment: dict[str, Any], rubric: Rubric) -> Profile:
    scores = dict(assessment.get("scores") or {})
    derivations: dict[str, Derivation] = {}
    for d in rubric.dimensions:
        derivations[d.id] = derive_level(d, scores.get(d.id) or {})
    return Profile(
        subject=assessment.get("subject", "?"),
        period=assessment.get("period", "?"),
        assessor=assessment.get("assessor", "?"),
        provisional=bool(assessment.get("provisional")),
        scores=scores,
        derivations=derivations,
    )


# ── 평가자 간 일치도 ──

def _signal_vectors(a: dict[str, Any], b: dict[str, Any], rubric: Rubric) -> tuple[list[bool], list[bool], list[str]]:
    """두 평가자가 모두 true/false 로 적은 (차원,신호) 의 관찰값."""
    va: list[bool] = []
    vb: list[bool] = []
    keys: list[str] = []
    sa, sb = a.get("scores") or {}, b.get("scores") or {}
    for d in rubric.dimensions:
        for s in d.signals:
            ca = (sa.get(d.id) or {}).get(s.id)
            cb = (sb.get(d.id) or {}).get(s.id)
            if not ca or not cb:
                continue
            oa, ob = ca.get("observed"), cb.get("observed")
            if oa is None or ob is None:
                continue
            va.append(bool(oa))
            vb.append(bool(ob))
            keys.append(f"{d.id}.{s.id}")
    return va, vb, keys


def compare_assessors(a: dict[str, Any], b: dict[str, Any], rubric: Rubric) -> dict[str, Any]:
    pa, pb = build_profile(a, rubric), build_profile(b, rubric)
    # 신호 단위
    sva, svb, _ = _signal_vectors(a, b, rubric)
    # 도출 레벨 단위
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
        "n_signals": len(sva),
        "signal_kappa": kappa_mod.cohen_kappa(sva, svb),
        "n_dims": len(la),
        "level_kappa": kappa_mod.cohen_kappa(la, lb),
        "disagreements": disagreements,
    }


# ── 렌더링 ──

_LEVEL_MARK = {0: "0", 1: "1", 2: "2", 3: "3", None: "?"}


def render_profile(profile: Profile, rubric: Rubric) -> str:
    v, z, coded = profile.verified_count(rubric)
    lines = [
        f"# 내부통제 평가 프로필 — {profile.subject} ({profile.period})",
        "",
        f"평가자 `{profile.assessor}`" + (" · provisional (잠정)" if profile.provisional else ""),
        "",
        "레벨은 **신호에서 도출**된다(직접 고르지 않음). 0 증거없음 · 1 언급 · 2 구체 · 3 검증 · `?` 미평가.",
        "**레벨은 '공개 증거 수준' 이지 '통제 유무' 가 아니다.**",
        "",
        f"코딩된 {coded} 차원 중 — 검증(3) **{v}** · 증거없음(0) **{z}** · 미평가 {len(rubric.dimensions) - coded}",
        "",
        "| 그룹 | # | 차원 | 레벨 | 발화 신호 (증거부족=↓) |",
        "|---|---|---|---|---|",
    ]
    for g, dims in rubric.groups().items():
        for d in dims:
            der = profile.derivations[d.id]
            mark = _LEVEL_MARK.get(der.level, "?")
            fired = ", ".join(der.fired)
            if der.downgraded:
                fired += ("; " if fired else "") + "↓" + ", ↓".join(der.downgraded)
            lines.append(f"| {g} | {d.num} | {d.name_ko} | **{mark}** | {fired} |")
    dist = profile.group_distribution(rubric)
    lines += ["", "## 그룹별 분포", ""]
    for g in GROUPS:
        dd = dist[g]
        parts = " · ".join(f"L{k} {dd[k]}" for k in ("3", "2", "1", "0", "unknown") if k in dd)
        lines.append(f"- **{g}**: {parts}")
    lines += ["", "`↓` = 신호를 관찰했으나(observed:true) 증거가 약해(보도 등) 그 레벨로 발화하지 못함.", ""]
    return "\n".join(lines) + "\n"


_HEAT = {None: "–", 0: "0", 1: "1", 2: "2", 3: "3"}


def render_comparison(profiles: list[Profile], rubric: Rubric) -> str:
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
    sk: kappa_mod.KappaResult = result["signal_kappa"]
    lk: kappa_mod.KappaResult = result["level_kappa"]

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [
        f"# 평가자 간 일치도 — {result['subject']}: `{result['assessor_a']}` vs `{result['assessor_b']}`",
        "",
        "| 단위 | n | 관측 일치율 | κ (비가중) | κ (선형가중) | Landis–Koch |",
        "|---|---|---|---|---|---|",
        f"| 신호 (관찰 true/false) | {result['n_signals']} | {f(sk.observed_agreement)} | {f(sk.kappa)} | – | {sk.landis_koch()} |",
        f"| 도출 레벨 (0–3) | {result['n_dims']} | {f(lk.observed_agreement)} | {f(lk.kappa)} | {f(lk.weighted_kappa)} | {lk.landis_koch()} |",
        "",
        "신호 κ 가 더 엄격한 재현성 지표다 — 두 평가자가 같은 공개 자료에서 같은 신호를 봤는가.",
        "",
    ]
    if result["disagreements"]:
        lines.append("## 도출 레벨 불일치 차원")
        for did, a, b in result["disagreements"]:
            lines.append(f"- `{did}`: {a} vs {b}")
    else:
        lines.append("도출 레벨 불일치 없음.")
    return "\n".join(lines) + "\n"
