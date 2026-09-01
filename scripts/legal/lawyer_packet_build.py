#!/usr/bin/env python3
"""변호사 자료 주간 자동 정리 — lawyer_packet_build.py (T11, 2026-05-28).

매주 일요일 21:00 KST APScheduler ops_lawyer_packet_weekly 가 본 스크립트를
호출하여 ~/Desktop/취준/변호사상담_PivoxQuant/weekly_packet_<YYYY-MM-DD>.md 를
생성한다.

수집 내용
==========
1. legal_question_queue.md 21건 카테고리/우선순위/상태 표
2. 지난 1주 관련 코드 변경 (git log --since)
3. SHIP_BLOCKERS.md RELEASE-BLOCKER 섹션 원문 인용
4. 다음 변호사 미팅 권장 + 자료 첨부 가이드

절대 금지
==========
- 변호사 직접 이메일 전송 X
- legal_question_queue.md 본문 수정 X
- 법조항 새 해석 제시 X — 파일 원문만 인용
- 외부 API 호출 X
- 추가 비용 X (Max + 도메인 + Railway 외)

실행
====
python -m scripts.legal.lawyer_packet_build            # 실제 파일 생성
python -m scripts.legal.lawyer_packet_build --dry-run  # stdout preview
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_env_memory = os.environ.get("PIVOX_MEMORY_DIR", "").strip()
_MEMORY_DIR = Path(_env_memory) if _env_memory else (
    Path.home() / ".claude/projects/-Users-seanbae-Desktop---/memory"
)
_QUEUE_FILE = _MEMORY_DIR / "legal_question_queue.md"
_env_lawyer = os.environ.get("PIVOX_LAWYER_DIR", "").strip()
_LAWYER_DIR = Path(_env_lawyer) if _env_lawyer else (
    Path.home() / "Desktop/취준/변호사상담_PivoxQuant"
)
_SHIP_BLOCKERS = _REPO_ROOT / "SHIP_BLOCKERS.md"

try:
    from zoneinfo import ZoneInfo
    _KST = ZoneInfo("Asia/Seoul")
except ImportError:  # pragma: no cover
    _KST = timezone(timedelta(hours=9))

_CATEGORY_MAP: dict[str, str] = {
    "Q1": "신용정보법 §22의9 (마이데이터)",
    "Q2": "신용정보법 §22의9 (마이데이터)",
    "Q3": "신용정보법 §22의9 (마이데이터)",
    "Q4": "신용정보법 §22의9 (마이데이터)",
    "Q5": "전자상거래법 §13 (통신판매업)",
    "Q6": "PIPA §28-8 / GDPR (국외이전)",
    "Q7": "자본시장법 §101 (SaaS 구독료)",
    "Q8": "전자상거래법 / 부가가치세법 §10",
    "Q9": "PIPA §22 ⑥ (만 14세)",
    "Q10": "자본시장법 §101 ④ (rec_shares)",
    "Q11": "약관규제법 §7 (손해배상 한도)",
    "Q12": "정통망법 §50 (매출 6% 과징금)",
    "Q13": "자본시장법 §101 (양방향채널)",
    "Q14": "표시광고법 (AI 생성물 라벨)",
    "Q15": "전자상거래법 (가분적 환불, 2026-07-21 시행)",
    "Q-S1": "정통망법 §50 (분리 동의 framework)",
    "Q-S3": "자본시장법 §101 ② vs 통신판매업 신고",
    "Q-S4": "자본시장법 §49 (영문 레짐 신호)",
    "Q-M1": "자본시장법 §101 (유료광고 충돌)",
    "Q-M2": "자본시장법 §7 §101 (마케팅 용어)",
    "Q-M3": "표시광고법 §3①4호 (뒷광고)",
}

_CODE_PATH_MAP: dict[str, str] = {
    "Q1": "services/data/ (KIS read-only)",
    "Q2": "services/data/ (KIS read-only)",
    "Q3": "services/data/ (KIS read-only)",
    "Q4": "services/data/ (KIS read-only)",
    "Q5": "frontend/src/app/pricing/",
    "Q6": "frontend/src/app/(auth)/signup/",
    "Q7": "docs/legal/terms-of-service.md §6.1",
    "Q8": "business_registration.md",
    "Q9": "frontend/src/app/(auth)/signup/",
    "Q10": "(삭제됨: services/ai/service.py — 2026-09-01)",
    "Q11": "docs/legal/terms-of-service.md",
    "Q12": "services/email/ (opt-out)",
    "Q13": "(삭제됨: services/twin/twin_runner.py)",
    "Q14": "(삭제됨: services/artifacts/templates/ — 8-31 prune)",
    "Q15": "docs/legal/terms-of-service.md §17",
    "Q-S1": "services/email/ + frontend/src/app/(auth)/signup/",
    "Q-S3": "scripts/nightly/commerce_registration_reminder.py",
    "Q-S4": "(삭제됨: services/quant/engine.py — 8-31 prune)",
    "Q-M1": "frontend/src/app/landing/",
    "Q-M2": "frontend/src/app/landing/",
    "Q-M3": "(외부 채널)",
}

# 2026-09-01: 위 경로 중 일부는 코드가 실제로 삭제되어 "(삭제됨: ...)" 로 바뀌었다.
# 이게 중요한 이유 — 변호사 의견서는 1회 300-500만원이고, **없어진 기능에 대한
# 질문에 돈을 쓰면 안 된다.** Q10(rec_shares 포지션 사이즈 문구) · Q13/Q14
# (Artifact 푸시·AI 라벨링) · Q-S4(RegimeSwitching 영문 신호) 는 근거 코드가
# 전부 사라졌으므로 **상담 전에 CEO 가 "지금도 유효한 질문인가"를 판단**해야 한다.
# 큐 원본(legal_question_queue.md)은 CEO 의 법률 문서라 이 스크립트가 고치지
# 않는다 — 대신 패킷에 경고로 노출한다(_stale_code_warning).


# 주간 git log 를 뽑을 경로. 2026-09-01 이전엔 여기에 `services/billing/` ·
# `services/quant/engine.py` · `signup_v2/` 가 있었는데 **셋 다 존재하지 않는
# 경로**였다. `git log -- <없는 경로>` 는 에러 없이 그 경로만 조용히 기여 0으로
# 처리하므로 패킷은 **과소보고**했다 — 실측(2026-09-01): 옛 목록 1건 vs 아래
# 목록 3건. 특히 결제가 `services/billing/`(없음)로 잡혀 있어 실제 결제 코드인
# `routes/billing.py` 변경이 한 번도 안 잡혔다. 아래는 **존재하는 경로만**
# 남기도록 필터링해서, 다음에 또 경로가 사라져도 조용히 새지 않게 한다.
_CANDIDATE_GIT_LOG_PATHS: tuple[str, ...] = (
    "services/legal/",
    "services/email/",
    "scripts/legal/",
    "routes/billing.py",          # 결제는 services/billing/ 이 아니라 여기다
    "docs/legal/",
    "frontend/src/app/(auth)/signup/",
    "frontend/src/app/landing/",
)
_GIT_LOG_PATHS: list[str] = [
    _p for _p in _CANDIDATE_GIT_LOG_PATHS if (_REPO_ROOT / _p).exists()
]


def _stale_code_warning() -> str:
    """경로가 '(삭제됨' 으로 표시된 질문을 패킷 상단에 경고로 모은다.

    자동 점검이라 다음에 또 코드가 지워져도 스스로 드러난다 — 이 표가
    조용히 낡아서 없는 파일을 변호사에게 들이미는 걸 막는 게 목적이다.
    """
    stale = [q for q, path in _CODE_PATH_MAP.items() if path.startswith("(삭제됨")]
    if not stale:
        return ""
    lines = [
        "> ⚠️ **근거 코드가 삭제된 질문 %d건 — 상담 전 유효성 확인 필요**" % len(stale),
        ">",
        "> 아래 질문들은 이미 트리에서 사라진 코드를 근거로 작성됐다. 의견서는",
        "> 1회 300-500만원이므로 **없는 기능을 묻는 데 쓰지 말 것.**",
        ">",
    ]
    lines += ["> - `%s` — %s" % (q, _CODE_PATH_MAP[q]) for q in stale]
    return "\n".join(lines) + "\n"

_PRIORITY_MAP: dict[str, str] = {
    "Q1": "P0", "Q2": "P0", "Q3": "P0", "Q4": "P0",
    "Q5": "P0", "Q6": "P0", "Q7": "P0", "Q8": "P0",
    "Q13": "P0", "Q-S1": "P0 BLOCKER",
    "Q9": "P1", "Q10": "P1", "Q11": "P1",
    "Q12": "P1 (재스캔 2026-08-15)",
    "Q14": "P1", "Q15": "P1 (시행 2026-07-21)",
    "Q-S3": "P1", "Q-S4": "P1",
    "Q-M1": "P1", "Q-M2": "P2", "Q-M3": "P1",
}

_ALL_Q_IDS = [
    "Q1", "Q2", "Q3", "Q4",
    "Q5", "Q6", "Q7", "Q8",
    "Q9", "Q10", "Q11", "Q12",
    "Q13", "Q14", "Q15",
    "Q-S1", "Q-S3", "Q-S4",
    "Q-M1", "Q-M2", "Q-M3",
]


def _now_kst() -> datetime:
    return datetime.now(_KST)


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text("utf-8")
    except OSError as exc:
        logger.warning("파일 읽기 실패 %s: %s", path, exc)
        return ""


def _extract_release_blockers(ship_text: str) -> str:
    if not ship_text:
        return "(SHIP_BLOCKERS.md 읽기 실패)"
    lines = ship_text.splitlines()
    in_section = False
    buf: list[str] = []
    for line in lines:
        if "RELEASE-BLOCKER" in line and line.startswith("##"):
            in_section = True
        elif in_section and line.startswith("## ") and "RELEASE-BLOCKER" not in line:
            break
        if in_section:
            buf.append(line)
    return "\n".join(buf) if buf else "(RELEASE-BLOCKER 섹션 없음)"


def _git_log_legal_paths(since_days: int = 7) -> str:
    since = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    cmd = [
        "git", "-C", str(_REPO_ROOT),
        "log", f"--since={since}", "--oneline", "--",
        *_GIT_LOG_PATHS,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        out = result.stdout.strip()
        return out if out else "(지난 1주 관련 커밋 없음)"
    except Exception as exc:
        return f"(git log 실패: {exc})"


def _extract_q_summaries(queue_text: str) -> dict[str, str]:
    summaries: dict[str, str] = {}
    pattern = re.compile(r"^####\s+(Q[\w-]+)\s+[—\-–]\s+(.+)$", re.MULTILINE)
    for m in pattern.finditer(queue_text):
        summaries[m.group(1).strip()] = m.group(2).strip()
    for qid in ("Q1", "Q2", "Q3", "Q4"):
        if qid not in summaries:
            summaries[qid] = "마이데이터 / 신용정보법 회색지대 (KIS read-only)"
    return summaries


def _extract_answered_items(queue_text: str) -> set[str]:
    answered: set[str] = set()
    pattern = re.compile(
        r"####\s+(Q[\w-]+).*?ANSWERED\s+\d{4}-\d{2}-\d{2}", re.DOTALL
    )
    for m in pattern.finditer(queue_text):
        answered.add(m.group(1).strip())
    return answered


def _build_packet(dry_run: bool = False) -> str:
    today = _now_kst().strftime("%Y-%m-%d")
    queue_text = _read_text_safe(_QUEUE_FILE)
    ship_text = _read_text_safe(_SHIP_BLOCKERS)

    summaries = _extract_q_summaries(queue_text)
    answered = _extract_answered_items(queue_text)
    git_log = _git_log_legal_paths(since_days=7)
    release_block = _extract_release_blockers(ship_text)

    rows: list[str] = [
        "| ID | 카테고리 | 질문 요지 | 코드 경로 | 우선순위 | 상태 |",
        "|---|---|---|---|---|---|",
    ]
    for qid in _ALL_Q_IDS:
        summary = summaries.get(qid, "(큐에서 제목 미파싱)")
        if len(summary) > 55:
            summary = summary[:52] + "..."
        status = "ANSWERED" if qid in answered else "PENDING"
        rows.append(
            f"| {qid} | {_CATEGORY_MAP.get(qid, '—')} | {summary} "
            f"| `{_CODE_PATH_MAP.get(qid, '—')}` "
            f"| {_PRIORITY_MAP.get(qid, '—')} | {status} |"
        )
    table = "\n".join(rows)

    pending_count = len([q for q in _ALL_Q_IDS if q not in answered])
    answered_count = len(answered)

    packet = f"""# PivoxQuant 변호사 자문 큐 — 주간 패킷 {today}

