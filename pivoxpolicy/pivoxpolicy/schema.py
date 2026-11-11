"""레지스트리 스키마와 검증.

점수 척도 (셀 하나 = 문서 × 통제):
  0  통제를 다루지 않음 (covered: false)
  1  자율 — 가이드라인·표준·초안·감독 안내 (binding 1)
  2  구속력 있음, 에이전트를 이름 붙이지 않음 (binding 2, names_agents false/null)
  3  구속력 있음 + 에이전트를 명시 (binding 2, names_agents true)
  None  코딩 안 함 (covered: null) — 매트릭스에서 "코딩 필요"로 표시

binding 0 문서(보도자료·보고서)는 규범이 아니므로 셀 점수를 내지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

JURISDICTIONS = ("KR", "US", "EU", "INTL")

DOC_TYPES = (
    "law",                  # 법률
    "regulation",           # 시행령·감독규정·행정규칙 (구속력)
    "supervisory_guidance", # 감독기관 안내서한 (SR letter, industry letter)
    "guideline",            # 자율 가이드라인
    "standard",             # 표준 (NIST, ISO)
    "criteria",             # 평가·점검 기준
    "draft",                # 초안·협의문서
    "report",               # 보고서
    "press_release",        # 보도자료·발표
)

STATUSES = ("in_force", "final", "draft", "consultation", "announced", "superseded", "unknown")

BINDING_LEVELS = {
    0: "규범 아님 (보도자료·보고서)",
    1: "자율 (가이드라인·표준·초안·감독 안내)",
    2: "구속력 있음 (법·규정·명령)",
}

REQUIRED_DOC_FIELDS = ("id", "title", "issuer", "jurisdiction", "doc_type", "status", "binding")


class SchemaError(ValueError):
    pass


@dataclass
class Control:
    id: str
    num: int
    stage: str
    name_ko: str
    name_en: str
    employee_analog: str
    agent_requirement: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Control":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


@dataclass
class Document:
    id: str
    title: str
    issuer: str
    jurisdiction: str
    doc_type: str
    status: str
    binding: int
    names_agents: bool | None = None
    date: date | None = None
    effective: date | None = None
    url: str | None = None
    url_verified: date | None = None
    url_note: str | None = None
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    source_note: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Document":
        missing = [k for k in REQUIRED_DOC_FIELDS if k not in d]
        if missing:
            raise SchemaError(f"{d.get('id', '?')}: 필수 필드 없음 {missing}")
        kw: dict[str, Any] = {}
        for k in cls.__dataclass_fields__:
            if k == "raw":
                continue
            if k in d:
                kw[k] = d[k]
        for dk in ("date", "effective", "url_verified"):
            kw[dk] = _as_date(kw.get(dk), f"{d.get('id', '?')}.{dk}")
        doc = cls(**kw)
        doc.raw = d
        doc.validate()
        return doc

    def validate(self) -> None:
        if self.jurisdiction not in JURISDICTIONS:
            raise SchemaError(f"{self.id}: jurisdiction {self.jurisdiction!r} 은 {JURISDICTIONS} 중 하나여야 함")
        if self.doc_type not in DOC_TYPES:
            raise SchemaError(f"{self.id}: doc_type {self.doc_type!r} 은 {DOC_TYPES} 중 하나여야 함")
        if self.status not in STATUSES:
            raise SchemaError(f"{self.id}: status {self.status!r} 은 {STATUSES} 중 하나여야 함")
        if self.binding not in BINDING_LEVELS:
            raise SchemaError(f"{self.id}: binding 은 0·1·2 중 하나 (받음: {self.binding!r})")
        if self.names_agents not in (True, False, None):
            raise SchemaError(f"{self.id}: names_agents 는 true/false/null")
        if self.binding == 2 and self.doc_type in ("guideline", "standard", "draft", "report", "press_release"):
            raise SchemaError(f"{self.id}: doc_type {self.doc_type} 에 binding 2 는 모순")
        if self.binding == 0 and self.doc_type not in ("report", "press_release"):
            raise SchemaError(f"{self.id}: binding 0 은 report·press_release 에만")
        if self.url is None and not self.url_note:
            raise SchemaError(f"{self.id}: url 이 없으면 url_note 에 이유('확인 필요' 등)를 적어야 함")


def _as_date(v: Any, where: str) -> date | None:
    """YAML 이 주는 날짜 값 → date. 'YYYY-MM-DD' 만 받는다 — 연월만·한국어·숫자 연도는 정렬이 깨지니 오류로."""
    if v is None:
        return None
    if isinstance(v, datetime):  # YAML timestamp(시각 포함) — 날짜만 쓴다
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            pass
    raise SchemaError(f"{where}: 날짜는 YYYY-MM-DD (받음: {v!r}). 날을 모르면 그 달 1일로 적고 note 에 밝힌다")


def cell_score(doc: Document, covered: bool | None) -> int | None:
    """문서 × 통제 셀 점수. binding 0 문서는 None (규범 아님)."""
    if covered is None:
        return None
    if doc.binding == 0:
        return None
    if not covered:
        return 0
    if doc.binding == 1:
        return 1
    return 3 if doc.names_agents else 2


def validate_coding(coding: dict[str, Any], docs: dict[str, Document], controls: list[Control]) -> list[str]:
    """코딩 파일의 문제점 목록. 비어 있으면 통과."""
    problems: list[str] = []
    if not isinstance(coding, dict):
        return ["코딩 파일이 비었거나 매핑이 아님"]
    if not isinstance(coding.get("items") or {}, dict):
        return ["items 는 문서 id → 통제 매핑이어야 함"]
    for k in ("coder", "coded_at", "items"):
        if k not in coding:
            problems.append(f"필수 필드 없음: {k}")
    control_ids = {c.id for c in controls}
    for doc_id, cells in (coding.get("items") or {}).items():
        if doc_id not in docs:
            problems.append(f"레지스트리에 없는 문서: {doc_id}")
            continue
        if docs[doc_id].binding == 0:
            problems.append(f"{doc_id}: binding 0 문서는 코딩 대상이 아님")
        if not isinstance(cells or {}, dict):
            problems.append(f"{doc_id}: 통제 id → {{covered: …}} 매핑이어야 함")
            continue
        for cid, cell in (cells or {}).items():
            if cid not in control_ids:
                problems.append(f"{doc_id}: 알 수 없는 통제 {cid}")
                continue
            if not isinstance(cell, dict) or "covered" not in cell:
                problems.append(f"{doc_id}.{cid}: covered 필드 필요 (true/false/null)")
                continue
            if cell["covered"] is not None and not isinstance(cell["covered"], bool):
                # 1 in (True, False, None) 이 참이라 '1' 이 통과하던 것 — 타입으로 본다
                problems.append(f"{doc_id}.{cid}: covered 는 true/false/null (받음: {cell['covered']!r})")
                continue
            if cell["covered"] is True and not cell.get("evidence"):
                problems.append(f"{doc_id}.{cid}: covered true 면 evidence(조문·항목 번호) 필요")
    return problems
