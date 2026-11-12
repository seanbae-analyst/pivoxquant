"""AI 에이전트 보안 사건 레지스트리 — 사건 × 통제 교차표.

규제 매트릭스(문서가 무엇을 요구하나)와 나란히 놓으면 "실제 사건에서 실패한 통제" 와
"구속력 있는 규정이 약한 통제" 가 겹치는지 숫자로 본다. 사건 수는 증거 수준별로 나눠 센다 —
보도(press)만으로 확인된 사건을 1차(primary)와 같은 무게로 섞지 않는다.
"""

from __future__ import annotations

import re
from datetime import date

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .registry import REGISTRY_DIR

AI_ROLES = ("attacker_used_ai_agent", "attacker_used_ai_tooling", "victim_ai_system_exploited",
            "ai_vulnerability_disclosed", "suspected", "ai_system_misbehaved", "none")
EVIDENCE = ("primary", "vendor", "press")
JURS = ("KR", "US", "EU", "INTL", "OTHER")

AI_ROLE_KO = {
    "attacker_used_ai_agent": "공격자가 에이전트 사용",
    "attacker_used_ai_tooling": "공격자가 AI 도구 보조",
    "victim_ai_system_exploited": "피해 측 AI 시스템 침해",
    "ai_vulnerability_disclosed": "AI 취약점 공개",
    "suspected": "AI 관여 추정",
    "ai_system_misbehaved": "AI 시스템이 스스로 일탈(평가·연구 중)",
    "none": "AI 관여 없음(비교 사례)",
}


class IncidentError(ValueError):
    pass


@dataclass
class Incident:
    id: str
    date: str
    title: str
    jurisdiction: str
    ai_role: str
    evidence_level: str
    source_url: str
    related_controls: list[str] = field(default_factory=list)
    target_sector: str = "unknown"
    detected_by: str = "unknown"
    source_checked: str = ""
    summary: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any], control_ids: set[str]) -> "Incident":
        if not isinstance(d, dict):
            raise IncidentError(f"incidents 항목은 매핑이어야 함 (받음: {type(d).__name__})")
        for k in ("id", "date", "title", "jurisdiction", "ai_role", "evidence_level", "source_url"):
            if not d.get(k):
                raise IncidentError(f"{d.get('id', '?')}: 필수 필드 없음 {k}")
        if d["ai_role"] not in AI_ROLES:
            raise IncidentError(f"{d['id']}: ai_role {d['ai_role']!r}")
        if d["evidence_level"] not in EVIDENCE:
            raise IncidentError(f"{d['id']}: evidence_level {d['evidence_level']!r}")
        if d["jurisdiction"] not in JURS:
            raise IncidentError(f"{d['id']}: jurisdiction {d['jurisdiction']!r}")
        rc = d.get("related_controls") or []
        if not isinstance(rc, list):
            raise IncidentError(f"{d['id']}: related_controls 는 목록이어야 함 (받음: {rc!r})")
        bad = [c for c in rc if c not in control_ids]
        if bad:
            raise IncidentError(f"{d['id']}: 모르는 통제 {bad}")
        kw = {k: d[k] for k in cls.__dataclass_fields__ if k in d and d[k] is not None}
        kw["date"] = _norm_date(kw["date"], d["id"])
        kw["related_controls"] = list(d.get("related_controls") or [])
        return cls(**kw)


_DATE_RE = re.compile(r"^(\d{4})[-./](\d{1,2})(?:[-./](\d{1,2}))?$")


def _norm_date(v: Any, iid: str) -> str:
    """'YYYY-MM-DD' 또는 'YYYY-MM' 로 맞춘다. 글자 정렬(최신순)이 날짜 순과 같아야 해서
    '2026.03.01' 같은 표기는 하이픈으로 바꾸고, 못 읽으면 오류."""
    if isinstance(v, date):
        return v.isoformat()[:10]
    m = _DATE_RE.match(str(v).strip())
    if not m:
        raise IncidentError(f"{iid}: date 는 YYYY-MM-DD 또는 YYYY-MM (받음: {v!r})")
    y, mo, dd = m.group(1), int(m.group(2)), m.group(3)
    if not 1 <= mo <= 12 or (dd and not 1 <= int(dd) <= 31):
        raise IncidentError(f"{iid}: 없는 날짜 {v!r}")
    return f"{y}-{mo:02d}" + (f"-{int(dd):02d}" if dd else "")


def load_incidents(registry_dir: Path = REGISTRY_DIR, control_ids: set[str] | None = None) -> list[Incident]:
    p = registry_dir / "incidents.yaml"
    if not p.exists():
        return []
    if control_ids is None:
        from .registry import load_controls
        control_ids = {c.id for c in load_controls(registry_dir)}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise IncidentError(f"incidents.yaml: YAML 문법 오류 — {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("incidents") or [], list):
        raise IncidentError("incidents.yaml: 최상위에 incidents: [ … ] 목록이 있어야 함")
    out = [Incident.from_dict(d, control_ids) for d in data.get("incidents") or []]
    ids = [i.id for i in out]
    if len(set(ids)) != len(ids):
        raise IncidentError("incidents.yaml: 중복 id")
    return out


def control_counts(incidents: list[Incident]) -> dict[str, dict[str, int]]:
    """통제 id → {total, primary, vendor, press}. 한 사건이 여러 통제에 걸리면 각각 센다."""
    out: dict[str, dict[str, int]] = {}
    for i in incidents:
        for c in i.related_controls:
            row = out.setdefault(c, {"total": 0, "primary": 0, "vendor": 0, "press": 0})
            row["total"] += 1
            row[i.evidence_level] += 1
    return out


def render_markdown(incidents: list[Incident], controls) -> str:
    cc = control_counts(incidents)
    roles = Counter(i.ai_role for i in incidents)
    ev = Counter(i.evidence_level for i in incidents)
    lines = [
        f"# AI 에이전트 보안 사건 — {len(incidents)}건",
        "",
        "증거 수준: " + " · ".join(f"{k} {ev.get(k, 0)}" for k in EVIDENCE),
        "",
        "AI 역할: " + " · ".join(f"{AI_ROLE_KO[k]} {roles[k]}" for k in AI_ROLES if roles.get(k)),
        "",
        "## 통제별 — 이 통제가 실패했거나 관련된 사건 수",
        "",
        "| # | 통제 | 전체 | 1차 | 벤더 | 보도 |",
        "|---|---|---|---|---|---|",
    ]
    for c in controls:
        r = cc.get(c.id, {"total": 0, "primary": 0, "vendor": 0, "press": 0})
        lines.append(f"| {c.num} | {c.name_ko} | **{r['total']}** | {r['primary']} | {r['vendor']} | {r['press']} |")
    lines += ["", "related_controls 는 finder 판단이다 — 논문에 쓰려면 2차 코딩 대상.", "", "## 목록 (최신순)", ""]
    for i in sorted(incidents, key=lambda x: x.date, reverse=True):
        ctl = ", ".join(i.related_controls) or "—"
        lines.append(f"- {i.date} · {i.jurisdiction} · {AI_ROLE_KO[i.ai_role]} · {i.evidence_level} — "
                     f"[{i.title}]({i.source_url}) · 통제: {ctl}")
    return "\n".join(lines) + "\n"
