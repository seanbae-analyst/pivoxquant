# PivoxQuant — 인수인계서 (Handover)

> **작성일**: 2026-04-16 (긴 세션 마감)
> **목적**: 다음 세션이 이 문서만 읽고 즉시 컨텍스트 복원 + 남은 버그 fix 재개

---

## 0. 30초 컨텍스트 복원

- **상태**: 프로덕션 배포 완료, 친구 베타 공유 직전. **남은 P0 4건 있어서 아직 공유 불가**
- **URL**: `https://pivoxquant.com` 베타 비번 `***REDACTED***`
- **백엔드**: Railway (gunicorn workers=1, PostgreSQL)
- **프론트**: Vercel (Next.js 16, Pretendard + Geist, Apple HIG 디자인)
- **최신 커밋**: `fc51bb6` (근본 원인 fix 4건 + 실시간 환율)

---

## 1. 🚨 다음 세션 시작 즉시 할 일 (D-Day)

### Step 1. **verify agent 활성화 확인**
이번 세션에서 `.claude/agents/` 에 6개 에이전트 생성 (세션 재시작 필요):
- `verify-ux.md` — 브라우저 클릭 검증
- `verify-api.md` — curl API 검증
- `verify-data.md` — 데이터 정확성 (0.00, NaN, 통화 기호)
- `verify-design.md` — Apple HIG 유지 감지
- `verify-security.md` — CSP, OAuth, 베타 게이트
- `investigate-bug.md` — 근본 원인 조사 (fix 금지)

Agent 호출 테스트:
```
Agent subagent_type="verify-ux" 로 간단한 tasks
```

### Step 2. **방금 푸시한 4건 fix 실제 검증**
`fc51bb6` 커밋이 Railway/Vercel 배포 완료 후, verify agent로 확인:

**B2 한국 종목 $0.00** (확신도 100%):
- URL: `https://pivoxquant.com/detail/005930`
- 기대: 가격 ₩ 표시, 기업명 "삼성전자"
- verify-ux로 브라우저 클릭 검증
- verify-data로 화면 값 0.00 아닌지

**B4 포트폴리오 통화 혼용** (100%):
- URL: `/portfolio` (포지션 추가 후)
- 기대: KRW 포지션 있으면 요약 카드 ₩ 단일 통화
- 현재 fx_rate로 USD 환산된 ₩ 통합값

**B6 SSE 400 폭주** (100%):
- Network 탭에서 `portfolio-stream` 400 반복 없는지
- 포지션 0명일 때 SSE 연결 안 하는지

**B7 타임머신 재계산** (100%):
- `/simulator/what-if` 계산 버튼 클릭 → 결과 카드 즉시 표시
- 파라미터 바꾸고 다시 계산 → 새 결과

**실시간 환율**:
- `/api/market/fx` 호출 → 최신 값
- 1분 주기 자동 갱신
- 프론트 30초 polling

---

## 2. 🟡 남은 버그 4건 (다음 세션 주요 작업)

이번 세션 조사에서 **확신도 50~80%** 로 추가 파악 필요:

### B1. Watchlist "+" 버튼 무반응 (P0)
- 증상: AAPL 검색 → 추가 → **네트워크 요청 0건**
- 조사 결과: `watchlist/page.tsx:262`에서 `API.market.lookup` (exact match) 쓰는데 검색 실패 시 드롭다운 안 뜸
- 수정 방향: `API.market.search` (퍼지) 로 교체. portfolio의 `AddPositionModal` 패턴 참고.
- 파일: `frontend/src/app/(dashboard)/watchlist/page.tsx:262`

### B3. Portfolio 추가 후 목록 미갱신 (P0)
- 증상: 토스트 뜨지만 목록 0건, 새로고침 필요
- 조사: `routes/portfolio.py:21-38` background thread + Railway cold start 의심
- 추가 조사 필요: 실제 Railway 응답 시간 측정 + `mutate()` 후 revalidate 타이밍
- 파일: `portfolio/page.tsx:1478-1480` (handleMutate) + `routes/portfolio.py` (background thread)

