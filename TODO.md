# PivoxQuant — 해야할 일 체크리스트 (2026-04-23 기준)

**세션 종료 v6 · commit `7f411b3` · 최신 반영**

상세 근거: `HANDOVER.md` §3 미완 항목 / §5 우선순위 / §3-F CEO 외부 / §6 Dashboard Terminal 명세.

---

## 🔴 P0 — 즉시 (법적/데이터 무결성 리스크)

### CEO 외부 (너만 가능, 1분~하루)
- [ ] **`.env` 파일 권한 변경** (1분)
  ```bash
  chmod 600 /Users/seanbae/Desktop/취준/stockpilot/.env
  ```
  근거: HANDOVER §3-B. 실 운영 키(Anthropic/KIS 실계좌/Google/Kakao) 유출 방지.

- [ ] **로펌 예약** (이번 주)
  - 지참: `LEGAL_CONSULT_PACKAGE.md` + `reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md` + DRAFT_* 3건 + Q1~Q20
  - 추천: 세움 / 한별 / 디라이트 / Kim&Chang
  - 비용: 150~300만원
  - 핵심 질문: Journal Companion 이 투자자문업인가 (Q7~Q11) / PIPA 방어선 (Q13~Q20)

- [ ] **상표 출원** (30분 × 2건, 총 62,000원 × 2 = 124,000원)
  1. 키프리스 http://www.kipris.or.kr → "PivoxQuant" 유사상표 검색
  2. 유사 없으면 특허로 https://www.patent.go.kr 온라인 출원
  3. "Pre-Trade Checklist" 도 별도 출원 권고

### 개발부 (나, 다음 세션 즉시)

- [ ] **Template systematic sanitize** (30~60분)
  - 근거: HANDOVER §3-A. `dd_checklist.html`에 AAPL 하드코딩, `brag_card.html`에 NVDA 하드코딩, 유저는 자기 보유 안 한 종목 데이터 수신
  - Step 1: A/B/C 등급 17건 전수 치환
    ```bash
    # 위험 등급 A/B/C 매치 regex
    grep -rn "default('[A-Z]{2,6}')" services/artifacts/templates/
    grep -rn "default('\\\$[0-9]" services/artifacts/templates/
    grep -rn "default('(Q[1-4]|January|April|...)" services/artifacts/templates/
    ```
    전부 `default(none)` 으로 치환
  - Step 2: Jinja `{% if field %}...{% endif %}` 섹션 래핑
    - `dd_checklist.html` Part II/III/IV 재무 섹션 (L 382, 740, 794 근방)
    - `earnings_prebrief.html` 제목·footer·L407 ticker
    - `brag_card.html` + `brag_card_email.html` 전체 (최악의 경우 AGENT_ENABLED=0 같은 feature flag 로 Closed Beta 처리)
  - Step 3: `.github/workflows/legal-guard.yml` 에 regex 추가
    ```yaml
    - name: Block hardcoded ticker/currency samples
      run: |
        ! grep -rnE "default\('[A-Z]{2,6}'\)|default\('\\\$[0-9]" services/artifacts/templates/
    ```
  - Step 4: `tests/test_no_hardcoded_samples.py` 신규 (pytest 이중 방어)
  - Step 5: 전수 pytest 회귀 (267/267 유지)

- [ ] **`/api/agent/waitlist` endpoint 추가** (1시간)
  - 근거: HANDOVER §3-D #2. frontend `companion-teaser.tsx`/`/companion` 페이지가 POST 하는데 endpoint 없음 (404/501 silent). 유저 이메일 수집 0.
  - Step 1: `models/companion_waitlist.py` 이미 있음 (`CompanionWaitlist.enroll()` 메서드 사용)
  - Step 2: `routes/agent.py` 에 추가:
    ```python
    @agent_bp.route("/waitlist", methods=["POST"])
    def waitlist() -> Any:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"error": "invalid-email"}), 400
        consent = bool(data.get("consent_direct_email"))
        source = (data.get("source") or "landing-teaser")
        CompanionWaitlist.enroll(
            email=email,
            consent_direct_email=consent,
            source=source,
        )
        return jsonify({"ok": True, "queued": True})
    ```
  - Step 3: `tests/test_agent_route.py` 에 waitlist 테스트 추가
  - Step 4: Frontend `useCompanion.ts` fallback 제거 (지금은 404 일 때 fake "성공" 처리)

