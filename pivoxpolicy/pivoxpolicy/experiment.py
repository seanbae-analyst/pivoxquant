"""실험 — 합성 에이전트 유형 × 규제 기준. 논문 표와 그림을 만든다.

설계
  에이전트 유형: registry/experiment_agents.yaml(증권사의 대표적인 에이전트 자리 일곱 곳, 하는 일 · 정보 · 배포 형태를 고정)
  규제 기준: 통제 없음(기준선) · 명문 기준 · 확장 해석 기준 · 자율규범 포함 기준 · 모든 통제 AI 수준(기준선).
             가운데 셋은 그 유형에 걸리는 조문(obligations)에서 도출한 통제 수준이다.
  시나리오: 각 유형의 실제 도구로 만든 공격 · 정상 업무 시나리오(intake.generate_cases). 같은 정책 엔진 샌드박스로 돈다.
지표
  공격: 자동 차단 · 승인 의존 · 미차단 · 공격면 없음 / 정상 업무: 정상 처리 · 승인 대기 · 과잉 차단
  해석 의존: 명문 기준과 확장 해석 기준 사이에서 판정이 바뀌는 공격 시나리오
  승인자 오판 민감도: 승인 의존 시나리오를 승인자가 확률 p 로 잘못 승인할 때의 기대 미차단 = 미차단 + p × 승인 의존
  공격 유형별: 같은 공격 유형(terms.SCENARIO)끼리 묶은 판정 — 어떤 공격이 해석에 달려 있는지
  적용성: 걸리는 조문 · 강제 조문 · AI 명시 또는 행위 규율 강제 조문 · 구성상 저촉 · 명문 기준이 AI 수준까지 요구하는 통제 수
재현: 결과는 결정적이다(난수 없음). manifest 에 의무 라이브러리 기준일 · 조문 수 · 에이전트 정의 지문 · 시나리오 지문 · 도구 버전을 남긴다.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import intake, terms
from . import obligations as obl
from .registry import OUT_DIR, REGISTRY_DIR
from .runtime import cases as cases_mod
from .runtime import policy

AGENTS_PATH = REGISTRY_DIR / "experiment_agents.yaml"
READINGS = ("none", "binding_explicit", "binding_interpretive", "guideline", "all")
READING_KO = {"none": "통제 없음", **terms.MODE, "all": "모든 통제 AI 수준"}
ATTACK_KEYS = ("good", "held", "defect", "na")
BENIGN_KEYS = ("good", "approval", "overblock")
P_GRID = (0.0, 0.05, 0.1, 0.3)
SCENARIO_ORDER = ("prompt_injection", "approval_exploitation", "insider_misuse", "rogue_agent", "multi_agent_cascade",
                  "supply_chain", "ai_credentials", "cross_customer_leak")
ACT_SHORT = {"order": "주문", "transfer": "이체 · 정산", "advice": "투자 권유", "customer_service": "고객 응대",
             "credit": "신용공여", "internal": "내부 업무", "code": "코드 실행"}
LLM_SHORT = {"onprem": "사내 설치", "domestic_cloud": "국내 클라우드", "foreign_api": "해외 API"}


def load_agents(path: Path = AGENTS_PATH) -> list[dict[str, Any]]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("agents") or []


def _hash(obj: Any) -> str:
    return hashlib.sha256(policy.canonical(obj).encode("utf-8")).hexdigest()[:16]


def _git_rev() -> str:
    from .diagnosis import _git_rev as g
    return g()


def run(path: Path = AGENTS_PATH, readings: tuple[str, ...] = READINGS, p_grid: tuple[float, ...] = P_GRID) -> dict[str, Any]:
    lib = obl.load_library()
    specs = load_agents(path)
    agents = []
    for a in specs:
        b = intake.build(a["spec"])
        A = obl.assess(lib, b["compliance"])
        base = {"id": f"agt_exp{a['id'].lower()}", "status": "active", "expires_at": None, **b["agent"]}
        lv = {"none": {c: 0 for c in policy.CONTROL_ORDER}, "all": {c: 2 for c in policy.CONTROL_ORDER}, **A["levels"]}
        per: dict[str, Any] = {}
        verdicts: dict[str, dict[str, str]] = {}
        scn = {c["id"]: c["scenario"] for c in b["cases"]}
        for rd in readings:
            res = cases_mod.run_cases({**base, "levels": lv[rd]}, b["cases"], b["components"])
            att = [r for r in res["results"] if r["kind"] == "attack"]
            ben = [r for r in res["results"] if r["kind"] == "benign"]
            m = {k: sum(1 for r in att if r["verdict"] == k) for k in ATTACK_KEYS}
            m.update({f"benign_{k}": 0 for k in BENIGN_KEYS})
            for r in ben:
                key = "good" if r["verdict"] == "good" else (terms.benign_key(r["control"]) if r["verdict"] == "friction" else None)
                if key:
                    m[f"benign_{key}"] += 1
            m["ai_controls"] = sum(1 for v in lv[rd].values() if v == 2)
            m["attacks"] = len(att)
            m["exposure"] = {str(p): round(m["defect"] + p * m["held"], 3) for p in p_grid}
            per[rd] = m
            verdicts[rd] = {r["id"]: r["verdict"] for r in att}
        dep = sorted(cid for cid in verdicts.get("binding_explicit", {})
                     if verdicts["binding_explicit"][cid] != verdicts.get("binding_interpretive", {}).get(cid))
        app = A["applicable"]
        agents.append({
            "id": a["id"], "label": a["label"], "profile": b["compliance"], "high_impact": A["high_impact"]["value"],
            "applicable": len(app), "binding": sum(r["binding"] for r in app),
            "binding_ai": sum(1 for r in app if r["binding"] and (r.get("layer") == "agent" or r.get("extends") == "direct")),
            "conflict": sum(1 for r in app if r.get("prohibits")), "offline": sum(1 for r in app if not r["runtime"]),
            "conflicts": [f"{r['doc']} {r['article']}" for r in app if r.get("prohibits")],
            "explicit_ai_controls": [c for c, v in A["levels"]["binding_explicit"].items() if v == 2],
            "explicit_basis": {c: A["basis"]["binding_explicit"][c] for c, v in A["levels"]["binding_explicit"].items() if v == 2},
            "levels": {rd: lv[rd] for rd in readings}, "readings": per, "interpretation_dependent": dep,
            "attack_cases": [{"id": cid, "scenario": scn.get(cid), "verdicts": {rd: verdicts[rd][cid] for rd in readings}}
                             for cid in sorted(verdicts[readings[0]])],
            "cases": len(b["cases"]), "case_hash": _hash(b["cases"]), "tools": len(b["tools"])})
    agg = {rd: {k: sum(x["readings"][rd][k] for x in agents) for k in (*ATTACK_KEYS, *(f"benign_{k}" for k in BENIGN_KEYS), "attacks")}
           for rd in readings}
    for rd in readings:
        agg[rd]["exposure"] = {str(p): round(agg[rd]["defect"] + p * agg[rd]["held"], 3) for p in p_grid}
    return {"agents": agents, "aggregate": agg, "readings": list(readings), "p_grid": list(p_grid),
            "manifest": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "tool_rev": _git_rev(),
                         "library_as_of": str(lib.get("as_of")), "obligations": len(lib.get("obligations") or []),
                         "reviewed_by_counsel": bool(lib.get("reviewed_by_counsel")), "agents_hash": _hash(specs),
                         "case_hashes": {x["id"]: x["case_hash"] for x in agents}}}


# ── 요약 문장(숫자에서 만든다) ──

def findings(R: dict[str, Any]) -> list[str]:
    ag, A = R["aggregate"], R["agents"]
    n = ag["binding_explicit"]["attacks"]
    pct = lambda a, b: f"{(100 * a / b):.0f}%" if b else "—"  # noqa: E731
    e, i, g = ag["binding_explicit"], ag["binding_interpretive"], ag["guideline"]
    none_ai = [x["label"] for x in A if not x["explicit_ai_controls"]]
    some_ai = [f"{x['label']}({', '.join(terms_name(c) for c in x['explicit_ai_controls'])})" for x in A if x["explicit_ai_controls"]]
    dep = sum(len(x["interpretation_dependent"]) for x in A)
    out = [
        f"에이전트 유형 {len(A)}개, 공격 시나리오 {n}개. 명문 기준만 따르면 미차단 {e['defect']}개({pct(e['defect'], n)}), 승인 의존 {e['held']}개({pct(e['held'], n)}), "
        f"자동 차단 {e['good']}개({pct(e['good'], n)})다.",
        f"확장 해석 기준에서는 미차단 {i['defect']}개, 승인 의존 {i['held']}개, 자율규범 포함 기준에서는 미차단 {g['defect']}개, 승인 의존 {g['held']}개다.",
        f"명문 기준이 어떤 통제도 AI 수준까지 요구하지 않는 유형이 {len(none_ai)}개다({', '.join(none_ai)}). "
        f"AI 수준 요구가 생기는 유형은 {', '.join(some_ai) or '없음'}이다.",
        f"판정이 명문 기준과 확장 해석 기준 사이에서 바뀌는 공격 시나리오(해석 의존)는 {dep}개({pct(dep, n)})다. "
        "사람·계정을 대상으로 쓴 조문을 에이전트에도 적용하느냐가 결과를 가른다.",
    ]
    p = R["p_grid"]
    if len(p) > 1:
        hi = str(p[-1])
        out.append(f"승인자가 승인 의존 시나리오의 {int(float(hi) * 100)}%를 잘못 승인한다고 가정하면 명문 기준의 기대 미차단은 {e['exposure'][hi]}개다.")
    sc = by_scenario(R)
    fully = [terms.SCENARIO.get(k, k) for k, v in sc.items() if v["n"] and v["dep"] == v["n"]]
    if fully:
        from .diagnosis import _josa
        out.append(f"공격 유형 가운데 {_josa(', '.join(fully), '은', '는')} 모든 시나리오의 판정이 명문 기준과 확장 해석 기준 사이에서 바뀐다.")
    cf = [x["label"] for x in A if x["conflict"]]
    if cf:
        out.append(f"구성상 저촉은 외부 클라우드 · 해외 API 모델을 쓰는 유형 {len(cf)}개({', '.join(cf)})에서 나타난다. 통제 수준과 상관없이 구성을 바꾸거나 예외 사유가 있어야 한다.")
    return out


# ── 그림(인라인 SVG, 스크립트 없음) ──

COL = {"good": "var(--pq-bronze)", "held": "var(--pq-bronze-deep)", "defect": "var(--pq-ivory)", "na": "var(--pq-ivory-line)"}
LBL = {"good": "자동 차단", "held": "승인 의존", "defect": "미차단", "na": "공격면 없음"}


def _bar(x: float, y: float, w: float, h: float, parts: list[tuple[str, int]], total: int) -> str:
    out, cx = [], x
    for k, v in parts:
        if not v or not total:
            continue
        ww = w * v / total
        out.append(f'<rect x="{cx:.1f}" y="{y:.1f}" width="{ww:.1f}" height="{h:.1f}" fill="{COL[k]}"><title>{LBL[k]} {v}</title></rect>')
        cx += ww
    return "".join(out)


def figure_aggregate(R: dict[str, Any]) -> str:
    """그림: 규제 기준별 공격 시나리오 판정(전체 유형 합)."""
    rows, W, L, H, G = R["readings"], 760, 170, 26, 14
    total = R["aggregate"][rows[0]]["attacks"]
    svg = [f'<svg viewBox="0 0 {W} {len(rows) * (H + G) + 28}" role="img" aria-label="규제 기준별 공격 시나리오 판정" class="xfig">']
    for i, rd in enumerate(rows):
        y = i * (H + G)
        a = R["aggregate"][rd]
        svg.append(f'<text x="0" y="{y + H * 0.68:.1f}" class="t">{html.escape(READING_KO[rd])}</text>')
        svg.append(_bar(L, y, W - L - 70, H, [(k, a[k]) for k in ATTACK_KEYS], total))
        svg.append(f'<text x="{W - 62}" y="{y + H * 0.68:.1f}" class="n">미차단 {a["defect"]}</text>')
    svg.append(f'<text x="{L}" y="{len(rows) * (H + G) + 16}" class="s">공격 시나리오 {total}개(유형 {len(R["agents"])}개 합)</text></svg>')
    return "".join(svg)


def figure_agents(R: dict[str, Any]) -> str:
    """그림: 유형별 × 기준별 작은 막대(명문 · 확장 해석 · 자율규범 포함)."""
    rds = [r for r in ("binding_explicit", "binding_interpretive", "guideline") if r in R["readings"]]
    W, L, H, G, colw = 760, 170, 18, 12, (760 - 170) / len(rds)
    out = [f'<svg viewBox="0 0 {W} {len(R["agents"]) * (H + G) + 30}" role="img" aria-label="에이전트 유형별 판정" class="xfig">']
    for j, rd in enumerate(rds):
        out.append(f'<text x="{L + j * colw:.1f}" y="12" class="h">{html.escape(READING_KO[rd])}</text>')
    for i, x in enumerate(R["agents"]):
        y = 22 + i * (H + G)
        out.append(f'<text x="0" y="{y + H * 0.75:.1f}" class="t">{html.escape(x["id"] + " " + x["label"])}</text>')
        for j, rd in enumerate(rds):
            m = x["readings"][rd]
            out.append(_bar(L + j * colw, y, colw - 16, H, [(k, m[k]) for k in ATTACK_KEYS], m["attacks"]))
    out.append("</svg>")
    return "".join(out)


def legend() -> str:
    return '<p class="key">' + "".join(f'<span><i style="background:{COL[k]}"></i>{LBL[k]}</span>' for k in ATTACK_KEYS) + "</p>"


# ── 표 ──

def by_scenario(R: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """공격 유형별 합: n(시나리오 수), 기준마다 판정 수, dep(해석 의존 수)."""
    out: dict[str, dict[str, Any]] = {}
    for x in R["agents"]:
        dep = set(x["interpretation_dependent"])
        for c in x["attack_cases"]:
            k = c["scenario"] or "?"
            d = out.setdefault(k, {"n": 0, "dep": 0, **{rd: {v: 0 for v in ATTACK_KEYS} for rd in R["readings"]}})
            d["n"] += 1
            d["dep"] += c["id"] in dep
            for rd, v in c["verdicts"].items():
                d[rd][v] += 1
    order = {k: i for i, k in enumerate(SCENARIO_ORDER)}
    return dict(sorted(out.items(), key=lambda kv: order.get(kv[0], 99)))


def tables(R: dict[str, Any]) -> list[tuple[str, list[str], list[list[str]]]]:
    A, rds = R["agents"], R["readings"]
    mid = [r for r in ("binding_explicit", "binding_interpretive", "guideline") if r in rds]
    t1 = ("표 1. 에이전트 유형별 적용 조문. 강제는 걸리는 조문 가운데 강제 조문, AI 수준 강제는 그 가운데 AI를 명시하거나 행위 자체를 규율하는 조문이다.",
          ["유형", "하는 일", "모델", "걸리는 조문", "강제", "AI 수준 강제", "구성상 저촉", "명문 기준의 AI 수준 통제", "고영향 AI"],
          [[f"{x['id']} {x['label']}", ", ".join(ACT_SHORT.get(a, a) for a in x["profile"]["activities"]),
            LLM_SHORT.get(x["profile"]["external_llm"], x["profile"]["external_llm"] or ""),
            str(x["applicable"]), str(x["binding"]), str(x["binding_ai"]), str(x["conflict"]),
            ", ".join(terms_name(c) for c in x["explicit_ai_controls"]) or "없음", "추정 해당" if x["high_impact"] else "아님"] for x in A])
    t2 = ("표 2. 유형별 미차단 / 승인 의존. 칸은 '미차단 수 / 승인 의존 수'이다.", ["유형"] + [READING_KO[rd] for rd in rds] + ["해석 의존"],
          [[f"{x['id']} {x['label']}"] + [f"{x['readings'][rd]['defect']} / {x['readings'][rd]['held']}" for rd in rds]
           + [str(len(x["interpretation_dependent"]))] for x in A])
    sc = by_scenario(R)
    t3 = ("표 3. 공격 유형별 판정(유형 합). 칸은 '미차단 수 / 승인 의존 수'이다.", ["공격 유형", "시나리오"] + [READING_KO[rd] for rd in mid] + ["해석 의존"],
          [[terms.SCENARIO.get(k, k), str(v["n"])] + [f"{v[rd]['defect']} / {v[rd]['held']}" for rd in mid] + [str(v["dep"])] for k, v in sc.items()])
    t4 = ("표 4. 규제 기준별 시나리오 판정(유형 합)", ["기준", "자동 차단", "승인 의존", "미차단", "공격면 없음", "정상 처리", "승인 대기", "과잉 차단"],
          [[READING_KO[rd]] + [str(R["aggregate"][rd][k]) for k in ATTACK_KEYS] + [str(R["aggregate"][rd][f"benign_{k}"]) for k in BENIGN_KEYS] for rd in rds])
    t5 = ("표 5. 승인자 오판 민감도. 기대 미차단 = 미차단 + p × 승인 의존(유형 합)", ["기준"] + [f"p = {p}" for p in R["p_grid"]],
          [[READING_KO[rd]] + [str(R["aggregate"][rd]["exposure"][str(p)]) for p in R["p_grid"]] for rd in rds])
    return [t1, t2, t3, t4, t5]


def _dep_names(x: dict[str, Any]) -> list[str]:
    """해석 의존 시나리오를 공격 유형 이름으로(같은 유형은 개수로 묶는다)."""
    scn = {c["id"]: c["scenario"] for c in x["attack_cases"]}
    cnt: dict[str, int] = {}
    for cid in x["interpretation_dependent"]:
        k = scn.get(cid) or "?"
        cnt[k] = cnt.get(k, 0) + 1
    order = {k: i for i, k in enumerate(SCENARIO_ORDER)}
    return [terms.SCENARIO.get(k, k) + (f" {n}" if n > 1 else "") for k, n in sorted(cnt.items(), key=lambda kv: order.get(kv[0], 99))]


@functools.lru_cache(maxsize=1)
def _ctl_names() -> dict[str, str]:
    from .diagnosis import _controls
    return {c["id"]: c["name"] for c in _controls()}


def terms_name(cid: str) -> str:
    return _ctl_names().get(cid, cid)


# ── 쓰기 ──

def to_markdown(R: dict[str, Any]) -> str:
    out = ["# 실험: 에이전트 유형 × 규제 기준", "", f"만든 시각 {R['manifest']['generated_at']} · 의무 라이브러리 기준일 {R['manifest']['library_as_of']} "
           f"(조문 {R['manifest']['obligations']}개, 변호사 검토 전) · 도구 버전 {R['manifest']['tool_rev']}", "", "## 결과 요약", ""]
    out += [f"- {s}" for s in findings(R)] + [""]
    for title, head, rows in tables(R):
        parts = title.split(". ")
        note = ". ".join(parts[2:])
        out += [f"## {parts[0]}. {parts[1]}", ""] + ([note, ""] if note else []) + ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        out += ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows] + [""]
    out += ["## 해석 의존 시나리오", ""] + [f"- {x['id']} {x['label']}: {', '.join(_dep_names(x)) or '없음'} ({', '.join(x['interpretation_dependent'])})"
                                          for x in R["agents"]] + [""]
    return "\n".join(out)


def to_csv(R: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["agent", "label", "reading", "metric", "value"])
    for x in R["agents"]:
        for rd, m in x["readings"].items():
            for k, v in m.items():
                if k == "exposure":
                    for p, e in v.items():
                        w.writerow([x["id"], x["label"], rd, f"exposure_p{p}", e])
                else:
                    w.writerow([x["id"], x["label"], rd, k, v])
        for k in ("applicable", "binding", "binding_ai", "conflict", "offline", "cases", "tools"):
            w.writerow([x["id"], x["label"], "", k, x[k]])
        w.writerow([x["id"], x["label"], "", "interpretation_dependent", len(x["interpretation_dependent"])])
    return "﻿" + buf.getvalue()


def write_all(out_dir: Path = OUT_DIR / "experiment", R: dict[str, Any] | None = None) -> list[Path]:
    R = R or run()
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {"results.csv": to_csv(R), "summary.md": to_markdown(R),
             "manifest.json": json.dumps(R["manifest"], ensure_ascii=False, indent=1),
             "results.json": json.dumps(R, ensure_ascii=False, indent=1, default=str)}
    paths = []
    for name, text in files.items():
        p = out_dir / name
        p.write_text(text, encoding="utf-8")
        paths.append(p)
    return paths


def page(R: dict[str, Any]) -> str:
    """연구 노트 형식의 실험 페이지(out/experiment.html). 첫 화면과 같은 틀 · 토큰 · 규칙(그림 N 캡션, 상자는 그림에만)."""
    from .landing import _tpl
    e = html.escape
    m = R["manifest"]
    T = tables(R)

    def table(t):
        title, head, rows = t
        return (f'<figure class="fig tblfig"><figcaption><b>{e(title.split(". ")[0])}</b> {e(title.split(". ", 1)[1])}</figcaption><div class="tblwrap"><table class="xt">'
                "<thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div></figure>")

    dep_rows = "".join(f"<li><b>{e(x['id'] + ' ' + x['label'])}</b> {e(', '.join(_dep_names(x)) or '없음')}</li>" for x in R["agents"])
    body = f"""