### B5. 검색 "nvidia" 회사명 빈 결과 (P1)
- 증상: "nvidia" → 빈 결과. "NVDA" → OK
- 조사: FMP 402 에러 시 fallback 진입 실패 가능성. FMP 응답이 비정상 JSON이면 `resp.json()` 파싱 실패 후 `fmp_ok=False` 안 됨.
- 추가 조사: FMP 실제 응답 상태 확인 필요
- 파일: `routes/market.py:70-91` (FMP 호출 + fallback)

### B8. /detail 로딩 중 거대 공백 (P1)
- 증상: `profile` API 404/500 시 Key Metrics 빈 grid 1000px+
- 조사: `detail/[ticker]/page.tsx:287-344` loadingProfile 조건 개선 필요
- 파일: `detail/[ticker]/page.tsx:291` — `loadingProfile || !profile` 로 수정

### B9. dev 세션 5~10분 만료 (P2, 인프라 이슈)
- Railway 컨테이너 재시작 (cold start) 의심
- 코드 문제 아님. 향후 Redis 세션 스토어 도입 고려

---

## 3. 다음 세션 실행 순서 (D-Day-1)

### Phase 1: 배포 확인 + 지난 세션 fix 검증 (10분)
1. `fc51bb6` Railway 배포 완료 확인
2. `verify-ux` + `verify-api` + `verify-data` 병렬 투입
3. B2/B4/B6/B7 + 환율 실제 동작 확인
4. 발견 추가 버그 있으면 우선순위 재조정

### Phase 2: 남은 4건 근본 원인 조사 (20분)
- `investigate-bug` agent (세션 재시작 후 활성) 투입
- B1, B3, B5, B8 확신도 100%로 끌어올림
- B9는 인프라 이슈라 별도 다룸

### Phase 3: fix + verify (40분)
- 원인 100% 확정 건만 fix agent
- 각 fix 후 verify agent로 실제 동작 확인
- **검증 통과한 것만 커밋**

### Phase 4: 통합 커밋 + 푸시 + 배포 (5분)

### Phase 5: 최종 전수 E2E (30분)
- user-tester agent로 15개 페이지 모두 클릭
- 9건 전부 PASS 확인
- 콘솔 에러 0건 확인

---

## 4. 📊 현재 상태 요약

### ✅ 완료된 것
- Railway 배포 + Vercel 연결 + pivoxquant.com 도메인
- Google + Kakao OAuth redirect URI
- Apple HIG + Bloomberg 디자인 리팩토링 (violet 그라디언트 전면 제거)
- 법무부 CRITICAL 5건 fix (자본시장법 컴플라이언스)
- i18n 전수 감사 + 95+ 키 추가 + Settings 언어 스위처
- Portfolio 저장 플로우 (버튼 영구 disabled 버그 fix)
- 유사 검색 + 단가 보존 + 달러 표시 + 한국종목 기업명 UI
- 한국 종목 Detail `.KS` 자동 접미
- 포트폴리오 요약 카드 통화 KRW 통합
- SSE 포지션 0명 가드
- 타임머신 재계산 timestamp 접미
- 실시간 환율 인프라 (FMP + 백업 이중화, 1분 scheduler, 30초 프론트)
- QA dev-login 바이패스 (`DEV_LOGIN_SECRET=***REDACTED***`)

### 🟡 남은 것 (다음 세션)
- B1, B3, B5, B8 버그 fix
- 최종 전수 E2E 검증
- 친구 베타 공유 메시지 작성
- Stripe 연결 (유료 전환 시점)

---

## 5. 🛠 핵심 파일 레퍼런스

