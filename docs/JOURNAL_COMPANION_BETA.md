# Journal Companion — Closed Beta 운영 런북

**작성**: 2026-04-23
**상태**: Closed Beta 준비 완료, 법적 검토 대기
**담당**: 배상현 (CEO + 개발자 본인)

본 문서는 Personal Journal Companion(Layer 4, Living CFO)의 운영·배포·비상 대응 절차를 정리한다. 기능의 법적 근거는 `reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6`, 구조적 정의는 `services/agents/prompts/companion_system.md`에 있다.

---

## 0. 현재 상태 체크리스트

| 항목 | 상태 |
|---|---|
| 코드 배포 | ✅ 완료 (`services/agents/`, `routes/agent.py`) |
| `AGENT_ENABLED` 기본값 | `0` (Dockerfile ENV) — 코드는 배포되되 **실행 불가** |
| 법률 검토 (로펌) | ⏳ 예약 대기 |
| 유사투자자문업 신고 | ⏳ 로펌 답변 이후 결정 |
| 개인정보처리방침 업데이트 | ⏳ Journal Companion 섹션 추가 필요 |
| 웨이팅 리스트 | ✅ `companion_waitlist` 테이블 + `POST /api/agent/waitlist` + `GET /api/admin/agent/waitlist` (P0-2, 2026-04-24) |
| Kill switch | ✅ `POST /api/admin/agent/kill` (admin 전용) |
| 테스트 | ✅ `tests/test_journal_companion_gate.py` 30 pass |
| 유저 노출 | ❌ 유저 0명 (flag 꺼짐) |

---

## 1. 기능 플래그 체계

### 1-1. 3 중 gate (코드 → 환경 → 테이블)

```
요청 진입
  │
  ▼
① 코드 배포 여부 (services/agents/ 존재)
  │
  ▼
② AGENT_ENABLED 환경변수 (Railway dashboard)
  │
  ▼
③ DB kill-switch 테이블 (settings.agent_kill_at)
  │
  ▼
④ 유저 entitlement (Premium Plus / Founding Lifetime)
  │
  ▼
⑤ Rate limit (20 초당 1회)
  │
  ▼
⑥ Legal gate (services/agents/legal_gate.py — 20 regex + 89 공용)
```

하나라도 실패하면 T5 refusal 반환. 각 거부는 감사 로그 남김.

### 1-2. 켜는 절차 (법적 승인 후)

1. `LEGAL_CONSULT_PACKAGE.md` Q7~Q11 **모두 green** 문서 보관.
2. 유사투자자문업 신고 완료 → 등록번호 확보.
3. 개인정보처리방침에 "Journal Companion 섹션" 추가 배포.
4. 약관에 "AI 면책 조항" 추가 배포.
5. Staging 에서 내부 7일 dogfood (CEO 계정만):
   ```
   railway variables set AGENT_ENABLED=1 --environment staging
   ```
6. Production 켜기:
   ```
   railway variables set AGENT_ENABLED=1
   ```
7. 엔드포인트 확인:
   ```
   curl https://pivoxquant.com/api/agent/status
   # {"enabled": true, "phase": "closed-beta", ...}
   ```
8. Founding 100명에 초대 이메일 발송.

### 1-3. 끄는 절차 (비상시)

순서대로, 가장 빠른 방법부터:

**A. DB Kill switch (5초 적용)**
```bash
curl -X POST https://pivoxquant.com/api/admin/agent/kill \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"reason": "사유 (감사 로그 기록)"}'
```

**B. 환경변수 토글 (1~2 분 재배포)**
```
railway variables set AGENT_ENABLED=0
```

**C. 엔드포인트 블록 (최후)**
Vercel 미들웨어에 `/api/agent/*` block. **5~10분 소요.**

어떤 방법을 썼든 반드시 `autopilot_log.md`에 기록.

---

## 2. 위험 신호 (Kill Criteria)

아래 중 하나라도 관측되면 **즉시 ①B 끄기**:

| 신호 | 탐지 방법 |
|---|---|
| "recommend / suggest / 추천 / 조언" 단어 유저 응답 누출 **1회** | `SELECT * FROM user_agent_audit WHERE gate_verdict='pass' AND (raw_output ILIKE '%recommend%' OR raw_output ILIKE '%추천%')` — legal_gate 뚫은 경우 |
| 금감원 / 공정위 / 개보위 1건 문의 접수 | 이메일/우편 |
| 유저 "이 AI가 나에게 매매 조언을 했다" 신고 | CS 채널 + SNS 모니터링 |
| gate `deny_advice_pattern` 비율 > 20% | 비정상 프롬프트 주입 시도 의심 |
| Claude API 응답 토큰 평균 > 1500 | 무한 루프 / 프롬프트 hijack 의심 |
| 유저당 일평균 요청 > 50 | 봇 또는 남용 |

---

## 3. 감사 로그 조회

### 3-1. 전체 요약
```
GET /api/admin/agent/stats
```
응답: 24h / 7d / 30d 요청 수, 거부율, 페르소나 분포.

### 3-2. 최근 거부 분석
```
GET /api/admin/agent/audit/recent?limit=50&verdict=deny_advice_pattern
```