<header class="masthead" id="top">
<p class="kicker">실험 노트 · {e(m['generated_at'][:10])} 기준</p>
<h1>에이전트 유형마다, 규제를 어떻게 읽느냐에 따라</h1>
<p class="deck">증권사의 대표적인 AI 에이전트 일곱 유형에 실제로 걸리는 조문을 골라 통제 수준을 세 가지 기준으로 도출하고, 각 유형의 도구로 만든 공격 시나리오를 같은 정책 엔진으로 돌렸다. 기준은 명문 기준, 확장 해석 기준, 자율규범 포함 기준이다.</p>
</header>
<section class="sh lead" aria-labelledby="h-r"><h2 id="h-r">결과</h2><div>
<div class="summary">{''.join(f'<p>{e(s)}</p>' for s in findings(R))}</div>
<figure class="fig"><figcaption><b>그림 1</b> 규제 기준별 공격 시나리오 판정. 일곱 유형의 시나리오를 합했다. 맨 위와 맨 아래는 기준선이다.</figcaption>{figure_aggregate(R)}{legend()}</figure>
</div></section>
<section class="sh" aria-labelledby="h-a"><h2 id="h-a">유형별</h2><div>
<figure class="fig"><figcaption><b>그림 2</b> 유형별 판정. 막대 하나가 그 유형의 공격 시나리오 전체다.</figcaption>{figure_agents(R)}{legend()}</figure>
{table(T[0])}{table(T[1])}
</div></section>
<section class="sh" aria-labelledby="h-s"><h2 id="h-s">공격 유형별</h2><div>
{table(T[2])}
<h3 class="deph">해석 의존 시나리오</h3><p class="body">명문 기준과 확장 해석 기준 사이에서 판정이 바뀌는 시나리오를 공격 유형으로 묶었다. 시나리오별 식별자는 experiment/summary.md 에 있다.</p><ul class="dep">{dep_rows}</ul>
</div></section>
<section class="sh" aria-labelledby="h-t"><h2 id="h-t">합계와 민감도</h2><div>{table(T[3])}{table(T[4])}</div></section>
<section class="sh" aria-labelledby="h-m"><h2 id="h-m">방법</h2><div>
<p class="body">에이전트 유형은 저자가 정한 합성 유형이다(registry/experiment_agents.yaml). 도구 이름, 인자, 배포 형태, 하는 일, 다루는 정보를 고정하고, 통제 수준만 기준마다 바꾼다. 걸리는 조문은 증권 의무 라이브러리({m['obligations']}개, 기준일 {e(m['library_as_of'])})에서 적용 조건으로 골랐다.</p>
<p class="body">명문 기준은 강제 조문을 문언대로 읽어, AI를 명시하거나 행위 자체를 규율하는 조문만 AI 수준을 요구한 것으로 본다. 확장 해석 기준은 사람·계정을 대상으로 쓴 강제 조문도 에이전트에 적용한다. 자율규범 포함 기준은 가이드라인과 평가기준까지 넣는다.</p>
<p class="body">시나리오 판정은 정책 엔진 샌드박스 재실행이다. 사람 승인 단계에서 멈춘 공격은 승인자가 승인한다고 가정해 한 번 더 돌려, 뒤의 통제가 막으면 자동 차단, 실행되면 승인 의존으로 분류한다. 결과는 결정적이다.</p>
</div></section>
<section class="sh" aria-labelledby="h-l"><h2 id="h-l">한계</h2><div><ul class="lim">
<li>조문 대응과 적용 조건, 조문이 에이전트에 미치는 방식의 구분은 변호사 검토 전이다.</li>
<li>에이전트 유형과 도구 구성은 가정이다. 같은 업무라도 도구를 다르게 나누면 결과가 달라진다.</li>
<li>시나리오는 정책 엔진의 판정을 본다. 모델이 실제로 숨은 지시를 따르는지는 LLM 레드팀으로 따로 잰다.</li>
<li>통제 수준 2(AI 수준)는 런타임이 집행한다고 가정한다. 운영 효과성(실제로 그렇게 돌고 있는지)은 이 실험 밖이다.</li>
</ul>
<p class="note-s">재현: 도구 버전 {e(m['tool_rev'])} · 에이전트 정의 지문 {e(m['agents_hash'])} · 시나리오 지문 {e(', '.join(f'{k} {v}' for k, v in m['case_hashes'].items()))}. 원자료는 experiment/results.csv · results.json.</p>
</div></section>"""
    css = """
