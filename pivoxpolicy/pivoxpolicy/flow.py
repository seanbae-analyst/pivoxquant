"""명령 흐름 — 명령(도구 호출) 하나가 지시 출처에서 런타임 판정 일곱 단계를 거쳐 결과에 이르는 길.

정책 엔진(policy.decide)이 남긴 checks(통제마다 pass · block · approval · flag · off · not_reached)를 그대로 그린다.
그림을 위해 판정을 다시 계산하거나 꾸미지 않는다. 실험 페이지와 진단 보고서가 같이 쓴다(스크립트 없음, HTML + CSS).

한 줄(lane) = 한 규제 기준에서의 시나리오 한 건. 단계마다
  지시 출처 · 인증 · 위임 · 구성요소 → 도구 호출(인자) → 판정 일곱 단계 → 결정
을 보이고, 끝에 판정(자동 차단 · 승인 의존 · 미차단 …)을 적는다. 승인 의존이면 '승인되면' 줄을 하나 더 그린다.
"""

from __future__ import annotations

import functools
import html
from typing import Any

from . import terms
from .runtime import policy

# 정책 엔진이 그 단계에서 보는 것(policy.decide 의 순서 그대로)
GATE_WHAT = {
    "inventory": "등록된 도구인가, 등록 기한 안인가",
    "vendors": "구성요소 이름 · 버전 · 지문이 승인된 것인가",
    "unique_id": "에이전트 전용 단기 토큰인가, 등록된 위임인가",
    "least_privilege": "도구 권한 · 외부 입력 · 응대 고객 범위 · 금액 한도",
    "human_approval": "고위험 호출은 그 요청 그대로 승인됐는가",
    "audit_trail": "입력 출처를 남기고 고위험 호출 빈도를 본다",
    "kill_switch": "이상 빈도면 에이전트를 자동으로 멈춘다",
}
STATE = {"pass": "통과", "block": "차단", "approval": "승인 요청", "flag": "탐지", "off": "검사 안 함", "not_reached": "도달 안 함"}
DECISION = {"allow": "허용", "deny": "거부", "require_approval": "승인 대기", "no_tool": "도구 없음"}
SRC = {"web": "외부 글", "email": "메일", "customer_message": "고객 메시지", "agent": "다른 에이전트", "user": "운영자 지시",
       "plan": "에이전트 자체 계획", "tool_description": "도구 설명"}
VERDICT_CLASS = {"good": "v-good", "held": "v-held", "defect": "v-defect", "na": "v-na", "friction": "v-held"}

e = html.escape


@functools.lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    from .diagnosis import _controls
    return {c["id"]: c["name"] for c in _controls()}


def gate_name(c: str) -> str:
    return _names().get(c, c)


def _fmt(v: Any) -> str:
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    return f'"{v}"'


def _call(tool: str | None, args: dict[str, Any] | None) -> str:
    a = ", ".join(f"{k}={_fmt(v)}" for k, v in (args or {}).items())
    return f"{tool or '?'}({a})"


def _chips(st: dict[str, Any]) -> list[str]:
    """그 단계의 입력 조건 — 출처 · 인증 · 위임 · 구성요소 · 반복 · 응대 고객."""
    out = []
    srcs = st.get("input_sources") or []
    if srcs:
        for s in srcs:
            out.append(f"출처 {SRC.get(s.get('kind'), s.get('kind'))}" + ("" if s.get("trusted") else "(신뢰하지 않는 입력)"))
    else:
        out.append("출처 표시 없음")
    out.append("인증 장기 키" if st.get("auth") == "key" else "인증 단기 토큰")
    if st.get("on_behalf_of"):
        out.append(f"위임 {st['on_behalf_of']}")
    if st.get("component_override"):
        out.append("구성요소 " + ", ".join(f"{k} {v}" for k, v in st["component_override"].items()))
    if (st.get("context") or {}).get("customer"):
        out.append(f"응대 고객 {st['context']['customer']}")
    if int(st.get("repeat") or 1) > 1:
        out.append(f"{st['repeat']}회 반복")
    return out