### 3-3. 특정 유저 (개보위 요청 대응)
```sql
-- audit는 user_id만 저장, message는 sha256만 저장 (정본 미보관)
SELECT request_id, persona_code, gate_verdict, gate_reason,
       user_message_len, raw_output_len, generated_at
FROM user_agent_audit
WHERE user_id = $1
ORDER BY generated_at DESC
LIMIT 100;
```

### 3-4. 감사 로그 purge
2년 지난 행은 자동 삭제 (cron). 수동 trigger:
```
POST /api/admin/agent/purge-expired
```

---

## 4. 유저 문의 대응 스크립트

### Q. "이 AI는 뭐예요?"
> Personal Journal Companion은 당신이 남긴 투자 일지·IPS를 **기억**하고, 당신의 과거 거래 **패턴을 되비춰주고**, 당신 스스로 답할 **질문을 던지는** 도구입니다. 투자 자문·권유·추천을 제공하지 않으며, 자본시장법상 투자자문업이 아닙니다.

### Q. "이 AI가 매수/매도를 추천해줬어요."
> 1) 유저에게 화면/응답 ID 요청. 2) `request_id` 기반 감사 로그 확인. 3) 실제 누출이면 즉시 ①B 끄고 전수 조사 + 해당 유저에 사과 + 개보위/금감원 자진 신고 검토. 4) 오인이면 UI 면책 문구 강화.

### Q. "내 데이터 삭제해주세요."
> `POST /api/profile/delete-agent-memory`. 30일 내 backup 포함 전 삭제. `companion_waitlist`도 `CompanionWaitlist.purge_by_email(email)` 호출.

### Q. "Premium Plus 가 뭐예요?"
> Living CFO 4 layer 전체 접근 (Personal Journal Companion 포함). 월 49,900 원. Founding Lifetime 99,000 원 일시불은 선착순 200 석.

---

## 5. 법적 대응 FAQ (로펌·금감원)

### "이 기능이 투자자문업인가?"
→ `reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6` 전체 + **Q7 ~ Q11** 5개 질문에 대한 변호사 서면 답변 PDF 제출.

### 증거 자료 체크리스트
- [ ] `services/agents/prompts/companion_system.md` 전문
- [ ] `services/agents/legal_gate.py` 소스
- [ ] `tests/test_journal_companion_gate.py` 테스트 결과
- [ ] 임의 10 유저 샘플 응답 (pseudonymized)
- [ ] 거부(T5) 응답 로그 1000건 (deny_advice_pattern verdict)
- [ ] 약관 + 개인정보처리방침 + 매 화면 배너 스크린샷
- [ ] Kill switch 동작 증명 영상

### 금감원 자진 질의
로펌 조언 하에 출시 전 1회. 답변서 받으면 **면허 여부 확정 + 안전판**.

---

## 6. 아키텍처 요약 (Ops Reference)

```
유저 브라우저
   │ POST /api/agent/query { message }
   ▼
 Vercel → Railway (Flask)
   │
   ▼
 routes/agent.py · query()
   ├─ ① AGENT_ENABLED 체크    → 꺼짐 → 503
   ├─ ② Flask-Login 인증       → 실패 → 401
   ├─ ③ 엔타이틀먼트 검증      → 실패 → 403 (Premium Plus 필요)
   ├─ ④ Rate limit 20s/유저   → 실패 → 429
   └─ ⑤ _load_context(user)   ── pseudonymized
        │  journal_entries / ips / trade_proxy
        ▼
     services/agents/journal_companion.py · query()
        ├─ AGENT_ENABLED 재확인 (race 방지)
        ├─ persona 검증
        ├─ system prompt 읽기 (파일 디스크)
        │  + persona overlay (services/agents/prompts/persona/)
        ├─ Claude Haiku API 호출 (max_tokens=800, temp=0.3)
        ├─ legal_gate.run_gate(raw_output)
        │   ├─ 20 advice regex
        │   ├─ 89 공용 legal filter (services/legal_filter.py)
        │   └─ footer 필수
        ├─ gate.verdict == PASS → safe_output
        │   gate.verdict != PASS → T5_REFUSAL
        ├─ audit_logger.log_agent_request(...)
        │   (models/user_agent_audit.py)
        └─ return AgentResponse
   │
   ▼
 유저 브라우저 (chat-panel.tsx)
    rendered with per-message disclaimer band
```

---

## 7. 개인정보 방어선 (PIPA + GDPR)

| 원칙 | 구현 |
|---|---|
| Data Minimization | audit row에 `user_message_hash` (sha256)만 저장. 정본 없음 |
| Local-first | 유저 대화 이력 기본 **localStorage**. 서버 저장은 옵트인 (현 단계 미구현) |
| Pseudonymization | `user_id → sha256[:16]`, ticker 미전송, 금액 `bin` 처리 |
| Retention | audit 2년, waitlist 영구 (유저 삭제 요청 시 즉시) |
| Purpose Limitation | 마케팅 profiling / A/B target / 모델 학습 일절 금지 |
| 민감정보 분리 | 감정·심리 수집 안 함 (향후 추가 시 별도 동의 + 별도 테이블) |
| 삭제권 | `companion_waitlist.purge_by_email`, `user_agent_audit` 유저 삭제 시 동시 purge |
| 국외이전 | Claude API (Anthropic US) 경유 pseudonymized payload만. TIA 문서화 |

