# PivoxQuant 출시 D-day 체크리스트

> **목적**: 출시일까지 CEO가 직접 처리해야 하는 항목 + 자동화 검증 통과 항목 분리.
> **작성**: 2026-04-30 자율 세션 (Claude Opus 4.7)
> **인수인계**: HANDOVER.md v17 §외부 액션과 1:1 매핑.

---

## 🟢 자동 검증 통과 (출시 가능 상태)

| 항목 | 검증 결과 | 비고 |
|---|---|---|
| pytest 백엔드 | **1305 passed / 1 skipped / 0 failed** | F7 sub-score 테스트 3개 추가 후 |
| Production /api/health | 200 / db ok / 0.6s | Railway live |
| WeasyPrint native PDF | v68.1, 한글 + template render OK | diag endpoint 통과 |
| 17/17 PDF persona body 분기 | 112/112 unique HTML hash | 14 services × 8 personas |
| 32 production endpoints | 모두 정상 (200/302/401/405) | Auth gate 작동 |
| OAuth 302 redirect | Google + Kakao 둘 다 | redirect URI 등록은 별도 |
| Disclaimer 페이지 하단 고정 | 17 CSS 파일 패치 완료 | flex column + margin-top:auto |
| ruff lint | All checks passed | 변경된 14개 파일 |
| Beta gate | pivoxquant.com → /beta-gate | 정상 |

### V2 토글 출시 매트릭스 (D-1 결정 항목)

> **결정 룰**: 시각 회귀 캡처가 없으면 OFF로 권장 (CEO가 D-1 직접
> 클릭 검증 후 ON 승급). E2E는 현재 `frontend/e2e/smoke.spec.ts`만
> 존재하며 V2 페이지 dedicated coverage 없음.
>
> **Evidence 기준 (2026-05-07 시점)**:
> - 시각 회귀 SS: `test-results/e2e-2026-04-15-v2/` 디렉터리 — 1개
>   파일(`01-hero-after-gate.jpg`, 랜딩 hero) 외 V2 페이지 캡처 0개
> - E2E: `smoke.spec.ts`는 `/`, `/login` reachability만 테스트, V2
>   페이지별 검증 없음
> - 코드 default: `frontend/src/app/.../page.tsx` 첫 20줄 주석 + 3-way
>   `_v1`/`_v2` 라우팅 분기

| Flag | V2 LOC | 코드 default | 시각 회귀 SS | E2E | **출시 권장값** | 사유 |
|---|---:|:---:|:---:|:---:|:---:|---|
| `NEXT_PUBLIC_HOME_V2`      | 185 | **active** | ❌ | ❌ | **OFF** | 캡처 없음. CEO 검증 후 ON 승급 |
| `NEXT_PUBLIC_REPORTS_V2`   | 193 | **active** | ❌ | ❌ | **OFF** | 캡처 없음 |
| `NEXT_PUBLIC_PORTFOLIO_V2` | 366 | **active** | ❌ | ❌ | **OFF** | 캡처 없음 |
| `NEXT_PUBLIC_RISK_V2`      | 267 | **active** | ❌ | ❌ | **OFF** | 캡처 없음 |
| `NEXT_PUBLIC_SIGNALS_V2`   | 249 | **active** | ❌ | ❌ | **OFF** | 캡처 없음 |
| `NEXT_PUBLIC_SETTINGS_V2`  | 952 | V1 default | ❌ | ❌ | **OFF** | 코드 default와 일치 |
| `NEXT_PUBLIC_PROFILE_V2`   | 649 | V1 default | ❌ | ❌ | **OFF** | 코드 default와 일치 |
| `NEXT_PUBLIC_SIGNUP_V2`    | 531 | V1 default | ❌ | ❌ | **OFF** | 코드 default와 일치 |
| `NEXT_PUBLIC_LOGIN_V2`     | 239 | V1 default | ❌ | ❌ | **OFF** | 코드 default와 일치 |

> **⚠️ 코드 default vs 권장값 충돌 (5개)**: HOME / REPORTS / PORTFOLIO /
> RISK / SIGNALS는 코드상 V2 active default지만 캡처 없음 → 권장 OFF.
> 충돌 해소 옵션 2가지:
>
> 1. **Vercel env에서 명시적 OFF** (`NEXT_PUBLIC_*_V2=false` 5건 설정):
>    코드 변경 없이 즉시 적용. D-day 후 CEO 검증 + 캡처 추가 시 ON
>    승급. **권장 (출시 안전성 우선)**
> 2. **D-day 전 시각 회귀 캡처 5장 + smoke E2E 추가**: 1~2시간 작업.
>    시간 여유 있으면 이쪽 — 코드 default 유지 가능
>
> CEO 결정 항목.