.xfig{width:100%;height:auto;margin:4px 0 0}
.xfig .t{font-size:12.5px;fill:var(--pq-ivory-soft)}
.xfig .h{font-size:12px;font-weight:600;fill:var(--pq-ivory-dim)}
.xfig .n{font-size:12px;fill:var(--pq-ivory)}
.xfig .s{font-size:11.5px;fill:var(--pq-ivory-dim)}
.key{display:flex;flex-wrap:wrap;gap:6px 16px;margin:10px 0 0;font-size:12.5px;color:var(--pq-ivory-dim)}
.key i{display:inline-block;width:12px;height:12px;margin-right:6px;vertical-align:-1px;border-radius:2px;box-shadow:inset 0 0 0 1px var(--pq-ivory-line)}
.tblfig{margin:28px 0 0}
.xt{font-size:13px}
.xt td:first-child{white-space:nowrap;font-weight:600}
.xt th{white-space:nowrap}
.deph{margin:36px 0 6px}
.dep{margin:8px 0 0;padding-left:18px;font-size:13.5px;color:var(--pq-ivory-soft)}
.dep li{margin:4px 0}
.lim{margin:0;padding-left:18px;color:var(--pq-ivory-soft);font-size:14px;line-height:1.7}
.summary p{margin:0 0 10px}
"""
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>실험: 에이전트 유형 × 규제 기준 · PivoxPolicy</title>
<meta name="description" content="증권사 AI 에이전트 일곱 유형에 걸리는 조문으로 통제 수준을 도출하고 공격 시나리오를 돌린 실험." />
<meta name="theme-color" content="#050505" />
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin />
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
<style>
{_tpl("tokens.css")}
{_tpl("base.css")}
{_tpl("landing.css")}
{css}
</style>
</head>
<body>
<a class="skip" href="#main">본문으로</a>
<div class="wrap land">
<header class="topbar">
<a class="brand" href="./" aria-label="PivoxPolicy 홈">Pivox<span class="b">Policy</span></a>
<nav class="nav" aria-label="페이지"><a href="sim.html">모의 테스트</a><a href="dashboard.html">대시보드</a><a href="./">첫 화면</a></nav>
</header>
<main id="main">{body}
</main>
<footer class="site"><span>PivoxPolicy 실험 노트. 법률 자문이 아니다.</span><span class="links"><a href="./">첫 화면</a></span></footer>
</div>
</body>
</html>
"""


def build(out_dir: Path = OUT_DIR) -> list[Path]:
    """out/experiment.html + out/experiment/(CSV · MD · JSON · manifest)."""
    R = run()
    paths = write_all(out_dir / "experiment", R)
    p = out_dir / "experiment.html"
    p.write_text(page(R), encoding="utf-8")
    return [p, *paths]
