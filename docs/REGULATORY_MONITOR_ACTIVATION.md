# Regulatory Monitor — 활성화 가이드

Agent: `regulatory-monitor`
버전: v2 (2026-05-06)
대상 독자: 1인 운영자 (배상현)

---

## 개요

`regulatory-monitor` agent는 PivoxQuant의 §101 면제 트랙과 마이데이터(§22의9) 비해당 상태를 위협할 수 있는 한국 금융 규제 변화를 일일 감시한다.

- Agent 정의 파일: `/Users/seanbae/Desktop/취준/pivoxquant/.claude/agents/regulatory-monitor.md`
- 취준 루트 복사본: `/Users/seanbae/Desktop/취준/.claude/agents/regulatory-monitor.md`
- 자문 질문 큐: `~/.claude/projects/-Users-seanbae-Desktop---/memory/legal_question_queue.md`
- 실행 로그 append 대상: `~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md`

---

## 1. 사용자가 직접 해야 하는 것

### 1-A. Scheduled Task 등록 (1회)

Claude Code에서 아래 명령 실행:

```
/schedule
```

스킬 실행 후 다음 내용으로 설정:
- **이름**: Regulatory Monitor Daily Scan
- **스케줄**: 매일 09:00 KST (cron: `0 0 * * *` UTC — KST는 UTC+9이므로 `0 0 * * *`)
- **프롬프트**:

```
regulatory-monitor agent를 Mode 1 일일 정기 스캔으로 실행하라.
대상 소스: 금융위원회, 금감원, 법제처 국가법령정보센터, 정통망법 관련 KISA, 핀테크 규제 샌드박스.
최근 24시간 신규 발행물 확인.
결과를 autopilot_log.md에 append하고, HIGH/CRITICAL 항목은 legal_question_queue.md에 자문 질문 추가.
§101 면제 트랙 및 §22의9 마이데이터 영향 여부 표기 필수.
```

또는 Claude Code 채팅에서 직접:

```
매일 09:00 KST에 다음을 실행하는 scheduled task를 등록해줘:
"regulatory-monitor agent Mode 1 일일 스캔 — 금융위/금감원/법제처/KISA 최근 24시간 감시,
 결과를 autopilot_log.md에 append, HIGH 이상은 legal_question_queue.md에 추가"
```

### 1-B. 수동 최초 실행 (등록 후 즉시)

```
regulatory-monitor를 실행해서 Mode 1 스캔을 지금 한 번 실행해줘.
기준 기간: 최근 7일.
```

첫 실행으로 baseline을 잡고 false positive 비율을 확인한다.

---

## 2. 무료 RSS 소스 검증 상태

아래는 각 소스의 RSS 지원 여부. `[VERIFY]` 표기는 agent 최초 실행 시 확인 필요.

| 소스 | URL | RSS 확인 상태 | 대체 방법 |
|------|-----|--------------|-----------|
| 금융감독원 보도자료 | `https://www.fss.or.kr/fss/bbs/B0000176/list.do?menuNo=200218` | [VERIFY] | RSS 없으면 WebFetch 직접 조회 |
| 금융위원회 보도자료 | `https://www.fsc.go.kr/no010101` | [VERIFY] | WebFetch 직접 조회 |
| 법제처 국가법령정보센터 | `https://www.law.go.kr` | [VERIFY] | 법령 검색 API 있음 (무료) |
| 금융위 법령고시 | `https://www.fsc.go.kr/po040301` | [VERIFY] | WebFetch 직접 조회 |
| KISA 개인정보 | `https://www.kisa.or.kr/public/laws/laws3.jsp` | [VERIFY] | WebFetch 직접 조회 |
| 자본시장연구원 | `https://www.kcmi.re.kr` | [VERIFY] | WebFetch 직접 조회 |
| 핀테크 규제 샌드박스 | `https://fintecsandbox.or.kr` | [VERIFY] | WebFetch 직접 조회 |

**비용 정책**: 모든 조회는 WebFetch (내장) 또는 WebSearch (내장) 사용. 외부 RSS 구독 서비스 / 유료 API 사용 금지. 추가 비용 0원.

**RSS 미지원 소스 처리**: RSS 피드가 없는 경우 WebFetch로 HTML 페이지를 직접 조회 후 최신 N개 항목 파싱. Agent 정의의 `[VERIFY]` 소스는 최초 실행 시 자동 확인하고 결과를 autopilot_log.md에 기록.

---

## 3. 첫 1주 검증 절차

