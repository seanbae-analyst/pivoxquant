"""2차 코딩 합치기 · 사건 × 통제 코딩의 코더 간 일치도.

- 문서 코딩(문서 × 통제 covered)의 κ 는 kappa.compare_coders 가 이미 낸다 — 여기서는 에이전트가 낸 JSON 을
  registry/codings/<coder>.yaml 로 옮기는 것만 한다.
- 사건 코딩(사건 × 통제 실패 여부)은 registry/incidents.yaml 의 related_controls(1차)와
  registry/incident_codings/<coder>.yaml(2차)을 통제마다 참/거짓으로 펼쳐 κ 를 낸다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from . import kappa as kappa_mod
from .registry import REGISTRY_DIR

CONTROL_IDS = ("inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch")


def _q(s: Any) -> str:
    return json.dumps("" if s is None else str(s), ensure_ascii=False)


def coding_yaml(result: dict[str, Any], coder: str, basis: str, coded_at: str) -> str:
    """에이전트 JSON({items:{doc:{ctl:{covered,evidence,note}}}}) → codings YAML 글."""
    lines = [
        f"# 2차 코딩 — {coder}. AI 코더(에이전트)가 1차 코딩을 보지 않고 원문을 받아 코딩했다.",
        "# 같은 모델 계열이 1차(덱 노트 기반)와 2차(원문 기반)를 했으므로, κ 는 '입력이 다른 두 AI 판단의 일치' 이지",
        "# 사람 코더 간 신뢰도가 아니다. 논문에는 사람 코더 1명을 더해 보고하는 것이 맞다.",
        f"coder: {coder}",
        f"coded_at: {coded_at}",
        f"basis: {_q(basis)}",
        "provisional: true",
        "items:",
    ]
    for doc_id, cells in sorted((result.get("items") or {}).items()):
        lines.append(f"  {doc_id}:")
        for cid in CONTROL_IDS:
            c = (cells or {}).get(cid) or {}
            cov = c.get("covered")
            cov_s = "true" if cov is True else "false" if cov is False else "null"
            parts = [f"covered: {cov_s}"]
            if c.get("evidence"):
                parts.append(f"evidence: {_q(c['evidence'])}")
            if c.get("note"):
                parts.append(f"note: {_q(c['note'])}")
            lines.append(f"    {cid}: {{{', '.join(parts)}}}")
    return "\n".join(lines) + "\n"


def load_incident_codings(registry_dir: Path = REGISTRY_DIR) -> dict[str, dict[str, Any]]:
    d = registry_dir / "incident_codings"
    out: dict[str, dict[str, Any]] = {}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.yaml")):
        out[p.stem] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return out


def incident_vectors(first: dict[str, list[str]], second: dict[str, dict[str, bool]]) -> tuple[list[bool], list[bool], list[tuple[str, str]], dict[str, tuple[list[bool], list[bool]]]]:
    """1차 {incident: [controls]} · 2차 {incident: {control: bool}} → 공통 사건의 (사건, 통제) 참/거짓 벡터.
    셋째 값 = 불일치 (사건, 통제), 넷째 = 통제별 벡터(통제마다 κ 용)."""
    a: list[bool] = []
    b: list[bool] = []
    diff: list[tuple[str, str]] = []
    per: dict[str, tuple[list[bool], list[bool]]] = {c: ([], []) for c in CONTROL_IDS}
    for iid in sorted(set(first) & set(second)):
        for c in CONTROL_IDS:
            x = c in (first[iid] or [])
            y = bool((second[iid] or {}).get(c))
            a.append(x)
            b.append(y)
            per[c][0].append(x)
            per[c][1].append(y)
            if x != y:
                diff.append((iid, c))
    return a, b, diff, per


def render_incident_agreement(first: dict[str, list[str]], second: dict[str, dict[str, bool]], coder_b: str) -> str:
    a, b, diff, per = incident_vectors(first, second)
    k = kappa_mod.cohen_kappa(a, b)
    n_inc = len(set(first) & set(second))

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [
        f"# 사건 × 통제 코딩 일치도 — 1차(finder) vs `{coder_b}`",
        "",
        f"공통 사건 {n_inc}건 × 통제 7 = 셀 {len(a)}. 관측 일치율 {f(k.observed_agreement)} · κ {f(k.kappa)} ({k.landis_koch()})",
        "",
        "| 통제 | 1차 참 | 2차 참 | 일치율 | κ |",
        "|---|---|---|---|---|",
    ]
    for c in CONTROL_IDS:
        x, y = per[c]
        kc = kappa_mod.cohen_kappa(x, y)
        lines.append(f"| {c} | {sum(x)} | {sum(y)} | {f(kc.observed_agreement)} | {f(kc.kappa)} |")
    lines += ["", f"## 불일치 {len(diff)}칸", ""]
    for iid, c in diff:
        side = "1차만 참" if c in (first.get(iid) or []) else "2차만 참"
        lines.append(f"- `{iid}` × {c} — {side}")
    return "\n".join(lines) + "\n"