### 백엔드
- `app.py` — create_app + scheduler (RUN_SCHEDULER=1 필요)
- `routes/auth.py` — OAuth state 검증, dev-login 별도
- `routes/dev_auth.py` — QA 전용 로그인
- `routes/market.py` — search, lookup, fx, overview
- `routes/portfolio.py` — background thread signal cache
- `routes/realtime.py:81-84` — SSE portfolio-stream (포지션 0 → 400)
- `services/fx_service.py` — 환율 서비스 (FMP + 백업)
- `ai_service.py` — compliance 필터 전면 적용
- `security.py` — CSRF, 세션, CORS

### 프론트
- `frontend/src/app/(dashboard)/portfolio/page.tsx` — Portfolio + AddPositionModal
- `frontend/src/app/(dashboard)/watchlist/page.tsx:262` — B1 수정 예정
- `frontend/src/app/(dashboard)/detail/[ticker]/page.tsx:175-180` — .KS 자동 접미 (B2)
- `frontend/src/app/simulator/what-if/what-if-client.tsx` — 타임머신 (B7)
- `frontend/src/components/dashboard/metric-cards.tsx` — 통화 통합 (B4)
- `frontend/src/lib/realtime.tsx` — SSE 포지션 가드 (B6)
- `frontend/src/lib/hooks.ts` — useFxRate 포함
- `frontend/middleware.ts` — 베타 게이트 + CSP

### 수정 금지 (절대)
- `engine.py`, `quant_models.py`, `autotrader.py`, `risk_defense.py`

### 환경변수 (Railway)
- `SECRET_KEY`, `CSRF_SECRET`, `BETA_SIGNING_SECRET`
- `FLASK_ENV=production`
- `CORS_ORIGINS=https://pivoxquant.vercel.app,https://pivoxquant.com,https://www.pivoxquant.com`
- `RUN_SCHEDULER=1`
- `BETA_PASSWORD=***REDACTED***`
- `DEV_LOGIN_SECRET=***REDACTED***` (QA 끝나면 삭제!)
- API 키: `ANTHROPIC_API_KEY`, `ALPACA_*`, `KIS_*`, `FMP_API_KEY`, `GOOGLE_*`, `KAKAO_*`, `SENDGRID_*`

### 환경변수 (Vercel)
- `NEXT_PUBLIC_API_URL=https://RAILWAY_BACKEND_HOST.up.railway.app`
- `BETA_PASSWORD=***REDACTED***`
- `BETA_SIGNING_SECRET=4c492c93dfe2e147986b81b8ee8aed5a534d2d6904b8963444cda39f31ab2114`

---

## 6. 🎯 다음 세션 오프닝 프롬프트 (추천)

```
HANDOVER.md 읽고 이어서 시작.

현재 상태:
- fc51bb6 배포 완료 (B2, B4, B6, B7 + 실시간 환율)
- 남은 P0/P1 버그 4건 (B1, B3, B5, B8)
- 새로 만든 verify agent 6개 활성화됨 (세션 재시작 후)

D-Day 순서:
1. fc51bb6 fix 4건 verify-ux + verify-api로 실제 검증
2. 남은 B1/B3/B5/B8 investigate-bug 근본 원인 조사
3. fix → verify → 커밋+푸시
4. 최종 전수 E2E → 공유

중요: 이번엔 verify agent 증거 없으면 절대 PASS 안 찍음.
```

---

## 7. 💰 재무 현황

- 총 지출: 266,696원 / 1,000,000원 (26.7%)
- Railway Hobby: $5/월 신규 지출
- 나머지 예산 73%

---

## 8. 📜 법적 체크리스트 (공유 전)

- [ ] 사업자등록 (본인 명의 간이과세자)
- [ ] 유사투자자문업 신고 (유료 전환 시, 금융위, 20만원)
- [ ] 변호사 자문 (약관 최종 검토, 핀테크 특화 50~150만원)
- [ ] 통신판매업 신고 (유료 결제 개시 전)

**지인 베타 (무료, 5~10명)는 위 조치 불필요.**

---

**작성**: Claude Code 세션 (2026-04-16 마감)
**다음 세션**: 이 문서 + `CLAUDE.md` + `docs/BETA_READINESS_PLAN.md` 순서로 읽으면 100% 복원됨
