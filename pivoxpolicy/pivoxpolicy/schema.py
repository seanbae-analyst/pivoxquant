"""레지스트리 스키마와 검증.

점수 척도 (셀 하나 = 문서 × 통제 [× 층]):
  0  통제를 다루지 않음 (covered: false)
  1  자율 — 가이드라인·표준·초안·감독 안내 (binding 1)
  2  구속력 있음, 에이전트를 이름 붙이지 않음
  3  구속력 있음 + 에이전트를 명시
  None  코딩 안 함 (covered: null) — 매트릭스에서 "코딩 필요"로 표시

binding 0 문서(보도자료·보고서)는 규범이 아니므로 셀 점수를 내지 않는다.

코딩 파일은 두 가지 모양이다 (coding_version):
  v1  통제마다 {covered, evidence}            — 2026-11-01 덱 · 2026-11-11 AI 2차 (층 구분 없음)
  v2  통제마다 {analog: {...}, agent: {...}}  — codebook: 2. registry/controls.yaml 의 두 층 규칙.
      analog 층 점수는 0~2 (에이전트 명시가 있을 수 없다), agent 층은 0~3 (근거 조항의 subject 가 agent 면 3).
v2 코딩은 layer_view() 로 한 층짜리(v1 모양)로 펴서 같은 매트릭스·κ 코드에 넣는다.
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

LAYERS = ("analog", "agent")          # 코드북 v2 의 두 층
AGENT_SUBJECTS = ("agent", "ai")       # agent 층 근거 조항의 대상: AI 에이전트 명시 / AI 시스템 일반
VIEWS = LAYERS + ("either",)           # either = analog 또는 agent (v1 의 covered 와 견줄 때)

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
    analog: dict[str, Any] = field(default_factory=dict)  # 코드북 v2: {true_if: [...], false_if: [...]}
    agent: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Control":
        optional = ("analog", "agent")
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k not in optional or k in d})  # type: ignore[arg-type]


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


def cell_score(doc: Document, covered: bool | None, names_agent: bool | None = None) -> int | None:
    """문서 × 통제 셀 점수. binding 0 문서는 None (규범 아님).
    names_agent = 이 칸의 근거가 에이전트를 명시하는가. None 이면 문서 단위 names_agents 를 쓴다(v1 코딩)."""
    if covered is None:
        return None
    if doc.binding == 0:
        return None
    if not covered:
        return 0
    if doc.binding == 1:
        return 1
    agentic = doc.names_agents if names_agent is None else names_agent
    return 3 if agentic else 2


def coding_version(coding: dict[str, Any] | None) -> int:
    """1 = 통제마다 covered 한 칸 · 2 = analog·agent 두 층 (codebook: 2)."""
    return 2 if isinstance(coding, dict) and coding.get("codebook") == 2 else 1


def is_adjudicated(coding: dict[str, Any] | None) -> bool:
    """독립 코더 둘을 칸마다 합친 조정본인가 (adjudicates: [A, B]). 조정본은 독립 판단이 아니라 κ 에서 뺀다."""
    return isinstance(coding, dict) and bool(coding.get("adjudicates"))


def independent_v2(codings: dict[str, Any]) -> list[str]:
    """κ 를 낼 수 있는 두 층(v2) 코더 — 조정본을 뺀 이름순."""
    return sorted(k for k, c in codings.items() if coding_version(c) == 2 and not is_adjudicated(c))


def primary_coder(codings: dict[str, Any]) -> str | None:
    """대표로 보일 코더 — 두 층(v2) 조정본 > 두 층 독립 코더 > 아무 코더, 각각 이름순 첫째."""
    if not codings:
        return None
    adj = sorted(k for k, c in codings.items() if coding_version(c) == 2 and is_adjudicated(c))
    if adj:
        return adj[0]
    v2 = independent_v2(codings)
    return v2[0] if v2 else sorted(codings)[0]


def validate_adjudication(coding: dict[str, Any], codings: dict[str, Any]) -> list[str]:
    """조정본 검사 — 원본 둘이 같은 칸은 원본 그대로인가, 갈린 칸(covered · agent subject)은 모두 adjudication 에 판정이 있는가.
    조정본이 아니면 빈 목록."""
    if not is_adjudicated(coding):
        return []
    srcs = coding.get("adjudicates") or []
    if len(srcs) != 2 or any(s not in codings for s in srcs):
        return [f"adjudicates 는 있는 코더 둘이어야 함: {srcs}"]
    a, b = (codings[s].get("items") or {} for s in srcs)
    mine = coding.get("items") or {}
    decided: set[tuple[str, str, str]] = set()
    problems: list[str] = []
    for d in coding.get("adjudication") or []:
        key = (d.get("document"), d.get("control"), d.get("layer"))
        if d.get("layer") not in LAYERS or d.get("follows") not in srcs or not d.get("reason"):
            problems.append(f"adjudication {key}: layer · follows(원본 코더 중 하나) · reason 필요")
        decided.add(key)

    def val(items: dict[str, Any], doc: str, cid: str, layer: str) -> tuple[Any, Any]:
        c = ((items.get(doc) or {}).get(cid) or {}).get(layer) or {}
        return c.get("covered"), (c.get("subject") if layer == "agent" else None)

    for doc in sorted(set(a) | set(b) | set(mine)):
        cids = set(a.get(doc) or {}) | set(b.get(doc) or {}) | set(mine.get(doc) or {})
        for cid in sorted(cids):
            for layer in LAYERS:
                va, vb, vc = val(a, doc, cid, layer), val(b, doc, cid, layer), val(mine, doc, cid, layer)
                key = (doc, cid, layer)
                if va == vb:
                    if vc != va:
                        problems.append(f"{doc}.{cid}.{layer}: 원본 둘이 {va} 로 같은데 조정본은 {vc}")
                    if key in decided:
                        problems.append(f"{doc}.{cid}.{layer}: 원본이 일치하는데 adjudication 에 있음")
                elif key not in decided:
                    problems.append(f"{doc}.{cid}.{layer}: 원본이 갈렸는데({va} vs {vb}) adjudication 에 판정 없음")
                elif vc not in (va, vb):
                    problems.append(f"{doc}.{cid}.{layer}: 조정 결과 {vc} 가 원본 어느 쪽도 아님")
    return problems


def _or3(a: bool | None, b: bool | None) -> bool | None:
    """세 값 OR — 하나라도 true 면 true, 둘 다 false 면 false, 그 밖(모르는 것이 섞임)은 None."""
    if a is True or b is True:
        return True
    if a is False and b is False:
        return False
    return None


def layer_view(coding: dict[str, Any], layer: str) -> dict[str, Any]:
    """두 층(v2) 코딩 → 한 층짜리(v1 모양) 코딩. layer: 'analog' | 'agent' | 'either'.
    각 칸에 names_agent 를 실어 매트릭스가 문서 단위 대신 칸 단위로 '에이전트 명시' 를 본다:
    analog 층은 늘 False, agent·either 층은 agent 칸이 true 이고 subject 가 'agent' 일 때만 True.
    v1 코딩은 그대로 돌려준다(층이 없다)."""
    if layer not in VIEWS:
        raise ValueError(f"layer 는 {VIEWS} 중 하나")
    if coding_version(coding) != 2:
        return coding
    items: dict[str, Any] = {}
    for doc_id, cells in (coding.get("items") or {}).items():
        out: dict[str, Any] = {}
        for cid, cell in (cells or {}).items() if isinstance(cells, dict) else []:
            if not isinstance(cell, dict):
                continue
            a = cell.get("analog") if isinstance(cell.get("analog"), dict) else {}
            g = cell.get("agent") if isinstance(cell.get("agent"), dict) else {}
            agentic = g.get("covered") is True and g.get("subject") == "agent"
            if layer == "analog":
                out[cid] = {"covered": a.get("covered"), "evidence": a.get("evidence", ""), "names_agent": False}
            elif layer == "agent":
                out[cid] = {"covered": g.get("covered"), "evidence": g.get("evidence", ""), "names_agent": agentic}
            else:
                ev = g.get("evidence") if g.get("covered") is True else a.get("evidence")
                out[cid] = {"covered": _or3(a.get("covered"), g.get("covered")), "evidence": ev or "", "names_agent": agentic}
        items[doc_id] = out
    return {**{k: v for k, v in coding.items() if k != "items"}, "items": items, "layer": layer}


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
    v2 = coding_version(coding) == 2
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
            if v2:
                problems += _validate_layers(f"{doc_id}.{cid}", cell)
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


def _validate_layers(where: str, cell: Any) -> list[str]:
    """v2 칸 하나: {analog: {covered, evidence}, agent: {covered, subject, evidence}, note}."""
    if not isinstance(cell, dict):
        return [f"{where}: {{analog: …, agent: …}} 매핑이어야 함"]
    out: list[str] = []
    for layer in LAYERS:
        sub = cell.get(layer)
        if not isinstance(sub, dict) or "covered" not in sub:
            out.append(f"{where}.{layer}: covered 필드 필요 (true/false/null)")
            continue
        cov = sub["covered"]
        if cov is not None and not isinstance(cov, bool):
            out.append(f"{where}.{layer}: covered 는 true/false/null (받음: {cov!r})")
            continue
        if cov is True and not sub.get("evidence"):
            out.append(f"{where}.{layer}: covered true 면 evidence(위치 + 원문 인용) 필요")
        if layer == "agent":
            subj = sub.get("subject")
            if cov is True and subj not in AGENT_SUBJECTS:
                out.append(f"{where}.agent: covered true 면 subject 는 {AGENT_SUBJECTS} 중 하나 (받음: {subj!r})")
            if cov is not True and subj is not None:
                out.append(f"{where}.agent: covered 가 true 가 아니면 subject 는 null")
    return out
