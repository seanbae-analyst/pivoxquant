# PivoxQuant — 인수인계서 (Handover)

> **작성일**: 2026-04-15
> **프로젝트**: PivoxQuant (디렉토리: `stockpilot`, 브랜드: `PivoxQuant`)
> **목적**: 다음 Claude 세션이 이 문서만 읽고 즉시 컨텍스트 복원 + 작업 재개

---

## 0. 30초 컨텍스트 복원

- **뭐하는 프로젝트**: 퀀트 기반 주식 분석 SaaS. Next.js 16 + Flask + Claude API + Alpaca(US) + KIS(KR)
- **상태**: 리브랜딩 완료 → Vercel 프론트 배포 완료 → **Railway 백엔드 배포 중 멈춤 (다음 세션 최우선 과제)**
- **도메인**: `pivoxquant.com` (구매 완료, DNS 전파 대기)
- **베타 게이트**: `https://pivoxquant.vercel.app` 비밀번호 = **`***REDACTED***`**
- **GitHub**: https://github.com/seanbae-analyst/pivoxquant
- **예산**: 266,696 / 1,000,000원 (26.7%), runway 18.3개월

---

## 1. 지금 당장 해야 할 것 (P0 — 다음 세션 첫 1시간)

### 1-1. Railway 백엔드 배포 (이번 세션 멈춘 지점)
```
1. railway.app 가입 → Trial $5 크레딧 (신용카드 필요)
   └─ 안 되면 Render 무료 tier 사용
2. New Project → Deploy from GitHub → seanbae-analyst/pivoxquant
3. Root Directory: / (루트, frontend/ 아님 — 백엔드는 루트에 있음)
4. Procfile 자동 감지: gunicorn app:app --worker-class gevent --workers 2 --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5 --log-level info
5. Variables → Raw Editor → /Users/seanbae/Desktop/취준/stockpilot/.env 붙여넣기 (60+개)
6. PostgreSQL 플러그인 추가 → DATABASE_URL 자동 주입됨
7. 배포 완료 후 Railway URL 복사 (예: pivoxquant-backend.up.railway.app)
```

### 1-2. Vercel에 백엔드 URL 연결
```
Vercel 대시보드 → pivoxquant 프로젝트 → Settings → Environment Variables
추가: NEXT_PUBLIC_API_URL = https://pivoxquant-backend.up.railway.app
→ Redeploy
```

### 1-3. pivoxquant.com 도메인 Vercel 연결
```
1. Vercel → Settings → Domains → Add Domain → pivoxquant.com
2. Vercel이 알려주는 DNS 레코드 복사
3. 가비아 로그인 → My가비아 → DNS 관리 → CNAME 또는 A 레코드 추가
4. 30분~2시간 대기 → https://pivoxquant.com 접속 확인
```

### 1-4. OAuth Redirect URI 프로덕션 등록 (CEO 직접)
```
Google Cloud Console:
  https://pivoxquant.com/api/auth/google/callback
  https://pivoxquant.vercel.app/api/auth/google/callback (fallback)

Kakao Developers:
  https://pivoxquant.com/api/auth/kakao/callback
  https://pivoxquant.vercel.app/api/auth/kakao/callback (fallback)
```

---

## 2. 이번 주 해야 할 것 (P1)

| # | 작업 | 누가 | 예상 시간 |
|---|------|------|-----------|
| 5 | Stripe 연결 (계정 생성 + API Key + Product/Price 매핑) | CEO + Claude | 2h |
| 6 | 본인 명의 간이과세자 등록 (홈택스, 무료) — **아빠 명의 절대 X** | CEO | 1일 |
| 7 | PWA 아이콘/로고/favicon 교체 (`frontend/public/icons/`, `logo-hero.jpeg`) | Claude | 30m |
| 8 | `/design-review` 실행 (도메인 + 백엔드 연결 후) | Claude | 1h |
| 9 | 친구들에게 베타 테스트 공유 (비밀번호 `***REDACTED***`) | CEO | - |
| 10 | 실제 유저 플로우 E2E 테스트 (로그인 → 온보딩 → 포트폴리오) | Claude + user-tester | 2h |

---

## 3. 다음 주 해야 할 것 (P2)