---

## 🟠 P1 — 다음 세션 (CEO 피드백 대응)

### 개발부 (나)

- [ ] **Dashboard "Terminal" Phase 1 — Bloomberg 톤 전환** (2~3시간)
  - 근거: HANDOVER §3-C + §6. CEO "싼마이 종이 컨셉" 피드백 미대응 상태.
  - 설치:
    ```bash
    cd frontend && npm i lightweight-charts
    ```
  - 신규 5 컴포넌트:
    1. `frontend/src/components/terminal/top-ticker.tsx` — 상단 live bar (KST + USD/KRW + VIX + 주요 지수, tick-flash)
    2. `frontend/src/components/terminal/kpi-card.tsx` — dense KPI with 0.3s green/red flash
    3. `frontend/src/components/terminal/data-table.tsx` — sortable + sticky header + J/K keyboard nav
    4. `frontend/src/components/terminal/candlestick-chart.tsx` — `lightweight-charts` TradingView wrapper
    5. `frontend/src/components/terminal/command-palette.tsx` — Cmd+K (fuzzy search 페이지/종목/액션)
  - `/home` 페이지 재배치:
    ```
    top-ticker → Brief│Snapshot│Risk → Positions│Watchlist → Chart → Signals│Pulse → Companion│Feedback
    ```
  - 유지: `/reports` 는 **Dossier 종이 컨셉 유지** (PDF 카탈로그엔 종이 메타포 맞음)
  - Out-of-scope (Phase 2): `/portfolio` / `/market` / `/signals` / `/risk` / `/watchlist` paper 교체

- [ ] **Engine 40-model drawer migration** (2시간)
  - 근거: HANDOVER §3-D #5. `/features/engine` 에 legacy 인터랙티브 drawer 미이식 (현재 요약만)
  - 대상 파일: `frontend/src/components/landing/landing-page.tsx` (orphaned, 3927 line) 안에 Engine drawer 구현 있음
  - 이식처: `frontend/src/app/features/engine/page.tsx`

- [ ] **Sample Reports flip-deck migration** (1~2시간)
  - 동일 패턴. `/features/reports` 6-card grid → legacy flip-deck 이식

- [ ] **CountUp V2 wire** (15분)
  - `count-up.tsx` 이미 존재 (이미 이번 세션에 today-hero 에서 사용)
  - `/` 랜딩 Hero (CAGR 21.19%, Sharpe 0.94) + Pricing 카운터 (Founding 200석) 에 연결

- [ ] **Legacy `landing-page.tsx` 삭제** (1분)
  - orphaned 3927 line. 아무도 import 안 함 (grep 검증 완료)
  - `git rm frontend/src/components/landing/landing-page.tsx`

### CEO 외부

- [ ] **Stripe Product 등록** (Stripe Dashboard 수동, 30분)
  - Pro 14,900 / Premium 29,900 / Premium Plus 49,900 / Founding Lifetime 99,000 (선착순 200석)
  - Webhook endpoint: `https://RAILWAY_BACKEND_HOST.up.railway.app/api/billing/webhook`
  - 후속 Railway env:
    ```
    STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
    STRIPE_PRICE_PRO, STRIPE_PRICE_PREMIUM, STRIPE_PRICE_PREMIUM_PLUS, STRIPE_PRICE_LIFETIME
    ```

- [ ] **사업자등록** (홈택스, 15분)
  - 업종코드: 642001 (데이터 처리·호스팅) + 642902 (응용 SW)
  - 상호: PivoxQuant 또는 개인
  - 수수료: 무료

- [ ] **통신판매업 신고** (정부24, 20분, 40,000원)

---

## 🟡 P2 — 2주 내

### 개발부

- [ ] **Chrome MCP 활성화 후 E2E 12-Track** — HANDOVER §3-D #1
- [ ] **Lighthouse 재측정** (Hero v4 cinematic 이후 perf 베이스라인)
- [ ] **dd_checklist 서비스 주입 로직** — Phase 2 실계산 데이터 주입 (종목별 FMP fundamentals + 업종 P/E)
- [ ] **Sample 라벨 시스템** — D 등급 퍼센트/카운트 하드코딩을 "sample" 배지 + 엔타이틀먼트 조건부로
- [ ] **legal-guard.yml 확장** — features/ 페이지 DisclaimerBanner 검사, persona partials regex

