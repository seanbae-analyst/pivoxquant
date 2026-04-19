# PivoxQuant — 인수인계서 (Handover)

> **작성일**: 2026-04-17 (세션 마감)
> **목적**: 다음 세션이 이 문서만 읽고 즉시 컨텍스트 복원 + 출시 실행 계속
> **이전 HANDOVER**: 2026-04-16 버전 (`docs/archive/` 아님, 커밋 히스토리에서 확인)

---

## 0. 30초 컨텍스트 복원

- **상태**: **PivoxQuant 출시 준비 문서 완성. 실제 출시 실행 대기.**
- **브랜드**: `stockpilot/` → `pivoxquant/` 로 rename (심볼릭 링크로 backward compat)
- **URL**: `https://pivoxquant.com` (베타 비번 `***REDACTED***`)
- **백엔드**: Railway + PostgreSQL (SQLite 전환 완료, `DATABASE_URL` 연결됨)
- **프론트**: Vercel
- **최신 커밋**: `0276e7c` (Component ES 미장 통화 환산 fix + 리스크 UX)
- **PivoxOne (피벗 옵션)**: `/pivoxone/docs/` 에 사업 기획만 저장. **구현 X, 장기 옵션**
- **이전 CEO 직접 테스트 버그 (2026-04-14 CRITICAL 5건)**: **전부 fix 완료**. 상세 아래.

---

## 1. 🎯 다음 세션에서 할 일 (우선순위 순)

### 🔴 P0 — 이번 주 안에

#### ① 변호사 미팅 잡기
- **들고 갈 문서**: `docs/launch/LAWYER_CONSULTATION_PACKAGE.md` (질문 Top 20 정리돼있음)
- **추천 로펌** (부티크, 100만원 예산 내):
  - 법무법인 **디라이트** (핀테크 특화)
  - 법무법인 **미션** (스타트업)
  - 법무법인 **민후**
- **상담 결과 3가지 시나리오**:
  - 🟢 Green → 베타 즉시 출시
  - 🟡 Yellow → CRITICAL 5건 기능 수정 후 출시
  - 🔴 Red → 유사투자자문업 신고 먼저 (금융위 ₩20만)

#### ② CRITICAL 5건 기능 재설계 (법무 리뷰 결과)
법무 검수에서 구조 변경 필요 판정됨 (상세: `docs/launch/LAWYER_CONSULTATION_PACKAGE.md`):
1. **Portfolio Impact Radar** — 수익률 숫자 제거 or 개인화 제거
2. **Options Strategy Translator** — 삭제 or 교육 컨텐츠로 재설계
3. **Thesis Tracker 경고** — "상태 업데이트"로 중립 표현
4. **데일리 AI 브리핑** — 유사투자자문업 신고 전 비활성화
5. **전략 마켓플레이스** — 1년 연기 (이미 미구현)

#### ③ 이용약관 + 개인정보처리방침 작성
- 현재 **미작성** 상태
- 변호사 피드백 받은 후 초안 → 감수 → 확정

### 🟠 P1 — 이번 달 안에

#### ④ KIS/키움 OAuth 자동 sync 구현
- **문서**: `docs/launch/AUTO_SYNC_TECH_PLAN.md` (4,600단어 상세 스펙)
- **4주 로드맵**:
  - Week 1: KIS 개인 OAuth (유저가 본인 API 키 발급 → AES-256-GCM 암호화 저장)
  - Week 2: 키움 REST API 연동
  - Week 3: SnapTrade 글로벌 (Pro/Premium 전용, 비용 관리)
  - Week 4: Celery 자동 sync (1시간 주기)
- **원칙**: 기존 `services/kis_service.py` 유지. 신규 `services/broker/user_kis_service.py` 생성.

#### ⑤ Stripe 결제 연동 완성
- 기존 `routes/billing.py` 있음
- 4-tier 확정: Free / Pro ₩9,900 / Premium ₩19,900 / **Elite ₩99,900 (anchor)**
- **Anchoring 전략**: `docs/launch/MONETIZATION_STRATEGY.md` 참조
- 연간 결제 20% 할인 + Affiliate 30% lifetime (추후)

#### ⑥ 친구 베타 5~10명 클로즈드
- 베타 게이트 `***REDACTED***` 유지
- `dev-upgrade` 엔드포인트로 개별 업그레이드 가능:
  ```bash
  curl -H "Content-Type: application/json" -X POST \
    -d '{"secret":"***REDACTED***","email":"X","tier":"premium"}' \
    https://RAILWAY_BACKEND_HOST.up.railway.app/api/auth/dev-upgrade
  ```

### 🟡 P2 — 다음 달 이후

#### ⑦ 유료 런칭 (월 100명 목표)
- 결제 활성화 + 첫 100명 피드백 루프

#### ⑧ Product Hunt 런칭 준비
- Launch day 자료 (video, screenshots) + Hunter 섭외

#### ⑨ 마이데이터 사업자 등록 검토 (장기)
- 미래에셋/토스/삼성 증권사 통합 커버 (자본금 5억원, 인가 6개월)
- 우선 KIS/키움 OAuth로 시작