| # | 작업 | 상세 |
|---|------|------|
| 11 | 변호사 자문 (자본시장법 50~100만원) | "임팩트 스코어" 투자자문 해당 여부, 한국어 약관 검토 |
| 12 | 국가장학금 / 건강보험 피부양자 현 상태 확인 | 한국장학재단 + 건강보험공단 |
| 13 | PostgreSQL 마이그레이션 검증 | Railway 배포 후 SQLite → PG 데이터 이관 |
| 14 | Sentry 에러 로거 연결 | 프로덕션 에러 모니터링 |
| 15 | 모바일 반응형 전체 점검 | 전 페이지 iPhone/Android 뷰 |

---

## 4. 런칭 후 (P3)

15. Detail 페이지 7섹션 (펀더멘털/뉴스/캔들/배당/SWOT/경쟁사/백테스트)
16. 푸시 알림 UI 활성화 (PWA Notification + VAPID 키 발급)
17. 뉴스 임팩트 분석 기능 (변호사 자문 후 검토)
18. 국민연금 동행 지수 (DART 5%룰 공시 활용)

---

## 5. 이번 세션 (2026-04-15) 완료 요약

### 리브랜딩
- StockPilot → PivoxQuant (53개 파일 교체)
- 도메인 `pivoxquant.com` 구매 (가비아 19,800원/년)
- GitHub repo 이름 변경 + git remote URL 업데이트
- 베타 비밀번호 = `***REDACTED***`

### 퀀트 모델 100% 완성
- 미연결 7개 연결: DualMomentum, CorrelationRegime, DonchianBreakout, LedoitWolfShrinkage, ConditionalDrawdown, TailRatio, SortinoByPosition
- NOT_IMPLEMENTED 2개 구현: `current_ratio`, `interest_coverage` (FMP balance-sheet/income-statement)
- CAN SLIM 정확도 개선: C(분기 EPS YoY), A(3년 EPS), I(institutional ownership)
- `earnings_tone` 활성화 (Pro+ 전용 lazy load, 90일 캐시)

### 신규 기능 2개
- **타임머신** `/simulator/what-if` (베타 게이트 우회, 바이럴용)
  - `GET /api/simulate/counterfactual?ticker=X&start_date=Y&amount=Z&recurring=W`
  - 마일스톤 감지, SPY/KOSPI 벤치마크, URL 공유, Web Share API, print
- **아침브리핑** (매일 06:00 KST cron)
  - DB: `morning_briefs` 테이블 + Alembic migration 003
  - Claude Haiku insight + compliance regex
  - 홈 카드 + `/morning-brief` 아카이브 + Settings 알림 탭

### P2 안정화
- `error.tsx`, `global-error.tsx`, `loading.tsx` (스택 트레이스 노출 차단)
- 한국어 약관: `terms-ko.md`, `privacy-ko.md` (변호사 검토 필요)
- 랜딩 footer dead link 13개 정리
- "AI coaching" → "AI Assistant" 4곳 교체
- `kis_token_manager.py` (1분당 1회 제한 위반 해소)
- FMP 402 fallback (Alpaca 우선 + 30분 쿨다운)

### i18n 한/영
- `LocaleProvider` + `useT()` 훅
- `messages/ko.json` + `en.json` (200+ keys)
- Top-bar 🇰🇷/🇺🇸 토글

### 베타 비밀번호 게이트
- `middleware.ts` BETA_PASSWORD 체크
- `/beta-gate` 페이지 + `/api/beta-auth` 엔드포인트
- `/simulator/what-if`는 게이트 우회 (바이럴)

### KIS 실시간 인프라
- `kis_websocket_service.py` 신규 (밀리초 실시간 한국 주식 스트리밍)
- `KIS_USE_REAL=1` (실전 계좌 전환)
- 자동 재연결 + PINGPONG heartbeat

### P0 버그 4건 수정
- BUG-1 morningBrief URL 미스매치
- BUG-2 What-If flat shape destructure
- BUG-3 Events 필드명 통일
- BUG-4 Archive 응답 키 통일

### ESLint cleanup
- 4 errors → 0, 32 warnings → 0
- 22개 미사용 import 제거, useMemo/useCallback 의존성 4개 수정

### pytest 69개 추가
- `conftest.py` + 8개 테스트 파일
- 외부 API 모두 mock, 실제 `.env` 격리