def _last_per_step(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """반복 단계는 마지막 시행만(멈춘 시행이거나 끝까지 간 시행)."""
    last: dict[int, dict[str, Any]] = {}
    for s in steps:
        last[s["step"]] = s
    return [last[k] for k in sorted(last)]


def _norm(checks: list[dict[str, Any]] | None) -> list[tuple[int, str, str, str]]:
    """일곱 단계 순서대로 (번호, 통제, 결과, 메모)."""
    by = {c["control"]: c for c in checks or []}
    out = []
    for i, c in enumerate(policy.CONTROL_ORDER, 1):
        ch = by.get(c) or {"result": "not_reached", "note": ""}
        out.append((i, c, ch["result"], ch.get("note") or ""))
    return out


def _gates(checks: list[dict[str, Any]]) -> str:
    """판정 일곱 칸(넓은 화면)."""
    cells = []
    for i, c, r, note in _norm(checks):
        if r == "off":
            note = note or "없음"
        cells.append(f'<li class="fl-g s-{r}"><span class="fl-gn">{i} {e(gate_name(c))}</span><span class="fl-gs">{e(STATE.get(r, r))}</span>'
                     + (f'<span class="fl-gx">{e(note)}</span>' if note and r not in ("not_reached", "pass") else "") + "</li>")
    return '<ol class="fl-gates">' + "".join(cells) + "</ol>"


def _mini(checks: list[dict[str, Any]], dtxt: str) -> str:
    """판정 일곱 칸을 한 줄로 — 번호 칸 일곱 개 + 상태별 번호 요약. 앞 단계와 좁은 화면에 쓴다."""
    rows = _norm(checks)
    sq = "".join(f'<li class="s-{r}" title="{i} {e(gate_name(c))}: {e(STATE.get(r, r))}">{i}</li>' for i, c, r, _ in rows)
    groups: dict[str, list[str]] = {}
    for i, _, r, _ in rows:
        groups.setdefault(r, []).append(str(i))
    order = ("block", "approval", "flag", "pass", "off", "not_reached")
    summ = " · ".join(f"{STATE[k]} {'·'.join(groups[k])}" for k in order if k in groups)
    acted = [(i, c, r, n) for i, c, r, n in rows if r in ("block", "approval", "flag")]
    act = "".join(f'<span class="fl-act">{i} {e(gate_name(c))} {e(STATE[r])}' + (f": {e(n)}" if n else "") + "</span>" for i, c, r, n in acted)
    return (f'<div class="fl-mini-w"><ol class="fl-mini" aria-hidden="true">{sq}</ol><span class="fl-sum">{e(summ)}</span>'
            f'<span class="fl-arrow">→ {e(dtxt)}</span></div>' + (f'<p class="fl-acts">{act}</p>' if act else ""))


def _step(tr: dict[str, Any], st: dict[str, Any], label: str | None = None, decisive: bool = True) -> str:
    """단계 하나. decisive(결과를 정한 단계)면 넓은 화면에서 일곱 칸을 다 펴고, 아니면 한 줄로 접는다."""
    head = label or f"단계 {tr['step']}" + (f" · {tr['repeat']}회째" if int(st.get("repeat") or 1) > 1 else "")
    chips = "".join(f'<span class="fl-chip">{e(c)}</span>' for c in _chips(st))
    if tr.get("decision") == "no_tool":
        return (f'<div class="fl-step"><p class="fl-sh"><b>{e(head)}</b> {e(tr.get("note") or "")}</p>'
                f'<p class="fl-dec d-deny">{e(tr.get("reason") or "")}</p></div>')
    dec = tr.get("decision")
    dtxt = DECISION.get(dec, dec)
    if tr.get("approved"):
        dtxt = "승인 요청 → 승인됨(가정)"
    top = (f'<p class="fl-sh"><b>{e(head)}</b> {e(tr.get("note") or "")}</p><p class="fl-in">{chips}</p>'
           f'<p class="fl-call"><span class="fl-k">도구 호출</span><code>{e(_call(tr.get("tool"), st.get("args")))}</code></p>')
    if not decisive:
        return f'<div class="fl-step is-minor">{top}{_mini(tr.get("checks"), dtxt)}</div>'
    return (f'<div class="fl-step">{top}<div class="fl-full">{_gates(tr.get("checks"))}</div>'
            f'<div class="fl-compact">{_mini(tr.get("checks"), dtxt)}</div>'
            f'<p class="fl-dec d-{e(dec or "")}">{e(dtxt)}' + (f' · {e(tr.get("reason") or "")}' if dec != "allow" else "") + "</p></div>")


def outcome_text(res: dict[str, Any]) -> str:
    """판정 한 줄 설명(사람이 읽는 문장)."""
    v, kind = res["verdict"], res["kind"]
    ctl = gate_name(res["control"]) if res.get("control") else None
    if v == "na":
        return "이 에이전트에는 그 공격이 쓸 도구가 없다."
    if kind == "attack":
        if v == "defect":
            return "모든 단계가 허용되어 명령이 실행됐다."
        if v == "good":
            ia = res.get("if_approved")
            if ia and ia.get("control"):
                return f"사람 승인 단계에서 멈췄고, 승인되더라도 {gate_name(ia['control'])} 단계가 막는다."
            return f"{ctl} 단계에서 자동으로 막혔다."
        if v == "held":
            return "사람 승인 단계에서만 멈췄다. 승인되면 실행된다."
    if v == "good":
        return "정상 업무가 끝까지 처리됐다."
    return f"정상 업무가 {ctl} 단계에서 멈췄다(" + terms.verdict_label("benign", v, res.get("control")) + ")."


def lane(res: dict[str, Any], case: dict[str, Any], label: str, sub: str = "") -> str:
    """한 규제 기준에서의 시나리오 한 건."""
    steps = case.get("steps") or []
    body = []
    trs = _last_per_step(res.get("steps") or [])
    for n, tr in enumerate(trs):
        st = steps[tr["step"] - 1] if 0 < tr["step"] <= len(steps) else {}
        body.append(_step(tr, st, decisive=n == len(trs) - 1))
    ia = res.get("if_approved")
    if res["verdict"] == "held" and ia:
        tr = _last_per_step(ia.get("steps") or [])[-1]
        st = steps[tr["step"] - 1] if 0 < tr["step"] <= len(steps) else {}
        body.append('<p class="fl-then">승인자가 승인하면(가정) 같은 요청을 다시 판정한다</p>' + _step(tr, st, label=f"단계 {tr['step']} · 승인 뒤"))
    vl = terms.verdict_label(res["kind"], res["verdict"], res.get("control"))
    vc = VERDICT_CLASS.get(res["verdict"], "v-na") if res["kind"] == "attack" else ("v-good" if res["verdict"] == "good" else "v-held")
    return (f'<section class="fl-lane"><header class="fl-lh"><b>{e(label)}</b>' + (f'<span>{e(sub)}</span>' if sub else "") + "</header>"
            + "".join(body)
            + f'<p class="fl-res"><i class="sw {vc}"></i><b>{e(vl)}</b> {e(outcome_text(res))}</p></section>')


def compare(case: dict[str, Any], lanes: list[tuple[str, str, dict[str, Any]]], title: str | None = None) -> str:
    """같은 시나리오를 여러 기준으로 — lanes: [(기준 이름, 부제, run_case 결과)]. 단계와 판정 칸이 위아래로 맞는다."""
    t = (case.get("title") or case["id"]) if title is None else title
    story = case.get("story") or ""
    return ('<div class="fl">' + (f'<p class="fl-t">{e(t)}</p>' if t else "") + (f'<p class="fl-story">{e(story)}</p>' if story else "")
            + "".join(lane(r, case, lb, sub) for lb, sub, r in lanes) + "</div>")


def order_legend() -> str:
    """판정 순서 — 정책 엔진이 명령 하나를 보는 차례와 각 단계가 보는 것."""
    items = "".join(f'<li><b>{i} {e(gate_name(c))}</b><span>{e(GATE_WHAT[c])}</span></li>' for i, c in enumerate(policy.CONTROL_ORDER, 1))
    states = "".join(f'<span class="fl-g s-{k}"><span class="fl-gs">{e(v)}</span></span>' for k, v in STATE.items())
    return (f'<ol class="fl-order">{items}</ol><p class="fl-states"><span class="fl-k">칸 표시</span>{states}</p>'
            '<p class="fl-note">검사 안 함은 그 통제가 AI 수준(레벨 2)이 아니어서 런타임이 보지 않은 단계다. 사람·계정 층의 절차가 있더라도 명령은 그대로 지나간다.</p>')


CSS = """
:root{--v-good:#5E4A31;--v-good-ink:var(--pq-ivory);--v-held:#B8956A;--v-held-ink:#050505;--v-defect:#F5F0E8;--v-defect-ink:#050505;--v-na:#1d1b18;--v-na-ink:var(--pq-ivory-dim);--fl-block:var(--pq-bronze);--fl-block-ink:#050505}
.fl{margin:0 0 28px}
.fl-t{margin:0 0 4px;font-size:16.5px;font-weight:700;color:var(--pq-ivory)}
.fl-story{margin:0 0 14px;font-size:15px;line-height:1.7;color:var(--pq-ivory-soft);max-width:72ch}
.fl-lane{margin:0 0 12px;padding:16px 18px;border:1px solid var(--pq-ivory-line-strong);border-radius:10px}
.fl-lh{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin:0 0 10px}
.fl-lh b{font-size:15.5px;color:var(--pq-bronze)}
.fl-lh span{font-size:14px;color:var(--pq-ivory-dim)}
.fl-step{margin:0 0 12px}
.fl-sh{margin:0 0 6px;font-size:15px;line-height:1.6;color:var(--pq-ivory-soft)}
.fl-sh b{margin-right:6px;color:var(--pq-ivory)}
.fl-in{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
.fl-chip{padding:2px 8px;border:1px solid var(--pq-ivory-line-strong);border-radius:6px;font-size:13.5px;color:var(--pq-ivory-soft)}
.fl-call{margin:0 0 10px;font-size:14px;color:var(--pq-ivory-soft);overflow-wrap:anywhere}
.fl-call code{font-family:inherit;font-size:14px;color:var(--pq-ivory)}
.fl-k{margin-right:8px;font-size:13px;font-weight:600;color:var(--pq-ivory-dim)}
.fl-gates{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px;margin:0;padding:0;list-style:none}
.fl-g{display:flex;flex-direction:column;gap:2px;min-height:64px;padding:8px 9px;border-radius:6px;border:1px solid var(--pq-ivory-line-strong)}
.fl-gn{font-size:13px;font-weight:600;color:var(--pq-ivory-soft)}
.fl-gs{font-size:14.5px;font-weight:700;color:var(--pq-ivory)}
.fl-gx{font-size:12.5px;line-height:1.45;color:var(--pq-ivory-dim)}
.fl-g.s-block{background:var(--fl-block);border-color:var(--fl-block)}
.fl-g.s-block .fl-gn,.fl-g.s-block .fl-gs,.fl-g.s-block .fl-gx{color:var(--fl-block-ink)}
.fl-g.s-approval{border:2px solid var(--pq-bronze)}
.fl-g.s-approval .fl-gs{color:var(--pq-bronze)}
.fl-g.s-flag{border-color:var(--pq-bronze)}
.fl-g.s-off{border-color:var(--pq-ivory-line);background:transparent}
.fl-g.s-off .fl-gs{font-weight:500;color:var(--pq-ivory-faint)}
.fl-g.s-off .fl-gn{color:var(--pq-ivory-dim)}
.fl-g.s-not_reached{border-color:var(--pq-ivory-line);opacity:.4}
.fl-g.s-not_reached .fl-gs{font-weight:500}
.fl-dec{margin:8px 0 0;font-size:14.5px;color:var(--pq-ivory-soft)}
.fl-compact{display:none}
.fl-step.is-minor{padding-bottom:12px;border-bottom:1px solid var(--pq-ivory-line)}
.fl-mini-w{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px}
.fl-mini{display:flex;gap:3px;margin:0;padding:0;list-style:none}
.fl-mini li{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:5px;border:1px solid var(--pq-ivory-line-strong);font-size:13px;font-weight:700;color:var(--pq-ivory)}
.fl-mini li.s-block{background:var(--fl-block);border-color:var(--fl-block);color:var(--fl-block-ink)}
.fl-mini li.s-approval{border:2px solid var(--pq-bronze);color:var(--pq-bronze)}
.fl-mini li.s-flag{border-color:var(--pq-bronze)}
.fl-mini li.s-off{border-color:var(--pq-ivory-line);color:var(--pq-ivory-faint);font-weight:500}
.fl-mini li.s-not_reached{opacity:.35;font-weight:500}
.fl-sum{font-size:13.5px;color:var(--pq-ivory-dim)}
.fl-arrow{font-size:14px;color:var(--pq-ivory-soft)}
.fl-acts{display:flex;flex-direction:column;gap:4px;margin:8px 0 0}
.fl-act{font-size:14px;color:var(--pq-ivory)}
.fl-dec.d-allow::before,.fl-dec.d-deny::before,.fl-dec.d-require_approval::before{content:"결정 ";font-size:13px;font-weight:600;color:var(--pq-ivory-dim)}
.fl-dec.d-deny,.fl-dec.d-require_approval{color:var(--pq-ivory)}
.fl-then{margin:4px 0 8px;font-size:14px;color:var(--pq-bronze)}
.fl-res{max-width:none;display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:6px 0 0;padding-top:12px;border-top:1px solid var(--pq-ivory-line-strong);font-size:15px;line-height:1.6;color:var(--pq-ivory-soft)}
.fl-res b{font-size:16px;color:var(--pq-ivory)}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px}
.v-good{background:var(--v-good);color:var(--v-good-ink)}
.v-held{background:var(--v-held);color:var(--v-held-ink)}
.v-defect{background:var(--v-defect);color:var(--v-defect-ink)}
.v-na{background:var(--v-na);color:var(--v-na-ink)}
.fl-order{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px;margin:0 0 10px;padding:0;list-style:none}
.fl-order li{display:flex;flex-direction:column;gap:4px;padding:10px 9px;border-top:2px solid var(--pq-bronze)}
.fl-order b{font-size:14px;color:var(--pq-ivory)}
.fl-order span{font-size:13px;line-height:1.5;color:var(--pq-ivory-dim)}
.fl-states{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 6px}
.fl-states .fl-g{min-height:0;padding:3px 10px;flex-direction:row}
.fl-states .fl-gs{font-size:13.5px}
.fl-note{margin:0 0 22px;font-size:14px;line-height:1.7;color:var(--pq-ivory-dim);max-width:72ch}
@media(max-width:760px){
  .fl-full{display:none}
  .fl-compact{display:block}
  .fl-compact+.fl-dec{display:none}
  .fl-order{grid-template-columns:minmax(0,1fr)}
  .fl-order li{flex-direction:row;flex-wrap:wrap;gap:2px 10px;padding:8px 0 8px 10px;border-top:0;border-left:2px solid var(--pq-bronze)}
  .fl-lane{padding:14px 12px}
}
@media print{.fl-lane{break-inside:avoid}}
"""

# 밝은 바탕(진단 보고서 · 인쇄). --pq-* 토큰을 밝은 값으로 다시 정하고, 판정 색은 어두울수록 노출이 큰 순서 척도
# (#C4A57B → #8A6A3F → #2E2418, dataviz validate_palette --ordinal --mode light --surface #ffffff 통과).
CSS_LIGHT = """
:root{--pq-ivory:#111;--pq-ivory-soft:#3a3a3a;--pq-ivory-dim:#666;--pq-ivory-faint:#999;--pq-ivory-line:#ebe6dd;--pq-ivory-line-strong:#d9d4cc;
--pq-bronze:#8a6a3f;--v-good:#C4A57B;--v-good-ink:#111;--v-held:#8A6A3F;--v-held-ink:#fff;--v-defect:#2E2418;--v-defect-ink:#fff;
--v-na:#f1ede6;--v-na-ink:#666;--fl-block:#8a6a3f;--fl-block-ink:#fff}
"""