### 보안부

- [ ] **`dev_auth.py` FLASK_ENV=production 가드** (스테이징 전용 강화)
- [ ] **Kakao placeholder email collision fix** (`routes/auth.py:556-558`)
- [ ] **CSP `unsafe-inline` 제거** (Next.js nonce propagation, `frontend/middleware.ts:161-178`)
- [ ] **legal_gate Unicode apostrophe 정규화** — `unicodedata.normalize('NFKC', ...)` before regex
- [ ] **Dependabot 추가** (`.github/dependabot.yml` 주 1회 pip + npm)
- [ ] **`anthropic==X.Y.Z` 버전 pin** + `requirements.lock`

### CEO 외부

- [ ] **유사투자자문업 신고** (로펌 Q9 답변 후, 수리 2~4주)
- [ ] **이용약관 + 개인정보처리방침 정식 배포** (로펌 반영 후 `frontend/src/app/terms/` + `privacy/` 업데이트)

---

## 🟢 P3 — Launch 준비 (한 달 내)

- [ ] **Internal Beta dogfood** — Journal Companion staging 7일 (CEO 본인만, AGENT_ENABLED=1)
- [ ] **Founding Lifetime 100~200명 모집** — 로펌 + 상표 + 유사투자자문업 완료 후
- [ ] **Field mapping 52% quick win** — 3 shared vars (issue_number/doc_ref/hero_headline) mixin (Field mapping audit 발견, 42 ORPHAN 한 번에 해소)
- [ ] **Dashboard Terminal Phase 2** — portfolio/market/signals/risk 페이지 paper → terminal
- [ ] **i18n 한글 랜딩** (선택)
- [ ] **Web Push VAPID 발급 + 실 발송**
- [ ] **Sentry 연결 실 에러 수집**

---

## 🔵 운영 체크리스트 (지속 관리)

### 매 배포 전
- [ ] `git diff origin/main --name-only | xargs grep -E "sk-ant-|PKBRZ|GOCSPX-|SG\\." ` → 결과 empty 확인
- [ ] `.env` 파일권한 `600` 유지
- [ ] `FLASK_ENV=production` Railway 설정 / `DEV_LOGIN_SECRET` Railway 에 **없음** 확인
- [ ] `AGENT_ENABLED=0` 로펌 승인 전까지 유지

### 주간
- [ ] `pip list --outdated` + `npm audit` → critical 검토
- [ ] `UserAgentAudit` refusal_rate 확인 (60% 미만 하락 시 gate 누수 의심)

### 월간
- [ ] `SECRET_KEY` rotate (모든 세션 무효화, 유저 재로그인 알림 필요)
- [ ] Railway 로그 `agent.gate.deny` 패턴 분석 → advice patterns 튜닝

### 분기
- [ ] 전 키 rotate (Anthropic / SendGrid / Kakao / Google / KIS)
- [ ] 외부 보안 리뷰 (또는 `gitleaks detect` 전체 이력)
- [ ] PIPA 데이터 export drill

---

## 📌 현재 상태 빠른 링크

- **최신 commit**: `7f411b3`
- **Tests**: 267/267 pass
- **Build**: 50/50 static routes, 0 TS errors
- **Production**: https://pivoxquant.com (베타 `***REDACTED***`)
- **Backend**: https://RAILWAY_BACKEND_HOST.up.railway.app
- **GitHub**: https://github.com/seanbae-analyst/pivoxquant
- **AGENT_ENABLED**: `0` (Closed Beta 안전)

**가장 치명 미완 1건**: `services/artifacts/templates/dd_checklist.html` AAPL 하드코딩 (자본시장법 §178 허위표시 리스크).

**가장 쉬운 즉시 조치**: `chmod 600 /Users/seanbae/Desktop/취준/stockpilot/.env`

---

**작성**: 2026-04-23 · TODO 단일 진실 공급원
**상세 배경**: `HANDOVER.md` v6 참조