### 배포 상태
- **Vercel 프론트 ✅ 성공** — `pivoxquant.vercel.app`
  - Root Directory: `frontend/`
  - `BETA_PASSWORD=***REDACTED***`
  - `NEXT_PUBLIC_SITE_URL=https://pivoxquant.com`
- **Railway 백엔드 ⏸️ 멈춤** — 다음 세션 재시도

### Git 커밋 7개 (푸시 완료)
```
4348522 feat: rebrand StockPilot to PivoxQuant + i18n
7c9a614 feat(quant): complete 7 unconnected models + CAN SLIM
56883ce feat: Time Machine + Morning Brief
42dde71 feat(ui): Portfolio + Risk + top-bar
cc96745 feat(realtime): KIS WebSocket + token manager + FMP fallback
d968924 feat: P2 stability + error boundaries + beta gate + pytest
088363d ci: GitHub Actions CI workflow
```

---

## 6. 재무 현황 (2026-04-15)

| 항목 | 금액 |
|------|------|
| **총 지출** | 266,696원 / 1,000,000원 (26.7%) |
| **남은 예산** | 733,304원 |
| **Runway** | 18.3개월 (유저 0명 기준) |
| **손익분기** | Pro 5명 또는 Premium 3명 |

### 신규 지출 (이번 세션)
- 가비아 도메인 `pivoxquant.com`: 19,800원 (1년)
- FMP API Starter: $29/월 (40,020원)

### 이미 결제 완료
- Claude Code Max: $149.91 (206,876원)
- 가비아 도메인 + FMP

### 미결제 (필요 시)
- Stripe: 수수료만, 가입 무료
- Vercel Hobby: 무료
- Railway Hobby: $5/월 (또는 Render 무료 tier)
- Google Workspace 이메일: $6/월

---

## 7. 중요 URL / 접속 정보

| 종류 | URL / 값 |
|------|----------|
| **GitHub Repo** | https://github.com/seanbae-analyst/pivoxquant |
| **Vercel 배포** | https://pivoxquant.vercel.app |
| **프로덕션 도메인** | https://pivoxquant.com (DNS 전파 중) |
| **로컬 프론트** | http://localhost:3000 |
| **로컬 백엔드** | http://localhost:5050 |
| **베타 비밀번호** | `***REDACTED***` |

### KIS 계좌
- 실전 계좌 (`KIS_USE_REAL=1`)
- 계좌번호: `XXXXXXXX-01` (read-only)

### Alpaca
- Paper Trading, ACTIVE
- 계정번호: `PA3BNKNKGLBD`
- 매수 가용: $188,415.64

---

## 8. 절대 하지 말 것 (Do Not)

- `engine.py`, `quant_models.py`, `autotrader.py`, `risk_defense.py` 직접 수정 금지
- 아빠 명의로 사업자등록 금지 (명의대여죄, 2년 이하 징역)
- UI에 "투자 추천", "매수", "매도" 단어 사용 금지 (자본시장법 위반)
- "AI Coach" 표현 금지 (→ "AI Assistant" 통일)
- `yfinance` 사용 금지 (Yahoo Finance ToS 위반, 상용 부적합)
- API URL 변경 금지 (`endpoints.ts` ↔ Flask routes 1:1 매핑)
- SWR 캐시 키 변경 금지

---

## 9. 알려진 이슈 (Known Issues)

| 이슈 | 상태 | 대응 |
|------|------|------|
| FMP 402 에러 | Starter 플랜 업그레이드 후에도 일부 엔드포인트 402 | Alpaca fallback + 30분 쿨다운 구현 완료 |
| KIS 토큰 1분 rate limit | 해결 | `kis_token_manager.py` 캐싱 구현 |
| Vercel "Flask" 자동 감지 | 해결 | Root Directory를 `frontend/`로 지정 |
| Railway 가입 시 신용카드 | 미해결 | 안 되면 Render 무료 tier 사용 |
| PostgreSQL 마이그레이션 | 미검증 | Railway 배포 후 SQLite→PG 이관 검증 필요 |

---

## 10. 비상 시 롤백

### Vercel 롤백
```
Vercel 대시보드 → Deployments → 이전 성공 배포 클릭 → "Promote to Production"
```

### Git 롤백 (프로덕션 사고 시)
```bash
cd /Users/seanbae/Desktop/취준/stockpilot
git log --oneline -10
git revert <문제 커밋 해시>
git push origin main
# Vercel 자동 재배포됨
```

