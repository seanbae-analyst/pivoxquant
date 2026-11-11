"""평가 루브릭 스키마·로더 + 레벨 도출 규칙.

핵심: 레벨을 평가자가 직접 고르지 않는다. 차원마다 **관찰 가능한 신호(signal)** 를 두고,
평가자는 "이 신호가 공개 자료에서 보이는가"(observed: true/false/null)와 그 **증거 수준**만 적는다.
차원의 레벨은 그로부터 **도출**된다(matrix 에서 점수를 binding×covered 로 도출한 것과 같은 원리).
그래서 두 평가자가 신호에만 동의하면 레벨이 똑같이 나온다 — 재현성·κ 가 신호 단위에서 측정된다.

도출 규칙 (derive_level):
  - 신호가 '발화(fires)' = observed==true 이고 그 증거 수준이 신호의 min_evidence 이상.
  - 레벨 = 발화한 신호들의 최고 level. 하나도 발화 안 했지만 observed==false 가 하나라도 있으면 0.
    모든 신호가 null(미확인)이면 None(미평가 — 분모에서 뺌).
  - min_evidence 로 "보도(press)만으로 레벨 3 불가" 를 구조적으로 강제한다(L3 신호는 min_evidence=primary).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .registry import REGISTRY_DIR

GROUPS = ("agent_control", "connection", "testing", "response")
EVIDENCE_LEVELS = ("primary", "press", "vendor", "unverified")
# 증거 강도 순위. primary(공시·제재문·감독기관 원문)가 가장 강하다. press·vendor 는 2차.
EVIDENCE_RANK = {"unverified": 0, "press": 1, "vendor": 1, "primary": 2}
LEVEL_RANGE = (0, 1, 2, 3)


class RubricError(ValueError):
    pass


@dataclass
class Level:
    level: int
    label_ko: str
    criterion: str


@dataclass
class Signal:
    id: str
    level: int                 # 발화 시 이 레벨을 준다 (1·2·3)
    question: str              # 평가자가 공개 자료에서 확인하는 예/아니오 질문
    min_evidence: str          # 이 신호를 인정하는 최소 증거 수준 (primary / press)
    note: str = ""

    @property
    def min_rank(self) -> int:
        return EVIDENCE_RANK[self.min_evidence]


@dataclass
class Dimension:
    id: str
    num: int
    group: str
    name_ko: str
    name_en: str
    question: str
    levels: list[Level]              # 사람이 읽는 레벨 앵커 (코드북용)
    signals: list[Signal]            # 기계가 레벨을 도출하는 규칙
    public_evidence_sources: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Dimension":
        if d.get("group") not in GROUPS:
            raise RubricError(f"{d.get('id')}: group {d.get('group')!r} 은 {GROUPS} 중 하나")
        levels = [Level(**l) for l in d.get("levels", [])]
        if [l.level for l in levels] != [0, 1, 2, 3]:
            raise RubricError(f"{d.get('id')}: levels 는 0·1·2·3 네 개가 순서대로여야 함")
        signals = [Signal(**s) for s in d.get("signals", [])]
        if not signals:
            raise RubricError(f"{d.get('id')}: signals 가 최소 1개 필요(레벨 도출 규칙)")
        sig_levels = {s.level for s in signals}
        if not sig_levels <= {1, 2, 3}:
            raise RubricError(f"{d.get('id')}: signal.level 은 1·2·3 (0 은 '발화 없음' 이라 신호가 아님)")
        if 3 not in sig_levels or 1 not in sig_levels:
            raise RubricError(f"{d.get('id')}: 레벨 1·3 신호가 각각 있어야 한다(도출 범위가 0~3 이 되도록)")
        for s in signals:
            if s.min_evidence not in EVIDENCE_RANK:
                raise RubricError(f"{d.get('id')}.{s.id}: min_evidence 는 {tuple(EVIDENCE_RANK)} 중 하나")
            if s.level == 3 and s.min_evidence != "primary":
                raise RubricError(f"{d.get('id')}.{s.id}: 레벨 3 신호는 min_evidence=primary (보도만으로 레벨 3 불가)")
        if len({s.id for s in signals}) != len(signals):
            raise RubricError(f"{d.get('id')}: 신호 id 중복")
        return cls(
            id=d["id"], num=d["num"], group=d["group"], name_ko=d["name_ko"], name_en=d["name_en"],
            question=d["question"], levels=levels, signals=signals,
            public_evidence_sources=d.get("public_evidence_sources", []), basis=d.get("basis", []),
        )

    def signal(self, sid: str) -> Signal:
        for s in self.signals:
            if s.id == sid:
                return s
        raise KeyError(sid)


@dataclass
class Derivation:
    """한 차원의 레벨 도출 결과 — 왜 그 레벨인지 추적."""
    level: int | None
    fired: list[str]            # 발화한 신호 id (레벨을 올린 것)
    downgraded: list[str]       # observed=true 지만 증거가 약해 발화 못 한 신호 id
    checked_any: bool           # observed 가 true/false 로 적힌 신호가 하나라도 있나


def derive_level(dim: Dimension, cells: dict[str, Any]) -> Derivation:
    """차원의 신호 응답(cells: signal_id -> {observed, evidence_level, ...})에서 레벨을 도출."""
    fired: list[tuple[int, str]] = []
    downgraded: list[str] = []
    checked_any = False
    any_false = False
    if not isinstance(cells, dict):
        return Derivation(None, [], [], False)
    for s in dim.signals:
        cell = cells.get(s.id)
        if not isinstance(cell, dict):
            continue
        obs = cell.get("observed")
        if obs is not True and obs is not False:  # null · 잘못된 값(1, "true") 은 미확인
            continue
        checked_any = True
        if obs is True:
            rank = EVIDENCE_RANK.get(cell.get("evidence_level", "unverified"), 0)
            if rank >= s.min_rank:
                fired.append((s.level, s.id))
            else:
                downgraded.append(s.id)
        else:
            any_false = True
    if fired:
        return Derivation(max(lv for lv, _ in fired), [sid for _, sid in fired], downgraded, True)
    if any_false:
        # 규칙: 하나도 발화 안 했는데 하나라도 false 로 확인 → 0
        return Derivation(0, [], downgraded, True)
    # 관찰은 true 인데 증거 수준이 모자라 전부 강등 — '없음(0)' 이 아니라 미평가. 증거 없음 ≠ 통제 없음.
    return Derivation(None, [], downgraded, checked_any)


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
    if not isinstance(a, dict):
        return ["평가 파일이 비었거나 매핑이 아님"]
    for k in ("subject", "period", "assessor", "scores"):
        if k not in a:
            problems.append(f"필수 필드 없음: {k}")
    scores = a.get("scores") or {}
    if not isinstance(scores, dict):
        return problems + ["scores 는 차원 id → 신호 매핑이어야 함"]
    for did, cells in scores.items():
        try:
            dim = rubric.by_id(did)
        except KeyError:
            problems.append(f"알 수 없는 차원: {did}")
            continue
        if not isinstance(cells, dict):
            problems.append(f"{did}: 신호 매핑이어야 함")
            continue
        valid_sids = {s.id for s in dim.signals}
        for sid, cell in cells.items():
            if sid not in valid_sids:
                problems.append(f"{did}.{sid}: 알 수 없는 신호 (가능: {', '.join(sorted(valid_sids))})")
                continue
            if not isinstance(cell, dict) or "observed" not in cell:
                problems.append(f"{did}.{sid}: observed 필드 필요 (true/false/null)")
                continue
            if cell["observed"] is not None and not isinstance(cell["observed"], bool):
                problems.append(f"{did}.{sid}: observed 는 true/false/null (받음: {cell['observed']!r})")
                continue
            if cell.get("observed") is True:
                if not cell.get("evidence"):
                    problems.append(f"{did}.{sid}: observed true 면 evidence 필요")
                if cell.get("evidence_level") not in EVIDENCE_LEVELS:
                    problems.append(f"{did}.{sid}: evidence_level 은 {EVIDENCE_LEVELS} 중 하나")
    # 레벨 0 = '찾아봤으나 없음' — 찾아본 출처가 적혀 있어야 한다. 없으면 미평가(null)로 둬야 한다.
    zeros = [d.id for d in rubric.dimensions
             if derive_level(d, scores.get(d.id) or {}).level == 0]
    if zeros and not a.get("sources_checked"):
        problems.append(f"레벨 0 차원 {len(zeros)}개({', '.join(zeros[:4])}…) — 찾아본 출처를 sources_checked 에 적어야 한다")
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
            data = yaml.safe_load(f)
        out[path.stem] = data if isinstance(data, dict) else {}
    return out


def render_codebook(rubric: Rubric) -> str:
    """코드북 — 두 번째 평가자가 따라올 수 있는 결정 절차 전문."""
    lines = [
        "# 평가 코드북 — 어떻게 레벨을 매기나",
        "",
        "평가자는 레벨(0~3)을 **직접 고르지 않는다.** 아래 각 신호를 공개 자료에서 확인해",
        "`observed: true/false/null` 과 **증거 수준**(primary/press/vendor)만 적는다. 레벨은 도출된다:",
        "",
        "- 신호가 **발화** = `observed: true` 이고 증거 수준이 그 신호의 최소 요건 이상.",
        "- 차원 레벨 = 발화한 신호들의 **최고 레벨**. 하나도 발화 안 했지만 하나라도 `false` 로 확인했으면 **0**.",
        "  모든 신호가 `null`(미확인)이면 **미평가**(분모에서 뺌).",
        "- `[primary 필요]` 신호는 1차 증거라야 발화한다 — **보도만으로는 그 레벨에 도달 못 한다.**",
        "",
        "증거 수준: **primary** 공시·제재문·감독기관/회사 원문 · **press** 언론 보도 · **vendor** 보안업체 분석 · **unverified** 미확인.",
        "",
    ]
    for g, dims in rubric.groups().items():
        lines.append(f"## {g}")
        lines.append("")
        for d in dims:
            lines.append(f"### {d.num}. {d.name_ko} ({d.name_en})")
            lines.append(f"- 질문: {d.question}")
            if d.public_evidence_sources:
                lines.append(f"- 어디서 보나: {', '.join(d.public_evidence_sources)}")
            if d.basis:
                lines.append(f"- 근거: {', '.join(d.basis)}")
            lines.append("- 신호:")
            for s in d.signals:
                gate = " `[primary 필요]`" if s.min_evidence == "primary" else ""
                lines.append(f"    - **L{s.level}** `{s.id}`{gate}: {s.question}")
            lines.append("- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).")
            lines.append("")
    return "\n".join(lines)