### Day 1 — Baseline 수립

```
1. Mode 1 수동 실행 (최근 7일 기간)
2. 감지 건수 기록 (예상: 0-5건/주)
3. false positive 식별 기준 확립:
   - "PivoxQuant와 관련 없는 법규 변화"가 HIGH로 잘못 분류되면 false positive
   - 예: 금융투자업 인가 관련 변화인데 유사투자자문 §101에 직접 영향 없는 경우
```

### Day 2-5 — 자동 실행 모니터링

```
1. scheduled task 자동 실행 확인 (09:00 KST)
2. autopilot_log.md 확인: 항목이 append되는지
3. false positive 비율 측정:
   - 목표: HIGH 분류 중 실제 영향 있는 것 > 70%
   - false positive 누적 시: agent 키워드 필터 조정 요청
```

### Day 7 — 주간 리뷰

```
1. 감지 건수 합산 (일일 평균)
2. legal_question_queue.md 추가된 질문 수 확인
3. §101 / §22의9 영향 표기 정확성 검토
4. 스캔 주기 조정 필요 여부 판단 (일일 → 주 3회 등)
```

**acceptable false positive rate**: HIGH/CRITICAL 중 30% 이하. 초과 시 키워드 필터 좁힘.

---

## 4. autopilot_log.md / legal_question_queue.md 연동 방식

### autopilot_log.md

위치: `~/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md`

agent가 스캔 완료 시 아래 형식으로 append:

```markdown
## [2026-05-07] Regulatory Monitor — Daily Scan

- 검토 소스: 7개
- 신규 감지: 2건 (HIGH: 1, MEDIUM: 1, LOW: 0, N/A: 0)
- §101 영향: YES(1건)

### HIGH/MEDIUM 항목
| 발행일 | 기관 | 제목 | 영향도 | §101 | §22의9 | URL |
|--------|------|------|--------|------|--------|-----|
| 2026-05-06 | 금융위 | 유사투자자문업 감독 강화 방안 | HIGH | YES | NO | https://... |
| 2026-05-05 | 금감원 | AI 금융서비스 가이드라인 개정 예고 | MEDIUM | NO | NO | https://... |

### legal_question_queue.md 추가: 1건 (#1)
```

### legal_question_queue.md

위치: `~/.claude/projects/-Users-seanbae-Desktop---/memory/legal_question_queue.md`

HIGH 이상 항목 발견 시 자동 추가. 변호사 미팅 전 Sean이 이 파일을 열어 확인.

답변 완료 항목은 `## 답변 완료` 섹션으로 이동.

---

## 5. GitHub Actions 대안 (선택사항)

Claude Code Max 플랜 scheduled task가 아닌 GitHub Actions를 사용하려면:

```yaml
# .github/workflows/regulatory-monitor.yml
name: Regulatory Monitor
on:
  schedule:
    - cron: '0 0 * * *'  # 09:00 KST = 00:00 UTC
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger regulatory scan
        run: echo "GitHub Actions trigger — regulatory-monitor agent 수동 실행 필요"
```

**주의**: GitHub Actions는 Claude Code agent를 직접 실행할 수 없다. Actions는 알림/트리거 용도로만 사용하고, 실제 스캔은 Claude Code scheduled task로 실행해야 한다. GitHub Actions 무료 한도(2,000분/월) 소비 최소화 목적으로는 scheduled task 방식이 우선.

---

## 6. 비용 정리

| 항목 | 비용 | 비고 |
|------|------|------|
| WebFetch / WebSearch | 0원 | Claude Code 내장 |
| Claude Code Max scheduled task | 0원 추가 | Max 플랜 포함 |
| 외부 RSS 서비스 | 사용 금지 | 유료 불허 |
| GitHub Actions | 0원 (무료 한도 내) | 선택사항 |

**총 추가 비용: 0원**

---

## 7. Escalation 경로

```
regulatory-monitor 감지
       ↓
영향도 판단
       ↓
N/A / LOW ──────→ autopilot_log.md 기록만
       ↓
MEDIUM ──────────→ legal_question_queue.md 추가 + autopilot_log.md
       ↓
HIGH ────────────→ legal_question_queue.md 추가 + legal agent 호출 권고
       ↓
CRITICAL ────────→ 즉시 legal agent 호출 + 변호사 에스컬레이션 + Sean 직접 알림
```

변호사 자문 연락처: legal_compliance.md 내 등록된 외부 자문 채널 참조.

---

마지막 업데이트: 2026-05-06