### Railway 롤백
```
Railway 대시보드 → Deployments → 이전 배포 → "Redeploy"
```

### DB 롤백 (Alembic)
```bash
cd /Users/seanbae/Desktop/취준/stockpilot
alembic downgrade -1  # 1단계 되돌리기
alembic downgrade 002  # 특정 버전으로
```

---

## 11. CEO가 직접 해야 할 체크리스트

- [ ] Railway 가입 + 신용카드 등록 (Trial $5 크레딧)
- [ ] 가비아 DNS 레코드 추가 (pivoxquant.com → Vercel)
- [ ] Google Cloud Console OAuth redirect URI 추가 (프로덕션)
- [ ] Kakao Developers OAuth redirect URI 추가 (프로덕션)
- [ ] Stripe 계정 생성 + API Key 발급
- [ ] 홈택스 간이과세자 등록 (본인 명의, 무료, 1~3일)
- [ ] 국가장학금 / 건강보험 피부양자 상태 확인
- [ ] 변호사 자문 예약 (자본시장법 50~100만원)

---

## 12. 코드 위치 퀵 레퍼런스

### 프론트엔드 (Next.js 16)
- 루트: `/Users/seanbae/Desktop/취준/stockpilot/frontend/`
- 앱 라우트: `frontend/app/`
- 컴포넌트: `frontend/components/`
- API 클라이언트: `frontend/lib/endpoints.ts`
- 국제화: `frontend/messages/ko.json`, `en.json`
- 미들웨어: `frontend/middleware.ts` (베타 게이트)
- 베타 게이트 페이지: `frontend/app/beta-gate/page.tsx`
- 타임머신: `frontend/app/(dashboard)/simulator/what-if/page.tsx`

### 백엔드 (Flask)
- 루트: `/Users/seanbae/Desktop/취준/stockpilot/`
- 엔트리: `app.py`
- 라우트: `routes/` (quant, billing, auth, morning_brief, simulate 등)
- 퀀트 모델: `quant_models.py` (수정 금지)
- 엔진: `engine.py` (수정 금지)
- 오토트레이더: `autotrader.py` (수정 금지)
- 리스크: `risk_defense.py` (수정 금지)
- KIS 토큰: `kis_token_manager.py`
- KIS WebSocket: `kis_websocket_service.py`
- Alembic: `alembic/versions/003_morning_briefs.py`
- 테스트: `tests/` (conftest.py + 8개 파일, 69개 테스트)

### 환경변수
- 로컬: `/Users/seanbae/Desktop/취준/stockpilot/.env` (60+ 키)
- Vercel: 대시보드 Settings → Environment Variables
- Railway: 대시보드 Variables → Raw Editor

---

## 13. 빠른 명령어

```bash
# 로컬 백엔드 실행
cd /Users/seanbae/Desktop/취준/stockpilot
python app.py

# 로컬 프론트 실행
cd /Users/seanbae/Desktop/취준/stockpilot/frontend
npm run dev

# pytest 실행
cd /Users/seanbae/Desktop/취준/stockpilot
pytest

# ESLint 실행
cd /Users/seanbae/Desktop/취준/stockpilot/frontend
npm run lint

# 프로덕션 빌드 테스트
cd /Users/seanbae/Desktop/취준/stockpilot/frontend
npm run build

# Git 상태
cd /Users/seanbae/Desktop/취준/stockpilot
git status && git log --oneline -5
```

---

## 14. 다음 세션 오프닝 프롬프트 (추천)

```
형, 이어서 시작할게.

HANDOVER.md 읽고 현재 상태:
- Vercel 프론트 배포 ✅
- Railway 백엔드 배포 ⏸️ (최우선)
- 도메인 pivoxquant.com DNS 연결 대기
- 베타 비번: ***REDACTED***

P0 첫 작업: Railway 배포 재개 (또는 Render 대안).
시작 전에 railway.app 가입 했는지 확인 필요.
```

---

**작성**: 비서 (Chief of Staff)
**세션 종료**: 2026-04-15
**다음 세션 컨텍스트**: 이 문서 + `CLAUDE.md` + `PRODUCT_PLAN.md` 순서로 읽으면 100% 복원됨