---

## 🔴 즉시 (D-7 이전)

| # | 항목 | 어디서 | ETA |
|---|---|---|---|
| 1 | **Anthropic API credit 충전** | console.anthropic.com/settings/billing | 5분 |
| 2 | **GitHub Actions billing 한도 $5/월** | github.com/settings/billing/spending_limit | 5분 |
| 3 | **변호사 자문 (50~80만원)** | §101 면제 + 父 명의 사업자등록 리스크 | 1주 |
| 4 | **사업자등록 (본인 명의 권장)** | 홈택스 → 간이과세자 | 1일 |
| 5 | **통신판매업 신고** | 정부24 | 사업자등록 후 즉시 |

---

## 🟠 사업자등록 후 (D-3 ~ D-1)

| # | 항목 | 어디서 |
|---|---|---|
| 6 | Stripe 사업자 인증 | dashboard.stripe.com |
| 7 | Stripe 4종 키 발급 + Railway 등록 | `STRIPE_PUBLIC_KEY` / `_SECRET_KEY` / `_WEBHOOK_SECRET` / `_PRICE_ID_*` |
| 8 | Stripe 3-tier Product 생성 (Free / Pro 9,900 / Premium 19,900) | Stripe Products |
| 9 | Stripe Test → Live mode 전환 | 테스트 결제 1건 후 |
| 10 | Google Cloud Console OAuth redirect URI 등록 | `https://pivoxquant.com/api/auth/google/callback` |
| 11 | Kakao Developers OAuth redirect URI 등록 | `https://pivoxquant.com/api/auth/kakao/callback` |
| 12 | OAuth 동의화면 사업자정보 등재 | Google + Kakao |
| 13 | SendGrid Sender 이름 "StockPilot" → "PivoxQuant" | sendgrid.com Sender Authentication |
| 14 | 사업자 대표 이메일 활성화 | `contact@pivoxquant.com` 가비아 또는 Workspace |
| 15 | 이용약관 한국어 verbatim 작성 | `frontend/src/app/terms/page.tsx` |
| 16 | 개인정보처리방침 PIPA 준수 | `frontend/src/app/privacy/page.tsx` (CISO/책임자 정보 포함) |

---

## 🟡 시각·실 동작 검증 (D-1, CEO 직접 클릭 필요)

| # | 항목 | 어떻게 |
|---|---|---|
| 17 | 17/17 PDF v3 디자인 톤 | `open /tmp/pq_weasy/v2_*.pdf` (디스클레이머 하단 고정 적용본) |
| 18 | OAuth 실 로그인 → 콜백 → 세션 생성 | pivoxquant.com/login → Google → 대시보드 진입 |
| 19 | Watchlist 종목 추가 → 표시 | 검색 → 추가 → 새로고침 후 잔존 |
| 20 | Portfolio 매수/매도 모달 | Settings → Connect KIS → 매수/매도 입력 |
| 21 | Discover 종목 스캔 결과 | /discover 페이지 데이터 로딩 + 필터 |
| 22 | 알림벨 / 프로필 드롭다운 | 우상단 클릭 → 메뉴 노출 |
| 23 | 모바일 반응형 (62 페이지) | iPhone Safari + Android Chrome |
| 24 | 실 SendGrid 메일 도달 | 다음 cron 시점 (08:05 KST dd_checklist) 메일함 확인 |

---

## 🟢 출시 후 (D+1 ~ D+7)

| # | 항목 | 비고 |
|---|---|---|
| 25 | 베타 비밀번호 rotation 정책 | Railway env `BETA_PASSWORD`에서만 보유. 노출 시 즉시 폐기 |
| 26 | Sentry 알림 채널 (Slack/이메일) | sentry.io 프로젝트 설정 |
| 27 | Anthropic 잔액 자동 알림 | 임계치 이하 시 메일 |
| 28 | 도메인 SSL 자동 갱신 확인 | Vercel + Railway 둘 다 자동이지만 90일 만료 한 번 체크 |
| 29 | 첫 N명 베타 유저 피드백 수집 | 슬랙/디스코드 채널 또는 메일 |
| 30 | analytics 대시보드 (KPI 추적) | analytics_metrics.md 1/3/6개월 목표 |

---