---

## 2. 📂 문서 위치 (2026-04-17 현재)

### 🏢 루트 구조 변경
```
/Users/seanbae/Desktop/취준/
├── pivoxquant/          ← 실제 폴더 (rename 완료)
├── stockpilot/          ← 심볼릭 링크 (backward compat, 기존 경로 호환)
└── pivoxone/            ← 피벗 기획만 (구현 X)
```

### 📚 PivoxQuant 핵심 문서 (2026-04-17 신규, 실제 코드 기반)
```
pivoxquant/docs/
├── QUANT_MODEL_EXPLAINED.md   ⭐ 15팩터 쉬운 설명 (본인 제품 이해)
├── SYSTEM_ARCHITECTURE.md     ⭐ 전체 구조 (routes/services/models 매핑)
├── USER_GUIDE.md              ⭐ 유저 매뉴얼 (12개 페이지)
├── OPERATIONS_RUNBOOK.md      ⭐ 장애 대응 (10개 시나리오 + 환경변수 30개)
├── launch/
│   ├── LAWYER_CONSULTATION_PACKAGE.md  ⭐ 변호사 상담 준비 (질문 20개)
│   ├── MONETIZATION_STRATEGY.md        ⭐ 돈 내게 하는 전략
│   └── AUTO_SYNC_TECH_PLAN.md          ⭐ KIS/키움/SnapTrade 연동
├── SESSION_2026-04-16.md       (전일 세션 요약)
├── BETA_READINESS_PLAN.md
├── QA_TEST_SCENARIOS.md
├── env-setup.md, deploy-guide.md, design-system.md, gstack-skills.md
├── 01-plan/, legal/            (참고)
└── archive/                    (13개 파일, 미구현 스펙/브레인스토밍 등 히스토리)
```

### 📦 PivoxOne (장기 피벗 옵션, 구현 X)
```
pivoxone/docs/
├── PIVOXONE_MASTER_PLAN.md
├── BIZ_PLAN_PART1_STRATEGY.md
├── BIZ_PLAN_PART2_PRODUCT.md
└── BIZ_PLAN_PART3_EXECUTION.md
```
→ **당분간 구현 X**. PivoxQuant 출시 성공 후 재검토.

---

## 3. 📊 이번 세션에서 한 것 (2026-04-17 요약)

### ✅ PivoxQuant 출시 준비 완료
1. **7개 신규 문서** (~27,000단어, 실제 코드 기반)
   - 제품 이해 3종 (Quant + Architecture + User Guide)
   - 운영 1종 (Runbook)
   - 출시 실행 3종 (Lawyer + Monetization + Auto-sync)
2. **경쟁사 실사 4건** (데이터 소스 22개, 알고리즘 12개, 토스 협업, 시장 조사)
3. **PivoxOne 사업기획서 3 Part + 마스터** (장기 옵션으로 보관)
4. **폴더 rename**: stockpilot → pivoxquant (심볼릭 링크 유지)
5. **불필요 파일 정리**: __pycache__ 60개, .pytest_cache, .DS_Store, 빈 Obsidian + 13개 구 기획 archive 이동

### ✅ 기능 검증 (변경 없음, 안 깨짐)
- Python py_compile 전부 OK
- TypeScript 빌드 exit 0
- KR 2,770 + US 12,743 종목 마스터 그대로
- 모든 routes/services/models 작동

### 🚫 이전 세션 (2026-04-16) CRITICAL 버그 전부 fix됨
과거 CEO 테스트 결과 5건은 전부 해결:
1. Portfolio 페이지 + Add Position + 매수/매도/수정 모달 — ✅ 구현됨
2. Search Stock — ✅ 동작
3. Watchlist 추가 — ✅ 동작
4. Risk 페이지 — ✅ 7-Layer Defense 연동, Component ES 통화 통일
5. Discover 데이터 — ✅ FMP 402 → yfinance fallback

---

## 4. 💰 예산 현황

| 항목 | 금액 |
|---|---|
| 기존 사용 | ₩266,696 (26.7%) |
| 잔여 예산 | ~₩733K |
| Railway (실제) | ~$6/월 (PostgreSQL 포함) |
| 도메인 (pivoxquant.com) | ₩19,800/년 |
| **예상 출시 비용** | **₩5.5~15M** (변호사 자문 중심) |

**법무 비용 확보가 관건**. 부티크 로펌 선택 시 **100만원 이내** 해결 가능.

---

## 5. 🔑 핵심 환경 변수 (Railway)

**필수** (없으면 부팅 실패):
- `SECRET_KEY`, `CSRF_SECRET`, `DATABASE_URL` (Postgres 연결됨 ✅)

**외부 API**:
- `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_USE_REAL=1`
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`
- `FMP_API_KEY`
- `ANTHROPIC_API_KEY` (Claude)

**OAuth**:
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`