---

## 8. 배포 체크리스트

Journal Companion 을 production에 올리기 전 전부 ✅:

- [ ] 로펌 서면 답변 보관 (Q7~Q11 green)
- [ ] 유사투자자문업 신고 등록번호 확보
- [ ] 개인정보처리방침 업데이트 배포
- [ ] 약관 AI 면책 조항 배포
- [ ] `AGENT_ENABLED=1` staging 7일 dogfood 완료
- [ ] 테스트 전수 pass (`pytest tests/test_journal_companion_gate.py`, `test_agent_route.py`, `test_persona_adapter.py`)
- [ ] Kill switch 실제 동작 증명 (staging에서 한 번 눌러보고 복구)
- [ ] Admin 대시보드 팝업 확인 (audit 조회/stats/purge UI)
- [ ] 거부(T5) 응답 1000건 시뮬레이션 통과
- [ ] `pytest tests/test_no_hardcoded_samples.py` 로컬 실행 완료 (macOS — BSD grep 은 `-P` 미지원, pytest 가 유일한 로컬 방어선)
- [ ] CI legal-guard job green 확인 (GitHub Actions `Legal Guard / No hardcoded sample tickers or money in template defaults`)
- [ ] CEO 서명

체크리스트 한 칸이라도 비면 `AGENT_ENABLED=1` 금지.

---

## 8.5 웨이팅 리스트 운영 (P0-2, 2026-04-24)

### 8.5-1. 엔드포인트

| 엔드포인트 | 용도 | 인증 | Rate limit |
|---|---|---|---|
| `POST /api/agent/waitlist` | 공개 신청 (익명 랜딩 방문자 포함) | 불필요 (선택적) | 5 req / 1h / IP |
| `GET /api/admin/agent/waitlist?limit=500&source=...` | 관리자 조회 (FIFO) | `ADMIN_EMAILS` 매칭 | — |

### 8.5-2. 동작 원칙

- **AGENT_ENABLED / kill switch 무관** — 웨이팅 리스트는 Closed Beta 진입 funnel 자체이므로 killed 상태에서도 접수 받는다.
- **이메일 저장 정책**: `DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md §9.1` 준수. `email_hash` (sha256) 를 기본 식별자로, `email_plaintext` 는 폼 제출(=직접 통지 동의)이 있을 때만 저장.
- **Free-form 텍스트 금지**: `persona` 는 8 개 canonical persona 외 값은 drop, `source`/`referrer` 는 allowlist 외 값은 `"other"` 로 축소 — legal_gate bypass 방지.
- **Idempotent**: 같은 이메일을 두 번 POST 하면 201(queued) → 200(already-registered), DB 상 동일 행 유지.

### 8.5-3. 운영 절차

**매일 아침 9 KST**:
```bash
# 신규 신청 수 확인
curl -s -b cookies.txt https://pivoxquant.com/api/admin/agent/waitlist?limit=2000 \
  | jq '.total, (.rows | map(select(.invited_at == null)) | length)'
```

**Closed Beta 초대 발송 (주간, 금요일)**:
1. 위 GET 으로 `invited_at IS NULL` 행 수 확인.
2. Founding 100 한도 내에서 선착순으로 초대.
3. (수동, 로펌 승인 후 자동화) 각 초대 완료 시 해당 행의 `invited_at` 을 현재 UTC 시각으로 업데이트 (스키마에 반영된 `invited_at` 컬럼).

**유저 삭제 요청 수신 시**:
```python
# Python shell
from models.companion_waitlist import CompanionWaitlist
CompanionWaitlist.purge_by_email("user@example.com")  # returns 1 if deleted
```
— `DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md §9.3` 요구사항 충족 (즉시 삭제).

### 8.5-4. 모니터링 지표

- `INFO: agent.waitlist.enrolled` JSON 로그 (request_id, source, persona, position)
- `ERROR: agent.waitlist.store_failed` JSON 로그 — 발생 시 즉시 Sentry 알림 확인
- Admin GET 응답의 `total` 필드 — 주간 delta 를 Notion 주간 리포트에 기록

### 8.5-5. 테스트

`tests/test_agent_waitlist.py` 13 케이스 — CI pass 필수:
- 신규/중복/잘못된 이메일/누락/대소문자 dedup
- persona allowlist, referrer alias, AGENT_ENABLED=0 하에서도 접수
- 5/hour rate limit
- admin 401/403/200 ladder

---

## 9. 변경 이력

| 날짜 | 변경 | 담당 |
|---|---|---|
| 2026-04-23 | 초안 작성, Closed Beta 준비 | 배상현 |
| 2026-04-24 | §8.5 웨이팅 리스트 운영 추가 (P0-2, `/api/agent/waitlist` + admin 조회) | 배상현 |

---

**본 문서는 Companion 운영 단일 진실 공급원이다. 켜기 전 반드시 재확인.**