## 🔒 알려진 미연동 / disabled (출시 영향 없음)

- **Alpaca DISABLED** (`ALPACA_ENABLED=0`) — 미국 broker-dealer 규제 회피. KIS read-only만.
- **Journal Companion DISABLED** (`AGENT_ENABLED=0`) — Closed Beta, 변호사 sign-off 전.
- **Stripe key 미연결** — 사업자등록 후 (#6~9).
- **Pretendard 폰트** — Production WeasyPrint diag 4회 시도. 현재 Variable font + lang=ko fontconfig 추가 (commit `f0cec05`). 빌드 결과는 다음 세션에 확인. **Noto CJK fallback 작동중이므로 한글 PDF 생성에는 영향 없음** — 디자인 톤만 차이.

---

## 자본시장법 §101 면제 트랙 (변호사 자문 항목)

> **WARNING**: 본 섹션은 일반 정리 자료. 정식 법률 자문 아님. 변호사 검토 필수.

### 핵심 요건 (요약)

자본시장법 §101 (유사투자자문업) 등록 면제 조건:
1. **개인 투자 정보 제공자에게 직접 자문 행위 부재** — 매수/매도/보유 권유 금지 (이미 코드에서 BUY/SELL/HOLD 라벨 0건으로 통과)
2. **불특정 다수 대상 정보 제공** — 가입한 모든 유저에게 동일 정보 제공 구조 (이미 PDF 7-tier 발송 구조)
3. **계약 형태로 자문 비용 수수 부재** — SaaS 구독료(₩9,900/19,900)는 정보 제공 대가지 자문 대가 아님 (이용약관에서 명시 필요)
4. **개별 주식의 매수·매도 시점·가격 권유 부재** — POSITIVE/NEGATIVE/NEUTRAL 라벨로 한정 (이미 통과)
5. **분기별·월별·일별 정보 발송이 일정한 형식** — 모든 유저에게 동일 템플릿 (이미 통과)

### 변호사 자문 시 물어볼 항목

1. 父 명의 사업자등록의 자본시장법 위반 가능성 (명의대여)
2. PivoxQuant SaaS 모델이 §101 면제 트랙에 정확히 부합하는지 검토
3. 17개 PDF 템플릿의 카피 레벨 검토 (legal_filter 89-regex 통과 후 재검증)
4. 이용약관 / 개인정보처리방침 한국어 verbatim 작성
5. 미래 등록(유사투자자문업) 시점 결정 (매출 1억 이상? 1만 유저 이상? 등)
6. 본인 명의로 시작 → 향후 법인 전환 시 명의 이전 절차

### 비용 / 일정

- 변호사 1차 자문: 50~80만원 (HANDOVER 외부 액션 #6 기록)
- 약관 작성 의뢰: 추가 30~50만원 (선택)
- 자본시장법 전문 변호사 (Kim & Chang, 법무법인 광장 등 펌) 또는 1인 변호사

---

## 출시 단계별 데모

### D-day Demo Plan (CEO가 시연 가능한 범위)

1. **랜딩 페이지** (베타 게이트 통과) → 가치 제안 + 3-tier 가격
2. **회원가입 → 온보딩 20문항** → 페르소나 결정 (8개 중 1개 자동)
3. **대시보드 진입** → 포트폴리오 / 시그널 / 마켓 / 디스커버
4. **Weekly Memo PDF 다운로드** → 페르소나에 따라 다른 톤·구도 (17개 PDF 중 1개 시연)
5. **AI 콘텐츠** (Anthropic credit 충전 후 활성화)

### 베타 → 정식 출시 전환

- ~~베타 비밀번호 게이트 제거~~ ✅ 2026-09-04 폐기 완료 (코드·env 삭제)
- Stripe live mode 활성화
- Sentry/모니터링 연결
- 첫 100 유저 피드백 1주일 수집 후 결정

---

## 인수인계

다음 세션 시작 시:

```
HANDOVER v17 (2026-04-30 자율 세션 종료) 읽고 이어서.
docs/LAUNCH_DDAY_CHECKLIST.md 도 같이 확인.

다음 우선순위:
1. /tmp/pq_weasy/v2_*.pdf 17개 시각 검증 (CEO)
2. Pretendard 4차 fix 결과 확인 (commit f0cec05 deploy 후 diag)
3. 변호사 자문 일정 (사업자등록 + §101 면제 + 父명의 리스크 검토)
4. Anthropic API credit + GitHub Actions billing limit
```

---

**END OF DOCUMENT**
