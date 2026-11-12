"""조항 단위 의무 — 업권 · 에이전트 프로필에 걸리는 조문만 골라 통제 수준을 도출한다.

관할 프리셋('한국 — 강제 규제만')은 적용 조건을 보지 않는다. 예: AI 층까지 강제인 유일한 한국 조문(AI 기본법 제34조)은
고영향 AI 에만 걸리는데, 프리셋은 정산 에이전트에도 똑같이 씌웠다. 여기서는 조문마다 적용 조건을 적고 프로필로 거른다.

모드 세 가지(강제력 × 해석)
  binding_explicit      강제 조문만. AI 를 명시한 조문(layer: agent)만 수준 2, 사람 · 계정 조문은 수준 1
  binding_interpretive  강제 조문만. 사람 · 계정 조문 중 에이전트에도 미친다고 읽을 여지가 있는 것(extends: interpretive)도 수준 2
  guideline             자율 가이드라인 · 평가기준까지. 해석 여지도 수준 2

결함과 조문을 잇는 분류(classify)
  violation             적용되는 강제 조문이 그 통제를 AI 까지 명시해 요구한다 → 위반 소지
  interpretive          강제 조문이 사람 · 계정 층만 말하고, 에이전트에 미치는지는 해석 → 해석에 따라 위반 소지
  guideline             자율 규범만 요구한다 → 가이드라인 미이행
  gap                   적용되는 조문이 없다 → 규제 공백(합법이지만 위험)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .registry import REGISTRY_DIR

OBLIGATIONS_DIR = REGISTRY_DIR / "obligations"
BINDING = frozenset({"law", "decree", "supervisory_regulation", "exchange_rule"})
FORCES = (*sorted(BINDING), "guideline", "criteria")
FORCE_KO = {"law": "법률", "decree": "시행령", "supervisory_regulation": "감독규정", "exchange_rule": "거래소 규정",
            "guideline": "가이드라인", "criteria": "평가기준"}
MODES = ("binding_explicit", "binding_interpretive", "guideline")
MODE_KO = {"binding_explicit": "강제 조문, 명시만", "binding_interpretive": "강제 조문, 해석 포함", "guideline": "가이드라인까지"}
VERIFIED = ("registry", "primary", "secondary", "none")
WHEN_KEYS = ("activities_any", "data_any", "external_llm_any", "retail", "automated_decision", "high_impact")
SECTORS = {"securities": "kr-securities.yaml"}


class ObligationError(ValueError):
    pass


def load_library(sector: str = "securities", path: Path | None = None) -> dict[str, Any]:
    if sector not in SECTORS and path is None:
        raise ObligationError(f"모르는 업권: {sector}")
    p = path or OBLIGATIONS_DIR / SECTORS[sector]
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def validate_library(lib: dict[str, Any], control_ids: set[str]) -> list[str]:
    probs, seen = [], set()
    q = lib.get("profile") or {}
    opts = {k: {o["id"] for o in (v.get("options") or [])} for k, v in q.items()}
    for ob in lib.get("obligations") or []:
        oid = ob.get("id")
        if not oid or oid in seen:
            probs.append(f"{oid}: id 가 없거나 중복")
        seen.add(oid)
        for k in ("doc", "article", "requires"):
            if not ob.get(k):
                probs.append(f"{oid}: {k} 필요")
        if ob.get("force") not in FORCES:
            probs.append(f"{oid}: force 는 {FORCES}")
        if ob.get("quote_verified", "none") not in VERIFIED:
            probs.append(f"{oid}: quote_verified 는 {VERIFIED}")
        if ob.get("quote") and ob.get("quote_verified", "none") == "none":
            probs.append(f"{oid}: 원문을 확인하지 않은 인용은 quote: null 로 둔다")
        if ob.get("runtime", True):
            if ob.get("control") not in control_ids:
                probs.append(f"{oid}: control 은 통제 id (런타임 밖이면 runtime: false)")
            if ob.get("layer") not in ("analog", "agent"):
                probs.append(f"{oid}: layer 는 analog · agent")
            if ob.get("extends") not in (None, "interpretive"):
                probs.append(f"{oid}: extends 는 interpretive 또는 비움")
            if ob.get("layer") == "agent" and ob.get("extends"):
                probs.append(f"{oid}: AI 를 명시한 조문(layer: agent)에는 extends 를 달지 않는다")
        elif not ob.get("category"):
            probs.append(f"{oid}: 런타임 밖 의무에는 category 필요")
        for k, v in (ob.get("when") or {}).items():
            if k not in WHEN_KEYS:
                probs.append(f"{oid}: when 키 {k} 는 {WHEN_KEYS}")
            elif k.endswith("_any"):
                base = k[:-4]
                bad = set(v or []) - opts.get(base, set())
                if bad:
                    probs.append(f"{oid}: when.{k} 에 모르는 값 {sorted(bad)}")
    return probs


# ── 프로필 ──

def clean_profile(lib: dict[str, Any], p: Any) -> dict[str, Any]:
    """콘솔 · API 에서 온 프로필 → 정규화. 모르는 값은 거부한다."""
    if not isinstance(p, dict):
        raise ObligationError("프로필은 JSON 객체")
    q = lib.get("profile") or {}
    out: dict[str, Any] = {"sector": lib.get("sector")}
    for key, spec in q.items():
        v = p.get(key)
        if spec.get("type") == "bool":
            out[key] = v is True
            continue
        ids = [o["id"] for o in spec.get("options") or []]
        if spec.get("multi"):
            v = v or []
            if not isinstance(v, list) or any(x not in ids for x in v):
                raise ObligationError(f"{key} 는 {ids} 중에서 고른 목록")
            out[key] = [x for x in ids if x in v]           # 순서 고정 · 중복 제거
        else:
            v = v if v is not None else ids[0]
            if v not in ids:
                raise ObligationError(f"{key} 는 {ids} 중 하나")
            out[key] = v
    return out


def high_impact(profile: dict[str, Any]) -> tuple[bool, str]:
    """AI 기본법 고영향 AI 여부 — 사용자가 판단했으면 그것을, 아니면 하는 일로 추정한다(추정은 추정이라고 말한다)."""
    h = profile.get("high_impact", "auto")
    if h == "high":
        return True, "회사가 고영향 AI 에 해당한다고 판단했다."
    if h == "not_high":
        return False, "회사가 고영향 AI 에 해당하지 않는다고 판단했다."
    if "credit" in (profile.get("activities") or []):
        return True, ("추정: 신용공여 심사는 법정 영역(대출 심사 등 개인의 권리·의무에 중대한 영향을 미치는 판단·평가)에 해당할 수 있다. "
                      "중대성은 과기정통부 판단 가이드라인으로 따로 가려야 한다.")
    return False, ("추정: 주문, 정산, 상담, 내부 업무는 법정 영역(채용, 대출 심사 같은 판단·평가)에 들지 않을 가능성이 크다. "
                   "고객에 대한 판단·평가를 한다면 다시 본다.")


def applies(ob: dict[str, Any], profile: dict[str, Any], labels: dict[str, str] | None = None) -> tuple[bool, str]:
    """조문 하나가 프로필에 걸리는가 → (걸림, 이유). 조건이 없으면 모든 증권사에 걸린다. labels: 선택지 id → 한국어."""
    when = ob.get("when") or {}
    if not when:
        return True, "모든 증권사"
    labels = labels or {}
    for k, v in when.items():
        if k.endswith("_any"):
            have = profile.get(k[:-4])
            have = have if isinstance(have, list) else [have]
            if not set(have) & set(v or []):
                return False, f"{_KEY_KO.get(k[:-4], k)} 조건({', '.join(labels.get(x, x) for x in v)})에 해당하지 않는다"
        elif k == "high_impact":
            hi, why = high_impact(profile)
            if bool(v) != hi:
                return False, ("고영향 AI 가 아니다. " if not hi else "고영향 AI 다. ") + why
        elif bool(profile.get(k)) != bool(v):
            return False, f"{_KEY_KO.get(k, k)} 조건에 해당하지 않는다"
    return True, "적용 조건: " + ", ".join(_when_text(when, labels))


_KEY_KO = {"activities": "하는 일", "data": "다루는 정보", "external_llm": "쓰는 모델", "retail": "일반투자자 상대",
           "automated_decision": "자동화된 결정", "high_impact": "고영향 AI"}


def _when_text(when: dict[str, Any], labels: dict[str, str]) -> list[str]:
    out = []
    for k, v in when.items():
        if k.endswith("_any"):
            out.append(f"{_KEY_KO.get(k[:-4], k)}이 " + " 또는 ".join(labels.get(x, x) for x in v))
        elif k == "high_impact":
            out.append("고영향 AI")
        else:
            out.append(_KEY_KO.get(k, k))
    return out


def option_labels(lib: dict[str, Any]) -> dict[str, str]:
    return {o["id"]: o["label"] for spec in (lib.get("profile") or {}).values() for o in spec.get("options") or []}


# ── 수준 도출 ──

def required_level(ob: dict[str, Any], mode: str) -> int:
    """조문 하나가 그 모드에서 자기 통제에 요구하는 수준(0 이면 그 모드에서 세지 않음)."""
    if not ob.get("runtime", True):
        return 0
    binding = ob.get("force") in BINDING
    if mode in ("binding_explicit", "binding_interpretive") and not binding:
        return 0
    if ob.get("layer") == "agent":
        return 2
    if ob.get("extends") == "interpretive" and mode in ("binding_interpretive", "guideline"):
        return 2
    return 1


def assess(lib: dict[str, Any], profile: dict[str, Any], levels: dict[str, int] | None = None,
           control_ids: tuple[str, ...] | None = None) -> dict[str, Any]:
    """프로필 → 적용 조문 · 미적용 조문(이유) · 모드별 통제 수준과 그 근거 조문 · (levels 를 주면) 충족 여부."""
    from .runtime.policy import CONTROL_ORDER
    cids = control_ids or CONTROL_ORDER
    labels = option_labels(lib)
    hi, hi_why = high_impact(profile)
    app, nap = [], []
    lv = {m: {c: 0 for c in cids} for m in MODES}
    basis: dict[str, dict[str, list[str]]] = {m: {c: [] for c in cids} for m in MODES}
    for ob in lib.get("obligations") or []:
        ok, why = applies(ob, profile, labels)
        row = {k: ob.get(k) for k in ("id", "doc", "article", "force", "quote", "quote_verified", "source", "requires",
                                      "control", "layer", "extends", "category", "note", "owner")}
        row.update(binding=ob.get("force") in BINDING, runtime=ob.get("runtime", True), force_ko=FORCE_KO.get(ob.get("force"), ""))
        if not ok:
            nap.append({**row, "reason": why})
            continue
        row["reason"] = why
        row["required"] = {m: required_level(ob, m) for m in MODES}
        for m in MODES:
            r, c = row["required"][m], ob.get("control")
            if r and c in lv[m]:
                if r > lv[m][c]:
                    lv[m][c], basis[m][c] = r, [ob["id"]]
                elif r == lv[m][c]:
                    basis[m][c].append(ob["id"])
        if levels is not None:
            row["status"] = _status(row, levels)
        app.append(row)
    order = {f: i for i, f in enumerate(("law", "decree", "supervisory_regulation", "exchange_rule", "guideline", "criteria"))}
    app.sort(key=lambda r: (not r["binding"], order.get(r["force"], 9), not r["runtime"], r["id"]))
    summary = {"applicable": len(app), "binding": sum(r["binding"] for r in app), "voluntary": sum(not r["binding"] for r in app),
               "offline": sum(not r["runtime"] for r in app), "not_applicable": len(nap)}
    if levels is not None:
        summary.update({s: sum(1 for r in app if r["status"] == s) for s in ("met", "partial", "unmet", "offline")})
        summary["unmet_binding"] = sum(1 for r in app if r["binding"] and r["status"] in ("unmet", "partial"))
    return {"sector": lib.get("sector"), "label": lib.get("label"), "reviewed_by_counsel": bool(lib.get("reviewed_by_counsel")),
            "profile": profile, "high_impact": {"value": hi, "reason": hi_why}, "applicable": app, "not_applicable": nap,
            "levels": lv, "basis": basis, "summary": summary}


def _status(row: dict[str, Any], levels: dict[str, int]) -> str:
    """met — 해석까지 충족 · partial — 사람 · 계정 층만(에이전트까지는 해석 영역) · unmet · offline(런타임 밖)."""
    if not row["runtime"]:
        return "offline"
    cur = int(levels.get(row["control"], 0))
    need = 2 if row["layer"] == "agent" else 1
    want = 2 if row.get("extends") == "interpretive" else need
    if cur >= want:
        return "met"
    if cur >= need:
        return "partial"
    return "unmet"


def preset_columns(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    """규제별 비교표에 넣을 '이 에이전트에 적용되는 조문' 열 — 관할 프리셋 대신."""
    return [{"id": "OB-" + m, "label": "적용 조문: " + MODE_KO[m], "levels": assessment["levels"][m]} for m in MODES]


def classify(assessment: dict[str, Any], controls: list[str]) -> dict[str, Any]:
    """결함 · 사람 승인에 기댐을 막는 통제들 → 그 통제를 요구하는 적용 조문과 분류(위반 소지 · 해석 · 가이드라인 · 공백)."""
    rel = [r for r in assessment["applicable"] if r["runtime"] and r["control"] in controls]
    if any(r["binding"] and r["layer"] == "agent" for r in rel):
        kind = "violation"
    elif any(r["binding"] and r.get("extends") == "interpretive" for r in rel):
        kind = "interpretive"
    elif any(not r["binding"] for r in rel):
        kind = "guideline"
    else:
        kind = "gap"
    return {"kind": kind, "obligations": [r["id"] for r in rel]}
