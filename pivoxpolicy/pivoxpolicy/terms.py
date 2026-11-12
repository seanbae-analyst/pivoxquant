"""용어 — 런타임 콘솔 · 진단 보고서 · LLM 레드팀 · 실험 결과가 같은 말을 쓰도록 한 곳에 둔다.

연구 보고서 · 논문 표에 그대로 옮길 수 있는 말로 정했다. 콘솔은 /admin/api/meta 의 terms 로 받아 쓴다.

시나리오 판정
  공격      자동 차단(런타임 통제가 막음) · 승인 의존(사람 승인 단계에서만 멈춤 — 승인하면 실행) · 미차단(끝까지 실행) · 공격면 없음
  정상 업무  정상 처리 · 승인 대기(사람 승인을 기다림) · 과잉 차단(자동 통제가 정상 업무를 막음)
조문과 결과의 관계
  미차단 · 승인 의존의 경우: 명문 요구 미충족 · 해석상 요구 미충족 · 자율규범 미이행 · 규율 공백
  자동 차단의 경우:         명문 요구에 따른 차단 · 해석상 요구에 따른 차단 · 자율규범에 따른 차단 · 근거 조문 없는 자체 통제
규제 기준(통제 수준을 도출하는 읽기 방식)
  명문 기준 · 확장 해석 기준(사람·계정 조문을 에이전트에도 적용) · 자율규범 포함 기준
조문이 에이전트에 미치는 방식
  AI 명시 · 행위 규율(처리 주체와 무관) · 주체 확장 해석(사람·계정 조문을 에이전트에) · 사람·계정 한정
"""

from __future__ import annotations

from typing import Any

LEVEL = ["없음", "사람·계정", "AI까지"]

ATTACK = {"good": "자동 차단", "held": "승인 의존", "defect": "미차단", "na": "공격면 없음"}
ATTACK_SHORT = {"good": "차단", "held": "승인", "defect": "미차단", "na": "·"}
BENIGN = {"good": "정상 처리", "approval": "승인 대기", "overblock": "과잉 차단", "na": "해당 없음"}
BENIGN_SHORT = {"good": "처리", "approval": "대기", "overblock": "과잉", "na": "·"}
SUMMARY = {"defect": "미차단", "held": "승인 의존", "good": "자동 차단 · 정상 처리", "friction": "정상 업무 제약", "na": "공격면 없음"}

LINK = {"violation": "명문 요구 미충족", "interpretive": "해석상 요구 미충족", "guideline": "자율규범 미이행", "gap": "규율 공백"}
LINK_LONG = {
    "violation": "이 에이전트에 걸리는 강제 조문이 이 통제를 문언대로 AI 수준까지 요구한다(AI 명시 또는 행위 규율).",
    "interpretive": "걸리는 강제 조문은 사람·계정 층만 말한다. 주체를 에이전트로 넓혀 읽으면 요구 미충족이고, 아니면 규율 공백이다.",
    "guideline": "자율규범(가이드라인, 평가기준)만 이 통제를 요구한다.",
    "gap": "이 에이전트에 걸리는 조문 가운데 이 통제를 요구하는 것이 없다.",
}
STOP = {"violation": "명문 요구에 따른 차단", "interpretive": "해석상 요구에 따른 차단", "guideline": "자율규범에 따른 차단",
        "gap": "근거 조문 없는 자체 통제"}
STOP_LONG = {
    "violation": "강제 조문이 문언대로 요구하는 차단이다.",
    "interpretive": "강제 조문은 사람·계정 층만 말한다. 주체를 에이전트로 넓혀 읽을 때의 요구에 따른 차단이다.",
    "guideline": "자율규범이 요구하는 차단이다.",
    "gap": "이 차단을 요구하는 조문은 이 에이전트에 걸리지 않는다. 회사가 스스로 둔 통제다.",
}
MODE = {"binding_explicit": "명문 기준", "binding_interpretive": "확장 해석 기준", "guideline": "자율규범 포함 기준"}
MODE_LONG = {"binding_explicit": "강제 조문을 문언대로 읽는다",
             "binding_interpretive": "사람·계정을 대상으로 쓴 강제 조문을 에이전트에도 적용한다",
             "guideline": "자율 가이드라인과 평가기준까지 넣는다"}
STATUS = {"met": "충족", "partial": "사람·계정 층만 충족", "unmet": "미충족", "offline": "런타임 외(증적 점검)", "conflict": "구성상 저촉"}
FIX = "단일 보완 통제"
# 공격 유형(시나리오 원형). sim_scenarios.yaml 의 id 와 같다.
SCENARIO = {"prompt_injection": "간접 프롬프트 주입", "approval_exploitation": "승인 절차 악용", "insider_misuse": "내부자 권한 남용",
            "rogue_agent": "자율 실행 일탈", "multi_agent_cascade": "에이전트 간 위임 전파", "supply_chain": "공급망 변조",
            "ai_credentials": "자격증명 유출", "cross_customer_leak": "고객 간 정보 노출", "tool_poisoning": "도구 설명 오염",
            "memory_poisoning": "기억 오염", "code_execution": "코드 실행 이탈", "ai_attacker": "AI 이용 침투"}
CONFLICT = "구성상 저촉"


def coverage(layer: str | None, extends: str | None, binding: bool = True) -> str:
    """조문이 에이전트에 미치는 방식."""
    if layer == "agent":
        return "AI 명시"
    if extends == "direct":
        return "행위 규율"
    if extends == "interpretive":
        return "주체 확장 해석"
    return "사람·계정 한정"


def strength(r: dict[str, Any]) -> str:
    """조문 한 줄의 강제력 × 미치는 방식 — 보고서 · 표의 짧은 꼬리표."""
    cov = coverage(r.get("layer"), r.get("extends"))
    return ("강제 · " if r.get("binding") else "자율 · ") + cov


def benign_key(control: str | None) -> str:
    """정상 업무가 막혔을 때: 사람 승인에서 멈췄으면 승인 대기, 다른 통제면 과잉 차단."""
    return "approval" if control == "human_approval" else "overblock"


def verdict_label(kind: str, verdict: str, control: str | None = None, short: bool = False) -> str:
    if kind == "attack":
        return (ATTACK_SHORT if short else ATTACK).get(verdict, verdict)
    key = "good" if verdict == "good" else ("na" if verdict == "na" else benign_key(control))
    return (BENIGN_SHORT if short else BENIGN)[key]


def as_dict() -> dict[str, Any]:
    """콘솔이 받는 용어 묶음."""
    return {"level": LEVEL, "attack": ATTACK, "attack_short": ATTACK_SHORT, "benign": BENIGN, "benign_short": BENIGN_SHORT,
            "summary": SUMMARY, "link": LINK, "link_long": LINK_LONG, "stop": STOP, "stop_long": STOP_LONG, "mode": MODE,
            "mode_long": MODE_LONG, "status": STATUS, "fix": FIX, "conflict": CONFLICT,
            "scenario": SCENARIO}
