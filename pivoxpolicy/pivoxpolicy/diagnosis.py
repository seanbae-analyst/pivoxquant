"""AI 에이전트 내부통제 진단 보고서(diagnosis) — 에이전트 하나(등록부 · 적용성 프로필 · 공격 케이스)로 문서 한 벌을 만든다.

담는 것: 요약 · 통제 매트릭스(RCM) · 조문별 충족 · 시나리오 시험 결과와 조문 관계 · 구성상 저촉 · 우선 조치 · 책무별 미충족 ·
한계 · 증적. 내용은 섹션 목록(sections) 하나로 만들고 Markdown · HTML 로 그린다(두 형식의 내용이 어긋나지 않게).
CSV 는 RCM 과 조문 표 두 가지.

모든 시험은 샌드박스다 — 같은 정책 엔진으로 케이스를 돌리고, 에이전트 상태를 바꾸지 않는다. 실제 모델 행동은 LLM 레드팀(별도)이 본다.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import flow
from . import obligations as obl
from . import terms as T
from .runtime import cases as cases_mod
from .runtime import policy

LV_KO = T.LEVEL
STATUS_KO = T.STATUS
TYPE_KO = {"inventory": "예방", "vendors": "예방", "unique_id": "예방", "least_privilege": "예방", "human_approval": "예방",
           "audit_trail": "탐지", "kill_switch": "대응"}
VERIFIED_KO = {"primary": "법령 원문", "registry": "문서 코딩 원문 대조", "secondary": "2차 자료", "none": "인용 없음"}


class ReportError(ValueError):
    pass


def _controls() -> list[dict[str, Any]]:
    from . import sim
    from .registry import load_controls
    helps = sim.load_scenarios().get("control_help") or {}
    return [{"id": c.id, "num": c.num, "name": c.name_ko, "help": helps.get(c.id, {})} for c in load_controls()]


def _git_rev() -> str:
    """HEAD 짧은 해시. 코드 · 레지스트리에 커밋 안 된 수정이 있으면 '+dirty' 를 붙인다(그 해시로는 재현되지 않는다)."""
    here = Path(__file__).resolve().parent
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here, capture_output=True, text=True, timeout=3)
        rev = r.stdout.strip()
        if not rev:
            return "알 수 없음"
        d = subprocess.run(["git", "status", "--porcelain", "--", ".", "../registry"], cwd=here, capture_output=True, text=True, timeout=5)
        return rev + ("+dirty" if d.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return "알 수 없음"


def _josa(word: str, with_final: str, without: str) -> str:
    """받침 따라 조사 하나만(을/를, 이/가 …). 영문 · 숫자는 읽는 소리로(AI를, API를, 10을). 구현은 terms.josa 하나."""
    return T.josa(word, with_final, without)


def _ref(r: dict[str, Any]) -> str:
    return f"{r['doc']} {r['article']}"


def _short_ref(r: dict[str, Any]) -> str:
    d = r["doc"].replace("자본시장과 금융투자업에 관한 법률", "자본시장법").replace("신용정보의 이용 및 보호에 관한 법률", "신용정보법") \
        .replace("금융회사의 지배구조에 관한 법률", "지배구조법").replace("인공지능 발전과 신뢰 기반 조성 등에 관한 기본법 (AI 기본법)", "AI 기본법") \
        .replace("금융소비자 보호에 관한 법률", "금소법").replace("금융회사의 정보처리 업무 위탁에 관한 규정", "위탁규정")
    return f"{d} {r['article']}"


def _strength(r: dict[str, Any]) -> str:
    return T.strength(r)


def _strong(r: dict[str, Any]) -> int:
    """근거 조문 정렬: 강제 · (AI 명시 · 행위 규율) → 강제 · 그 밖 → 자율."""
    return 0 if r["binding"] and (r.get("layer") == "agent" or r.get("extends") == "direct") else 1 if r["binding"] else 2


# ── 진단(데이터) ──

def diagnose(agent: dict[str, Any], approved: list[dict[str, Any]], cases: list[dict[str, Any]] | None = None,
             lib: dict[str, Any] | None = None, audit: dict[str, Any] | None = None, now: datetime | None = None,
             company: str | None = None) -> dict[str, Any]:
    prof = agent.get("compliance")
    if not prof:
        raise ReportError("적용성 프로필(업권 · 하는 일 · 정보 · 모델)이 없어 보고서를 만들 수 없다")
    lib = lib or obl.load_library(prof.get("sector") or "securities")
    levels = {c: int((agent.get("levels") or {}).get(c, 0)) for c in policy.CONTROL_ORDER}
    A = obl.assess(lib, prof, levels)
    cs = cases or agent.get("cases") or cases_mod.load_cases()
    by_case = {c["id"]: c for c in cs}
    res = cases_mod.run_cases(agent, cs, approved, now)
    for r in res["results"]:
        r["fixes"], r["link"] = [], None
        if r["kind"] == "attack" and r["verdict"] in ("defect", "held"):
            r["fixes"] = cases_mod.minimal_fixes(agent, by_case[r["id"]], approved, now)
            r["link"] = {**obl.classify(A, r["fixes"]), "basis": "fix"} if r["fixes"] else None
        elif r["control"] and r["verdict"] == "good":
            r["link"] = {**obl.classify(A, [r["control"]]), "basis": "stop"}
    cols = [{"id": "current", "label": "지금 통제", "levels": levels}, *obl.preset_columns(A)]
    mx = cases_mod.run_matrix(agent, cols, cs, approved, now)
    ctls = _controls()
    by_ob = {r["id"]: r for r in A["applicable"]}
    return {"generated_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "company": company, "agent": agent, "profile": prof, "assessment": A, "attack": res, "matrix": mx,
            "controls": ctls, "rcm": _rcm(A, res, levels, ctls, by_ob), "actions": _actions(A, res, levels, ctls),
            "owners": _owners(A), "intake": agent.get("intake") or {}, "audit": audit, "lib": lib,
            "case_hash": hashlib.sha256(policy.canonical(cs).encode("utf-8")).hexdigest()[:16], "rev": _git_rev(), "case_defs": by_case,
            "case_source": "이 에이전트의 도구로 만든 케이스" if (cases or agent.get("cases")) else "데모 케이스 라이브러리"}


def _rcm(A, res, levels, ctls, by_ob) -> list[dict[str, Any]]:
    rows = []
    for c in ctls:
        cid = c["id"]
        rel = [r for r in A["applicable"] if r["runtime"] and r["control"] == cid]
        rel.sort(key=_strong)
        need = {m: A["levels"][m][cid] for m in obl.MODES}
        cur = levels[cid]
        touched = [r for r in res["results"] if r.get("control") == cid or cid in (r.get("fixes") or [])]
        vc = Counter(r["verdict"] for r in touched)
        if cur < need["binding_explicit"]:
            judge = "명문 기준 미달"
        elif cur < need["binding_interpretive"]:
            judge = "확장 해석 기준 미달"
        elif cur < need["guideline"]:
            judge = "자율규범 포함 기준 미달"
        else:
            judge = "적정(조문 기준)"
        if cid == "human_approval" and vc.get("held"):
            judge += f". 승인 의존 {vc['held']}건"
        owners = Counter(r.get("owner") for r in rel if r.get("owner"))
        rows.append({"id": f"PVX-{c['num']}", "control": cid, "name": c["name"], "type": TYPE_KO[cid],
                     "mode": {2: "자동", 1: "수동", 0: "없음"}[cur],
                     "description": (c["help"].get("agent") if max(need.values()) >= 2 else c["help"].get("analog")) or "",
                     "risks": [r["title"] for r in touched], "basis": [f"{_short_ref(r)} ({_strength(r)})" for r in rel[:3]],
                     "basis_more": max(0, len(rel) - 3), "need": need, "current": cur,
                     "owner": owners.most_common(1)[0][0] if owners else "미정",
                     "test": f"시나리오 {len(touched)}개(이 통제에서 멈췄거나 이 통제가 단일 보완 통제인 것)를 샌드박스에서 같은 정책 엔진으로 재실행",
                     "result": ", ".join(f"{T.SUMMARY[k] if k == 'friction' else T.ATTACK.get(k, T.SUMMARY.get(k, k))} {v}" for k, v in vc.items()) or "관련 시나리오 없음",
                     "judgment": judge})
    return rows


def _actions(A, res, levels, ctls) -> list[dict[str, Any]]:
    name = {c["id"]: c["name"] for c in ctls}
    out = []
    for r in A["applicable"]:
        if r.get("prohibits"):
            out.append({"rank": 0, "title": f"구성상 저촉 해소: {_short_ref(r)}", "why": r["requires"], "how": r.get("unless") or "",
                        "basis": [_ref(r)], "kind": "conflict"})
    fixed: dict[str, list[str]] = {}
    for r in res["results"]:
        for c in r.get("fixes") or []:
            fixed.setdefault(c, []).append(r["title"])
    cand = set(fixed) | {c for c in policy.CONTROL_ORDER if levels[c] < A["levels"]["binding_interpretive"][c]}
    rank = {"violation": 1, "interpretive": 2, "guideline": 3, "gap": 4}
    for c in cand:
        if levels[c] >= 2:
            continue
        link = obl.classify(A, [c])
        by_id = {x["id"]: x for x in A["applicable"]}
        rel = [by_id[i] for i in link["obligations"]][:3]          # classify 가 센 근거부터 정렬해 둔 순서 그대로
        n = len(fixed.get(c, []))
        out.append({"rank": rank[link["kind"]], "n": n, "title": f"{_josa(name[c], '을', '를')} AI까지로 올린다",
                    "why": (f"미차단 · 승인 의존 시나리오 {n}건이 자동 차단으로 바뀐다(같은 엔진으로 재실행해 확인)." if n
                            else "시험한 시나리오 가운데 이것 하나로 바뀌는 것은 없지만 조문이 요구한다.") + f" 관계: {T.LINK[link['kind']]}.",
                    "how": "", "basis": [f"{_ref(x)} ({_strength(x)})" for x in rel], "kind": link["kind"]})
    cats = Counter(r.get("category") for r in A["applicable"] if not r["runtime"] and not r.get("prohibits"))
    if cats:
        out.append({"rank": 5, "title": "런타임 외 의무를 증적으로 점검한다",
                    "why": ", ".join(f"{k} {v}개" for k, v in cats.most_common()), "how": "조문별 충족 표의 '런타임 외' 행마다 담당 책무와 증적을 정한다.",
                    "basis": [], "kind": "offline"})
    out.sort(key=lambda a: (a["rank"], -a.get("n", 0), a["title"]))
    return out


def _owners(A) -> list[dict[str, Any]]:
    g: dict[str, dict[str, list[str]]] = {}
    for r in A["applicable"]:
        st = r.get("status")
        if st in ("unmet", "partial", "conflict", "offline"):
            g.setdefault(r.get("owner") or "미정", {}).setdefault(st, []).append(_short_ref(r))
    return [{"owner": k, **{s: v.get(s, []) for s in ("conflict", "unmet", "partial", "offline")}}
            for k, v in sorted(g.items(), key=lambda kv: (-len(kv[1].get("conflict", [])) - len(kv[1].get("unmet", [])), kv[0]))]


# ── 섹션(형식과 무관한 내용) ──

def sections(D: dict[str, Any]) -> list[tuple]:
    a, A, res, prof = D["agent"], D["assessment"], D["attack"], D["profile"]
    S, s = [], A["summary"]
    lab = obl.option_labels(D["lib"])
    rs = res["summary"]
    cols = {p["preset"]: p for p in D["matrix"]["presets"]}
    S.append(("banner", "변호사 검토 전 초안이다. 조문 대응, 적용 조건, 해석 여지는 이 도구의 판단이며 법률 자문이 아니다. "
                        "공격 시험은 샌드박스 재실행이고 실제 모델의 행동은 따로(LLM 레드팀) 본다."))
    # 요약
    S.append(("h2", "1. 요약"))
    S.append(("kv", [("에이전트", f"{a['name']} ({a.get('id', '등록 전')})"), ("책임자", a.get("owner", "")), ("목적", a.get("purpose") or "—"),
                     ("하는 일", ", ".join(lab.get(x, x) for x in prof["activities"])), ("다루는 정보", ", ".join(lab.get(x, x) for x in prof["data"]) or "없음"),
                     ("쓰는 모델", lab.get(prof["external_llm"], prof["external_llm"])), ("일반투자자", "상대한다" if prof["retail"] else "아니다"),
                     ("AI 기본법 고영향", ("해당(추정 포함)" if A["high_impact"]["value"] else "해당 안 함(추정 포함)"))]))
    hl = [f"걸리는 조문 {s['applicable']}개(강제 {s['binding']}, 자율 {s['voluntary']}), 걸리지 않는 조문 {s['not_applicable']}개.",
          f"지금 통제 기준: 충족 {s['met']}, 사람·계정 층만 충족 {s['partial']}, 미충족 {s['unmet']}, 런타임 외 {s['offline'] - s['conflict']}, 구성상 저촉 {s['conflict']}.",
          f"시나리오 시험({D['case_source']} {len(res['results'])}개): 미차단 {rs['defect']}, 승인 의존 {rs['held']}, "
          f"자동 차단 {sum(1 for r in res['results'] if r['kind'] == 'attack' and r['verdict'] == 'good')}, 정상 업무 제약 {rs['friction']}, 공격면 없음 {rs['na']}."]
    def col(pid):
        p = cols.get(pid)
        return f"미차단 {p['summary']['defect']}, 승인 의존 {p['summary']['held']}" if p else "—"
    hl.append(f"걸리는 조문만큼 통제를 갖추면 명문 기준 {col('OB-binding_explicit')}, 확장 해석 기준 {col('OB-binding_interpretive')}, "
              f"자율규범 포함 기준 {col('OB-guideline')}. 지금 통제는 {col('current')}.")
    if s["conflict"]:
        hl.append(f"구성상 저촉 {s['conflict']}건은 통제를 켜도 풀리지 않는다. 우선 조치 맨 앞에 둔다.")
    S.append(("list", hl))
    S.append(("p", "AI 기본법 고영향 판단: " + A["high_impact"]["reason"]))
    # 우선 조치
    S.append(("h2", "2. 우선 조치"))
    rows = []
    for i, x in enumerate(D["actions"], 1):
        rows.append([str(i), x["title"], (x["why"] + (" 해소: " + x["how"] if x["how"] else "")).strip(), "; ".join(x["basis"]) or "—"])
    S.append(("table", ["순서", "조치", "이유", "근거 조문"], rows or [["—", "조치할 것이 없다", "", ""]]))
    # RCM
    S.append(("h2", "3. 통제 매트릭스 (RCM)"))
    S.append(("p", "통제마다 대응 위험(이 통제에서 멈췄거나 이 통제가 단일 보완 통제인 시나리오), 유형, 수행 방식, 근거 조문, 요구 수준(명문 기준 / "
                   "확장 해석 기준 / 자율규범 포함 기준)과 지금 수준, 책무, 시험 결과, 판정을 적는다. 수행 방식에서 자동은 런타임이 호출마다 집행한다는 뜻이고, "
                   "수동은 사람 절차라 런타임 밖이라는 뜻이다. 근거 조문은 센 것부터 세 개."))
    rows = []
    for r in D["rcm"]:
        rows.append([r["id"], r["name"], r["type"], r["mode"], "; ".join(r["risks"][:4]) + (f" 외 {len(r['risks']) - 4}" if len(r["risks"]) > 4 else "") or "—",
                     "; ".join(r["basis"]) + (f" 외 {r['basis_more']}" if r["basis_more"] else "") or "걸리는 조문 없음",
                     " / ".join(LV_KO[r["need"][m]] for m in obl.MODES), LV_KO[r["current"]], r["owner"], r["result"], r["judgment"]])
    S.append(("table", ["ID", "통제", "유형", "수행", "대응 위험", "근거 조문", "요구(명문 / 확장 해석 / 자율규범)", "지금", "책무", "시험 결과", "판정"], rows, "rcm"))
    # 구성상 저촉
    cf = [r for r in A["applicable"] if r.get("prohibits")]
    if cf:
        S.append(("h2", "4. 구성상 저촉"))
        S.append(("table", ["조문", "요구", "해소 방법"], [[_ref(r), r["requires"], r.get("unless") or ""] for r in cf]))
    # 공격 시험
    S.append(("h2", "5. 시나리오 시험 결과"))
    S.append(("p", f"{D['case_source']}를 지금 통제로 샌드박스에서 돌렸다. 사람 승인 단계에서 멈춘 공격은 승인자가 승인한다고 가정하고(왜곡된 요약, 승인 피로) "
                   "한 번 더 돌려, 뒤의 통제가 막으면 자동 차단, 실행되면 승인 의존으로 분류한다. 단일 보완 통제는 통제 하나를 AI 수준으로 올려 다시 돌려 "
                   "자동 차단으로 바뀌는 것만 적는다."))
    rows = []
    name = {c["id"]: c["name"] for c in D["controls"]}
    for r in res["results"]:
        vk = T.verdict_label(r["kind"], r["verdict"], r.get("control"))
        stop = f"{name[r['control']]} · {r['stopped_at']}단계" if r.get("control") else "—"
        link = r.get("link")
        lk = "" if not link else (T.STOP if link.get("basis") == "stop" else T.LINK)[link["kind"]]
        rows.append([r["title"], "공격" if r["kind"] == "attack" else "정상 업무", vk, stop, ", ".join(name[c] for c in r.get("fixes") or []) or "—", lk or "—"])
    S.append(("table", ["시나리오", "종류", "판정", "멈춘 곳", "단일 보완 통제", "조문과의 관계"], rows))
    open_ = [r for r in res["results"] if r["kind"] == "attack" and r["verdict"] in ("defect", "held")]
    if open_ and D.get("case_defs"):
        S.append(("p", f"아래는 미차단 · 승인 의존인 공격 {len(open_)}개의 명령 흐름이다. 명령이 런타임의 관문 일곱 개를 지나는 길이고, "
                       "빈 관문(○)은 그 통제가 AI 수준이 아니어서 런타임이 보지 않은 곳이다."))
        S.append(("flows", [(D["case_defs"][r["id"]], r) for r in open_ if r["id"] in D["case_defs"]]))
    # 조문별 충족
    S.append(("h2", "6. 조문별 충족"))
    rows = [[_ref(r), r["force_ko"], _strength(r), r["requires"], (name.get(r["control"], "") if r["runtime"] else (r.get("category") or "")),
             STATUS_KO.get(r.get("status"), ""), r.get("owner") or "", VERIFIED_KO.get(r.get("quote_verified"), "")] for r in A["applicable"]]
    S.append(("table", ["조문", "강제력", "강제력 · 미치는 방식", "요구", "통제 · 분류", "지금 상태", "책무", "인용"], rows))
    S.append(("details", f"걸리지 않는 조문 {len(A['not_applicable'])}개와 이유", [f"{_ref(r)}: {r['reason']}" for r in A["not_applicable"]]))
    # 책무별
    S.append(("h2", "7. 책무별 미충족"))
    S.append(("p", "지배구조법 제30조의2에 따라 책무 임원이 점검할 목록이다. 책무명은 시행령 별표 1을 따른 흔한 배정이며, 실제 배정은 회사의 책무구조도를 따른다."))
    rows = [[o["owner"], "; ".join(o["conflict"]) or "—", "; ".join(o["unmet"]) or "—", "; ".join(o["partial"]) or "—", str(len(o["offline"]))] for o in D["owners"]]
    S.append(("table", ["책무", "구성상 저촉", "미충족", "사람·계정 층만 충족", "런타임 외(증적 점검, 개수)"], rows or [["—", "", "", "", ""]]))
    # 명세 가져오기
    it = D["intake"]
    if it.get("tools"):
        S.append(("h2", "8. 도구 종류 추정"))
        S.append(("p", "명세의 도구 정의에서 추정한 값이다. 확신도가 낮은 도구는 회사가 확인해야 한다."))
        S.append(("table", ["도구", "형식", "종류", "근거", "확신도", "금액 인자", "고객 인자"],
                  [[t["name"], t.get("format", ""), t["kind"], t.get("why", ""), {"high": "높음", "medium": "보통", "low": "낮음"}.get(t.get("confidence"), ""),
                    t.get("amount_arg") or "—", t.get("customer_arg") or "—"] for t in it["tools"]]))
        if it.get("warnings") or it.get("skipped"):
            S.append(("list", [*it.get("warnings", []), *it.get("skipped", [])]))
    # 한계
    S.append(("h2", "9. 한계"))
    vq = Counter(r.get("quote_verified") for r in D["lib"].get("obligations") or [])
    S.append(("list", [
        "변호사 검토 전이다. 조문 대응, 적용 조건, 조문이 에이전트에 미치는 방식(AI 명시, 행위 규율, 주체 확장 해석)의 구분은 이 도구의 초안이다.",
        f"의무 라이브러리 기준일 {D['lib'].get('as_of')}, 조문 {len(D['lib'].get('obligations') or [])}개(인용 확인: " +
        ", ".join(f"{VERIFIED_KO.get(k, k)} {v}" for k, v in vq.most_common()) + "). 개정은 자동으로 감지하지 못한다.",
        "시나리오 시험은 정책 엔진 샌드박스 재실행이다. 실제 모델이 숨은 지시를 따르는지는 LLM 레드팀으로 따로 본다.",
        "입력 출처(외부 글인지)는 에이전트가 스스로 신고한다. 키를 가진 공격자는 출처를 위조할 수 있다(게이트웨이 · 프록시로 풀 과제).",
        "지금 통제 수준은 회사의 자가 진단 값이다. 운영 효과성(실제로 그렇게 돌고 있는지)은 감사 기록으로 따로 확인한다.",
        "도구 종류와 프로필은 명세에서 추정한 값이 섞여 있다(8절)."]))
    # 증적
    S.append(("h2", "10. 증적"))
    au = D.get("audit")
    S.append(("kv", [("만든 시각", D["generated_at"]), ("도구 버전", D["rev"]), ("케이스 집합 지문", D["case_hash"]),
                     ("감사 기록 사슬", (f"{'이어져 있다' if au.get('ok') else '끊겼다'}, {au.get('checked')}줄" + (f", 머리 {str(au.get('head'))[:16]}" if au.get("head") else "")) if au else "런타임 밖에서 만든 보고서(해당 없음)"),
                     ("명세 가져온 시각", it.get("imported_at") or "—")]))
    return S


# ── 그리기 ──

def to_markdown(D: dict[str, Any]) -> str:
    a = D["agent"]
    out = [f"# AI 에이전트 내부통제 진단 보고서: {a['name']}", "",
           f"{D.get('company') + ' · ' if D.get('company') else ''}{D['assessment']['label']} · {D['generated_at']}", ""]
    for blk in sections(D):
        k = blk[0]
        if k == "banner":
            out += [f"> **{blk[1]}**", ""]
        elif k == "h2":
            out += [f"## {blk[1]}", ""]
        elif k == "p":
            out += [blk[1], ""]
        elif k == "list":
            out += [f"- {x}" for x in blk[1]] + [""]
        elif k == "kv":
            out += [f"- **{x}**: {y}" for x, y in blk[1]] + [""]
        elif k == "table":
            esc = lambda v: str(v).replace("|", "\\|").replace("\n", " ")  # noqa: E731
            out += ["| " + " | ".join(blk[1]) + " |", "|" + "---|" * len(blk[1])]
            out += ["| " + " | ".join(esc(c) for c in row) + " |" for row in blk[2]] + [""]
        elif k == "details":
            out += [f"<details><summary>{html.escape(blk[1])}</summary>", ""] + [f"- {x}" for x in blk[2]] + ["", "</details>", ""]
        elif k == "flows":                         # 마크다운에는 단계별 결정만 줄글로
            for c, r in blk[1]:
                out.append(f"- **{r['title']}**: " + " → ".join(
                    f"{s['tool']} {flow.DECISION.get(s['decision'], s['decision'])}" + (f"({flow.gate_name(s['control'])})" if s.get("control") else "")
                    for s in flow._last_per_step(r["steps"])))
            out.append("")
    return "\n".join(out)


CSS = """
:root{--ink:#111;--soft:#444;--dim:#6b6b6b;--line:#d9d4cc;--bronze:#8a6a3f;--wash:#f6f1e8}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:14px/1.65 'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif}
main{max-width:1200px;margin:0 auto;padding:48px 40px 72px}
table.rcm td:nth-child(-n+4),table.rcm td:nth-child(8){white-space:nowrap}
table.rcm td:nth-child(7){white-space:nowrap}
.kicker{margin:0;font-size:12.5px;color:var(--bronze);font-weight:600}
h1{margin:6px 0 4px;font-size:26px;line-height:1.3}
.meta{margin:0 0 20px;color:var(--dim);font-size:13px}
.banner{margin:0 0 24px;padding:10px 14px;border-left:3px solid var(--bronze);background:var(--wash);font-size:13px;font-weight:600}
h2{margin:36px 0 10px;padding-top:14px;border-top:1px solid var(--line);font-size:18px}
p{margin:8px 0;max-width:80ch;color:var(--soft)}
ul{margin:8px 0;padding-left:20px;color:var(--soft)}
li{margin:3px 0}
dl{display:grid;grid-template-columns:150px minmax(0,1fr);gap:4px 14px;margin:8px 0}
dt{color:var(--dim)}dd{margin:0;font-weight:600}
.tw{overflow-x:auto;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-weight:600;color:var(--dim);border-bottom:1.5px solid var(--ink);white-space:nowrap}
td:first-child{font-weight:600}
details{margin:8px 0;font-size:13px;color:var(--soft)}
summary{cursor:pointer;color:var(--ink)}
footer{margin-top:40px;color:var(--dim);font-size:12px}
@media print{main{padding:0;max-width:none}h2{break-after:avoid}tr{break-inside:avoid}.tw{overflow:visible}}
"""


def to_html(D: dict[str, Any]) -> str:
    e = html.escape
    a = D["agent"]
    body = [f'<p class="kicker">AI 에이전트 내부통제 진단 보고서</p><h1>{e(a["name"])}</h1>',
            f'<p class="meta">{e((D.get("company") + " · ") if D.get("company") else "")}{e(D["assessment"]["label"])} · {e(D["generated_at"])}</p>']
    for blk in sections(D):
        k = blk[0]
        if k == "banner":
            body.append(f'<p class="banner" role="note">{e(blk[1])}</p>')
        elif k == "h2":
            body.append(f"<h2>{e(blk[1])}</h2>")
        elif k == "p":
            body.append(f"<p>{e(blk[1])}</p>")
        elif k == "list":
            body.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in blk[1]) + "</ul>")
        elif k == "kv":
            body.append("<dl>" + "".join(f"<dt>{e(x)}</dt><dd>{e(str(y))}</dd>" for x, y in blk[1]) + "</dl>")
        elif k == "table":
            cls = f' class="{e(blk[3])}"' if len(blk) > 3 else ""
            th = "".join(f"<th>{e(h)}</th>" for h in blk[1])
            tr = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in row) + "</tr>" for row in blk[2])
            body.append(f'<div class="tw"><table{cls}><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>')
        elif k == "details":
            body.append(f"<details><summary>{e(blk[1])}</summary><ul>" + "".join(f"<li>{e(x)}</li>" for x in blk[2]) + "</ul></details>")
        elif k == "flows":
            lv = D["agent"].get("levels") or {}
            on = [c["name"] for c in D["controls"] if int(lv.get(c["id"], 0)) >= 2]
            items = [(*((r["title"].split(": ", 1)) if ": " in r["title"] else (r["title"], "")), [r]) for c, r in blk[1]]
            steps = "".join(f"<li><b>{e(r['title'])}</b><ul>" + "".join(f"<li>{e(x)}</li>" for x in flow.steps_text(r, c)) + "</ul></li>"
                            for c, r in blk[1])
            body.append(f'<p>지금 AI 수준인 통제: {e(", ".join(on) if on else "없음")}</p>' + flow.legend() + flow.gate_list(always=True)
                        + flow.rows(["지금 통제"], items)
                        + f'<details class="mt-det"><summary>단계별 판정 보기</summary><ul>{steps}</ul></details>')
    body.append('<footer>PivoxPolicy 진단 보고서. 법률 자문이 아니다. 조문 인용은 국가법령정보센터 현행 원문 등에서 대조했고 출처는 조문별 충족 표의 인용 열을 본다.</footer>')
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>진단 보고서: {e(a["name"])}</title><meta name="robots" content="noindex">'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">'
            f"<style>{CSS}{flow.CSS}{flow.CSS_LIGHT}</style></head><body><main>" + "".join(body) + "</main></body></html>")


def _csv(header: list[str], rows: list[list[Any]]) -> str:
    """엑셀에서 바로 열리게(BOM · CRLF), 수식으로 읽히는 칸(= + - @ 로 시작)은 막는다."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(header)
    for r in rows:
        w.writerow([("'" + s) if (s := str(v)) and s[0] in "=+-@\t\r" else s for v in r])
    return "\ufeff" + buf.getvalue()


def rcm_csv(D: dict[str, Any]) -> str:
    return _csv(["통제 ID", "통제", "유형", "수행 방식(자동=런타임 집행, 수동=사람 절차)", "통제 내용", "대응 위험", "근거 조문", "요구(명문 기준)", "요구(확장 해석 기준)",
                 "요구(자율규범 포함 기준)", "지금 수준", "책무", "시험 방법", "시험 결과", "판정"],
                [[r["id"], r["name"], r["type"], r["mode"], r["description"], "; ".join(r["risks"]), "; ".join(r["basis"]),
                  LV_KO[r["need"]["binding_explicit"]], LV_KO[r["need"]["binding_interpretive"]], LV_KO[r["need"]["guideline"]],
                  LV_KO[r["current"]], r["owner"], r["test"], r["result"], r["judgment"]] for r in D["rcm"]])


def obligations_csv(D: dict[str, Any]) -> str:
    A = D["assessment"]
    name = {c["id"]: c["name"] for c in D["controls"]}
    return _csv(["조문", "강제력", "강제력 · 미치는 방식", "요구", "통제", "분류", "지금 상태", "책무", "적용 이유", "인용", "인용 확인", "출처", "시행·개정"],
                [[_ref(r), r["force_ko"], _strength(r), r["requires"], name.get(r["control"], "") if r["runtime"] else "", r.get("category") or "",
                  STATUS_KO.get(r.get("status"), ""), r.get("owner") or "", r.get("reason") or "", r.get("quote") or "",
                  VERIFIED_KO.get(r.get("quote_verified"), ""), r.get("source") or "", r.get("effective") or ""] for r in A["applicable"]])