> 자동 생성: scripts/legal/lawyer_packet_build.py (T11)
> 생성 시각: {_now_kst().strftime("%Y-%m-%d %H:%M:%S")} KST
> 큐 원본: {_QUEUE_FILE}
> 절대 금지: 변호사 직접 발송 X / 법조항 새 해석 X / 큐 본문 수정 X

---

## 1. 질문 큐 현황 요약

- 총 질문: {len(_ALL_Q_IDS)}건
- PENDING (변호사 답변 대기): {pending_count}건
- ANSWERED (답변 수령 완료): {answered_count}건
- 출시 RELEASE-BLOCKER 직결: R1 / R2 / R5 / R6 (SHIP_BLOCKERS.md)

## 2. 질문 큐 전체 표

{_stale_code_warning()}
{table}

---

## 3. 지난 1주 관련 코드 변경

경로: {" / ".join(_GIT_LOG_PATHS)}

```
{git_log}
```

---

## 4. SHIP_BLOCKERS.md — RELEASE-BLOCKER 원문 인용

{release_block}

---

## 5. 다음 변호사 미팅 권장

- 예상 자문료: 300-500만원 1회 일괄 의견서 (출처: legal_question_queue.md)
- 미팅 예약 상태: BLOCKED — CEO 직접 예약 필요
- 준비 자료:
  - 사업자등록증 PDF (459-01-03808)
  - terms-ko.md / privacy-ko.md
  - regulatory_changes_2026-05.md
  - Q-S1 보조: KISA 불법스팸 방지 정통망법 안내서 최신판
  - 변호사 작동설명 PDF: ~/Desktop/취준/변호사상담_PivoxQuant/PivoxQuant_변호사상담_작동설명.pdf (53p)
