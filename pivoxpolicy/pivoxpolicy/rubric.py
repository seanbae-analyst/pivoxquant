"""평가 루브릭 스키마·로더.

루브릭 = 차원(dimension) 목록. 각 차원은 레벨 0~3 정의와 공개 증거 출처·근거(basis)를 갖는다.
평가(assessment) 는 한 기관·한 기간에 대해 차원마다 {level, evidence, source_url, evidence_level} 를 적은 것.
점수는 평가자가 매긴 level 을 그대로 쓴다(문서 코딩과 달리 자동 계산이 아니다 — 증거 수준 판단 자체가 코딩이다).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .registry import REGISTRY_DIR

GROUPS = ("agent_control", "connection", "testing", "response")
EVIDENCE_LEVELS = ("primary", "press", "vendor", "unverified")
LEVEL_RANGE = (0, 1, 2, 3)


class RubricError(ValueError):
    pass


@dataclass
class Level:
    level: int
    label_ko: str
    criterion: str


@dataclass
class Dimension:
    id: str
    num: int
    group: str
    name_ko: str
    name_en: str
    question: str
    levels: list[Level]
    public_evidence_sources: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Dimension":
        if d.get("group") not in GROUPS:
            raise RubricError(f"{d.get('id')}: group {d.get('group')!r} 은 {GROUPS} 중 하나")
        levels = [Level(**l) for l in d.get("levels", [])]
        if [l.level for l in levels] != [0, 1, 2, 3]:
            raise RubricError(f"{d.get('id')}: levels 는 0·1·2·3 네 개가 순서대로여야 함")
        return cls(
            id=d["id"], num=d["num"], group=d["group"], name_ko=d["name_ko"], name_en=d["name_en"],
            question=d["question"], levels=levels,
            public_evidence_sources=d.get("public_evidence_sources", []), basis=d.get("basis", []),
        )


@dataclass
class Rubric:
    dimensions: list[Dimension]
    provisional: bool
    scoring_rules: list[str]
    pitfalls: list[str]
    source_note: str = ""

    def by_id(self, did: str) -> Dimension:
        for d in self.dimensions:
            if d.id == did:
                return d
        raise KeyError(did)

    def groups(self) -> dict[str, list[Dimension]]:
        out: dict[str, list[Dimension]] = {g: [] for g in GROUPS}
        for d in self.dimensions:
            out[d.group].append(d)
        return out


def load_rubric(registry_dir: Path = REGISTRY_DIR) -> Rubric:
    p = registry_dir / "rubric.yaml"
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    dims = [Dimension.from_dict(d) for d in data["dimensions"]]
    nums = [d.num for d in dims]
    if nums != sorted(nums) or len(set(nums)) != len(nums):
        raise RubricError("rubric.yaml: num 은 중복 없이 오름차순")
    if len({d.id for d in dims}) != len(dims):
        raise RubricError("rubric.yaml: 중복 id")
    return Rubric(
        dimensions=dims,
        provisional=bool(data.get("provisional")),
        scoring_rules=data.get("scoring_rules", []),
        pitfalls=data.get("pitfalls", []),
        source_note=data.get("source_note", ""),
    )


def validate_assessment(a: dict[str, Any], rubric: Rubric) -> list[str]:
    """평가 파일의 문제점 목록. 비어 있으면 통과."""
    problems: list[str] = []
    for k in ("subject", "period", "assessor", "scores"):
        if k not in a:
            problems.append(f"필수 필드 없음: {k}")
    dim_ids = {d.id for d in rubric.dimensions}
    for did, cell in (a.get("scores") or {}).items():
        if did not in dim_ids:
            problems.append(f"알 수 없는 차원: {did}")
            continue
        if not isinstance(cell, dict) or "level" not in cell:
            problems.append(f"{did}: level 필드 필요 (0~3 또는 null)")
            continue
        lv = cell["level"]
        if lv is not None and lv not in LEVEL_RANGE:
            problems.append(f"{did}: level 은 0·1·2·3 또는 null (받음: {lv!r})")
        if lv is not None and lv > 0:
            if not cell.get("evidence"):
                problems.append(f"{did}: level {lv} 이면 evidence 필요")
            el = cell.get("evidence_level")
            if el not in EVIDENCE_LEVELS:
                problems.append(f"{did}: evidence_level 은 {EVIDENCE_LEVELS} 중 하나")
            if lv == 3 and cell.get("evidence_level") == "press":
                problems.append(f"{did}: press 증거만으로 level 3 금지 (scoring_rules)")
    return problems


def load_assessments(registry_dir: Path = REGISTRY_DIR) -> dict[str, dict[str, Any]]:
    """파일 stem → 평가 dict. TEMPLATE 은 건너뛴다."""
    out: dict[str, dict[str, Any]] = {}
    d = registry_dir / "assessments"
    if not d.exists():
        return out
    for path in sorted(d.glob("*.yaml")):
        if path.stem.upper() == "TEMPLATE":
            continue
        with path.open(encoding="utf-8") as f:
            out[path.stem] = yaml.safe_load(f)
    return out