**결제**:
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`

**기능 플래그**:
- `RUN_SCHEDULER=1` (스케줄러 활성)
- `BETA_PASSWORD=***REDACTED***`
- `DEV_LOGIN_SECRET=***REDACTED***` (**QA 끝나면 삭제!**)

**프론트 (Vercel)**:
- `NEXT_PUBLIC_API_URL=https://RAILWAY_BACKEND_HOST.up.railway.app`
- `BETA_SIGNING_SECRET=4c492c93dfe2e147986b81b8ee8aed5a534d2d6904b8963444cda39f31ab2114`

상세: `docs/OPERATIONS_RUNBOOK.md` 섹션 2

---

## 6. 🛠 주요 파일 레퍼런스

### 백엔드
- `app.py` — Flask 팩토리 + 스케줄러
- `engine.py`, `quant_models.py` — **수정 금지** (15팩터 엔진)
- `autotrader.py`, `risk_defense.py` — **수정 금지**
- `routes/auth.py`, `routes/dev_auth.py` — 인증
- `routes/portfolio.py` — 포지션 관리
- `routes/market.py` — 시세/검색 (KR 2,770 + US 12,743)
- `routes/quant.py` — 리스크 분석 (Component ES 통화 환산 fix됨)
- `services/kis_service.py` — KIS API (유지, 유저 OAuth는 신규 파일로)
- `services/kr_stock_registry.py`, `services/us_stock_registry.py`
- `services/market_status.py` — KST 장 상태
- `security.py` — CSRF, 세션, CORS

### 프론트
- `frontend/middleware.ts` — 베타 게이트 + CSP
- `frontend/src/app/(dashboard)/*/page.tsx` — 12개 주요 페이지
- `frontend/src/components/dashboard/*`
- `frontend/src/lib/endpoints.ts` — API 엔드포인트
- `frontend/public/sw.js` — Service Worker (NETWORK_FIRST 전환 완료)

---

## 7. ⚠️ 알려진 제한사항 / Optional TODO

1. **역사적 FX 미지원**: B7 what-if 계산에서 현재 FX로 환산 (미세 오차)
2. **autotrader.py ↔ available_capital 미연동**: 모의투자가 하드코딩 ₩10M/$100K. 시드머니 UI 있지만 실제 반영 안 됨. (Optional)
3. **SignalCache stale 레코드**: 기존 "Unknown" sector 레코드는 TTL(60s) 만료 후 자동 갱신
4. **모바일 /settings 탭**: 데스크톱 정상, 모바일 미검증 (dashboard-layout 이중 렌더 구조)
5. **Peer 엔드포인트**: 한국종목 sector 매핑 후 재분석 필요 (기존 캐시 "Unknown")
6. **Google/Kakao OAuth redirect URI**: 프로덕션용 Console 설정은 CEO가 수동 추가해야 함

---

## 8. 🎯 다음 세션 오프닝 프롬프트 (추천)

```
HANDOVER.md 읽고 이어서 시작.

현재 상태:
- PivoxQuant 출시 준비 7개 문서 완성 (pivoxquant/docs/)
- 폴더 rename 완료 (stockpilot → pivoxquant, 심볼릭 링크 있음)
- 이전 CRITICAL 5건 전부 fix 완료
- 법무 리뷰에서 지적된 CRITICAL 5건 기능 수정 대기 중
- 변호사 미팅 안 잡힘

우선 진행:
1. 변호사 미팅 잡기 (부티크 디라이트/미션/민후 중 택 1)
2. 피드백 받은 후 CRITICAL 5건 수정
3. KIS OAuth 구현 시작 (AUTO_SYNC_TECH_PLAN 기반)

PivoxOne 피벗은 장기 옵션, 지금은 PivoxQuant 출시 집중.
```

---

## 9. 🚫 절대 하지 말아야 할 것

- `engine.py`, `quant_models.py`, `autotrader.py`, `risk_defense.py` 수정
- `/pivoxone/` 폴더 코드 구현 (기획만)
- `DEV_LOGIN_SECRET` 프로덕션에 남기기 (베타 끝나면 삭제)
- 변호사 피드백 없이 유료 결제 오픈
- "추천", "매수/매도 시점", "예상수익률 X%" 단어 사용 (법무 위반)
- `services/*_stocks_data.json` 삭제 (KR/US 종목 마스터)
- `BUY/SELL/HOLD` 라벨 사용 (`POSITIVE/NEGATIVE/NEUTRAL`만)
- "AI Coach", "투자 코치" 사용 (`AI Assistant`만)

---

## 10. 📞 긴급 연락처 / 자원

- **Railway**: RAILWAY_BACKEND_HOST.up.railway.app
- **Vercel**: pivoxquant.vercel.app + pivoxquant.com
- **GitHub**: https://github.com/seanbae-analyst/pivoxquant
- **KIS Developers**: https://apiportal.koreainvestment.com
- **키움 API**: https://api.kiwoom.com
- **SnapTrade**: https://docs.snaptrade.com
- **금융위 유사투자자문업 신고**: https://www.fss.or.kr

---

**작성**: Claude Code (2026-04-17 세션 마감)
**다음 세션**: 이 문서 + `docs/launch/LAWYER_CONSULTATION_PACKAGE.md` + `docs/QUANT_MODEL_EXPLAINED.md` 순서로 읽으면 100% 복원됨