- 추천: 금융규제·자본시장법 전문 (Kim & Chang / 율촌 / 광장 등)

---

## 6. 변호사 답변 close 방법

1. legal_question_queue.md 해당 항목에 `ANSWERED YYYY-MM-DD: <요지>` 추가 (CEO 직접)
2. 다음 주 일요일 21:00 KST 자동 생성 패킷에서 ANSWERED 상태 자동 반영
3. VIOLATION 판정 시 해당 코드 fix + SHIP_BLOCKERS.md 해제 조건 충족 확인

---

본 파일은 매주 일요일 21:00 KST APScheduler ops_lawyer_packet_weekly 가 자동 생성합니다.
변호사에게 직접 발송하지 마십시오 — CEO 직접 컨택 후 첨부 파일로만 전달.
"""

    if dry_run:
        print(packet)
        logger.info("[lawyer_packet] --dry-run: stdout 출력 완료 (파일 미생성)")
        return packet

    _LAWYER_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _LAWYER_DIR / f"weekly_packet_{today}.md"
    out_path.write_text(packet, encoding="utf-8")
    logger.info("[lawyer_packet] 생성 완료: %s", out_path)
    return packet


def main() -> int:
    """APScheduler _wrap_python_main 진입점."""
    _build_packet(dry_run=False)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="변호사 자문 큐 주간 패킷 생성")
    parser.add_argument("--dry-run", action="store_true",
                        help="파일 저장 없이 stdout preview 만 출력")
    args = parser.parse_args()
    _build_packet(dry_run=args.dry_run)
