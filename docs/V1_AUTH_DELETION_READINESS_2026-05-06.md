# signup/login _v1 → _v2 P0 법적 기능 동등성 검증 — 2026-05-06

> 조사자: investigator agent (file Read + grep 기반, 추측 없음)
> 조사일: 2026-05-06
> 근거 파일: _v1/page-v1.tsx, _v2/page-v2.tsx, page.tsx (각 라우트), .env.local 직접 열람

---

## V2 활성 상태

### .env.local 실측값

| 페이지 | 환경변수 | .env.local 값 | 실제 렌더 |
|--------|----------|---------------|-----------|
| signup | NEXT_PUBLIC_SIGNUP_V2 | **미설정 (행 없음)** | **v1이 라이브** |
| login | NEXT_PUBLIC_LOGIN_V2 | **미설정 (행 없음)** | **v1이 라이브** |

증거:
- `/Users/seanbae/Desktop/취준/pivoxquant/frontend/.env.local` 전체 7행 확인 — NEXT_PUBLIC_SIGNUP_V2, NEXT_PUBLIC_LOGIN_V2 두 항목 모두 존재하지 않음 (grep exit code 1 반환)
- `.env.example` line 45-46: `NEXT_PUBLIC_LOGIN_V2=true`, `NEXT_PUBLIC_SIGNUP_V2=true` — example에는 있지만 .env.local에 복사되지 않은 상태
- `signup/page.tsx` line 25: `const v2Enabled = process.env.NEXT_PUBLIC_SIGNUP_V2 === "true";` — 엄격 비교, unset → false → v1 렌더
- `login/page.tsx` line 25: `const v2Enabled = process.env.NEXT_PUBLIC_LOGIN_V2 === "true";` — 동일 패턴

**결론: signup과 login 모두 현재 v1이 production 활성 상태. v2는 dead-code 상태.**

---

## signup _v1 vs _v2 — 5 consent P0 항목

### 검증 기준

| # | 항목 | 법적 근거 | 필수/선택 |
|---|------|-----------|-----------|
| 1 | 이용약관 + 개인정보처리방침 동의 | 약관 13조, 개보처 12조 | 필수 |
| 2 | 자본시장법 §101 면제 — 투자자문업 아님 고지 | §101 4요건 | 필수 |
| 3 | 만 14세 이상 (PIPA §22) | PIPA §22 연령 확인 | 필수 |
| 4 | 개인정보 국외 이전 동의 (PIPA §28-8) | PIPA §28-8 | 필수 |
| 5 | 마케팅 수신 동의 (정통망법 §50 opt-in) | 정통망법 §50 | 선택 |

---

### 상세 동등성 비교표

#### Consent 1: 이용약관 + 개인정보처리방침

| 항목 | _v1 위치 | _v2 위치 |
|------|----------|----------|
| 텍스트 | line 226-248: `[필수] 이용약관 및 개인정보처리방침에 동의합니다.` | line 351-382: `[필수] 이용약관 및 개인정보처리방침에 동의합니다.` |
| 필수 여부 | [필수], allRequired 4개 중 포함 | [필수], allRequired 4개 중 포함 (`consents.terms` line 129) |
| /terms 링크 | line 229: `href="/terms"` | line 353: `href="/terms"` |
| /privacy 링크 | line 239: `href="/privacy"` | line 366: `href="/privacy"` |
| 체크박스 id | `agree_terms` (line 221) | `agree_terms` (line 347) |
| pulse 기능 | ring-rose-400/70 pulse (line 219) | pulseRowStyle active (line 343) |

판정: 텍스트 동등 ✅ / 필수 동등 ✅ / 링크 동등 ✅ / pulse UX 동등 ✅

---

#### Consent 2: 자본시장법 §101 면제 — 투자자문업 아님 고지

| 항목 | _v1 위치 | _v2 위치 |
|------|----------|----------|
| 텍스트 | line 262-265: `PivoxQuant는 자본시장법상 투자자문업이 아니며, 본 서비스의 모든 분석·리포트·시그널은 정보 제공 목적임을 이해합니다. 투자 판단과 그 결과는 이용자 본인의 책임입니다.` | line 397-401: 동일 텍스트 (공백 배치만 상이) |
| 필수 여부 | [필수], `consents.non_advisory` allRequired 포함 (line 124) | [필수], `consents.non_advisory` allRequired 포함 (line 130) |
| 링크 | 없음 | 없음 |
| 체크박스 id | `agree_non_advisory` (line 253) | `agree_non_advisory` (line 390) |
| pulse 기능 | ring-rose-400/70 (line 254) | pulseRowStyle active (line 388) |

판정: 텍스트 동등 ✅ / 필수 동등 ✅ / pulse UX 동등 ✅

---

#### Consent 3: 만 14세 이상 (PIPA §22)

| 항목 | _v1 위치 | _v2 위치 |
|------|----------|----------|
| 텍스트 | line 279: `만 14세 이상입니다. (개인정보보호법 §22)` | line 417-419: `만 14세 이상입니다. (개인정보보호법 §22)` |
| 필수 여부 | [필수], `consents.age` allRequired 포함 (line 125) | [필수], `consents.age` allRequired 포함 (line 131) |
| 링크 | 없음 | 없음 |
| 체크박스 id | `agree_age` (line 270) | `agree_age` (line 404) |
| pulse 기능 | ring-rose-400/70 (line 271) | pulseRowStyle active (line 409) |

판정: 텍스트 동등 ✅ / 필수 동등 ✅ / pulse UX 동등 ✅

---

#### Consent 4: 개인정보 국외 이전 (PIPA §28-8)

| 항목 | _v1 위치 | _v2 위치 |
|------|----------|----------|
| 텍스트 | line 295-300: `개인정보의 국외 이전에 동의합니다. (PIPA §28-8 — Anthropic / Stripe / Vercel / Railway / Google, 미국 소재 위탁처)` | line 434-438: 동일 텍스트 |
| 필수 여부 | [필수], `consents.cross_border` allRequired 포함 (line 126) | [필수], `consents.cross_border` allRequired 포함 (line 132) |
| /privacy#cross-border 링크 | line 298-305: `href="/privacy#cross-border"` + `보기` 앵커 | line 438-442: `href="/privacy#cross-border"` + `보기` 앵커 |
| 체크박스 id | `agree_cross_border` (line 286) | `agree_cross_border` (line 428) |
| pulse 기능 | ring-rose-400/70 (line 287) | pulseRowStyle active (line 423) |

판정: 텍스트 동등 ✅ / 필수 동등 ✅ / 링크 동등 ✅ / pulse UX 동등 ✅

---

#### Consent 5: 마케팅 수신 동의 (정통망법 §50)

| 항목 | _v1 위치 | _v2 위치 |
|------|----------|----------|
| 텍스트 | line 319-322: `마케팅 정보(이벤트, 신기능 안내) 수신에 동의합니다.` | line 455-458: `마케팅 정보(이벤트, 신기능 안내) 수신에 동의합니다.` |
| 필수/선택 | [선택] — allRequired 4개에 미포함 | [선택] — allRequired 4개에 미포함 (`optionalTagStyle` line 232) |
| 링크 | 없음 | 없음 |
| 체크박스 id | `agree_marketing` (line 311) | `agree_marketing` (line 449) |
| pulse 없음 확인 | pulse 클래스 없음 (선택 항목) | pulseRowStyle 미적용 (line 449: `style={consentRowStyle}` — pulseRowStyle 합성 없음) |
| §50 서버 flush | 없음 (localStorage만) | v2 주석 line 20-26: `flushPendingMarketingConsent()` in `lib/consents.ts` — 최초 dashboard mount 시 POST /api/consents/marketing 실행 예고 (PR #73 의존) |

판정: 텍스트 동등 ✅ / 선택 동등 ✅ / pulse 미적용 동등 ✅

주목: v2는 정통망법 §50 server flush 경로 (`flushPendingMarketingConsent`) 구현이 별도 PR #73 (`routes/consents.py`) 에 의존한다고 주석에 명시되어 있음. 이 PR의 머지 여부는 본 조사 범위(파일 열람)에서 확인 불가 — PR #73 상태는 별도 확인 필요.

---

### signup 종합 consent 동등성 매트릭스

| Consent | _v1 위치 (라인) | _v2 위치 (라인) | 텍스트 동등 | 필수 동등 | 링크 동등 | pulse 동등 | GO/MISSING |
|---------|----------------|----------------|------------|----------|----------|-----------|------------|
| 1. 이용약관 + 개인정보 | v1:226-248 | v2:339-382 | ✅ | ✅ | ✅ (/terms, /privacy) | ✅ | GO |
| 2. §101 비자문 고지 | v1:252-266 | v2:384-402 | ✅ | ✅ | 해당없음 | ✅ | GO |
| 3. 만 14세 (PIPA §22) | v1:268-282 | v2:404-420 | ✅ | ✅ | 해당없음 | ✅ | GO |
| 4. 국외 이전 (PIPA §28-8) | v1:284-307 | v2:422-447 | ✅ | ✅ | ✅ (/privacy#cross-border) | ✅ | GO |
| 5. 마케팅 (§50 opt-in) | v1:309-324 | v2:449-459 | ✅ | ✅(선택) | 해당없음 | ✅(미적용 동등) | GO |

모든 5개 consent: GO

---

### signup 추가 기능 동등성

| 기능 | _v1 | _v2 | 동등 |
|------|-----|-----|------|
| CONSENT_STORAGE_KEY | `"pivox_signup_consents"` (line 51) | `"pivox_signup_consents"` (line 41) | ✅ 동일 상수 |
| allRequired 4개 필수 체크 | terms && non_advisory && age && cross_border (line 123-127) | 동일 조건 (line 129-133) | ✅ |
| handleOAuthClick consent gate | 미충족 시 e.preventDefault() (line 163-165) | 동일 gate (line 175-178) | ✅ |
| localStorage snapshot | JSON.stringify({...consents, consented_at}) (line 169-176) | 동일 구조 (line 180-188) | ✅ |
| pulseUnchecked 900ms auto-clear | setTimeout 900ms (line 132-135) | setTimeout 900ms (line 137-140) | ✅ |
| useAuth + router.replace("/home") | line 142-146 | line 142-146 | ✅ |
| Google OAuth 버튼 | API.auth.google (line 330) | OAuthButtonsV2 → API.auth.google (oauth-buttons-v2.tsx line 133) | ✅ |
| Kakao OAuth 버튼 | API.auth.kakao (line 352) | OAuthButtonsV2 → API.auth.kakao (oauth-buttons-v2.tsx line 155) | ✅ |
| 로그인 링크 | href="/login" (line 391) | AuthLinkV2 href="/login" (line 498) | ✅ |
| 베타 배지 | `베타 기간 무료 · 카드 등록 불필요` (line 400) | `Beta · 카드 등록 불필요` (line 517) | ✅ 동등 (영문 "Beta" 사용) |

---

## login _v1 vs _v2 — OAuth + 면책

### 상세 동등성 비교표

| 기능 | _v1 위치 | _v2 위치 | 동등 |
|------|----------|----------|------|
| Google OAuth | API.auth.google href (line 95-101) | OAuthButtonsV2 → API.auth.google (oauth-buttons-v2.tsx line 133) | ✅ |
| Kakao OAuth | API.auth.kakao href (line 103-109) | OAuthButtonsV2 → API.auth.kakao (oauth-buttons-v2.tsx line 155) | ✅ |
| useAuth + router.replace("/home") | line 47-51 | line 37-41 | ✅ |
| loading 스피너 | line 53-58 (animate-spin) | line 43-57 (animate-spin, Bronze 컬러) | ✅ |
| user null gating | line 61: `if (user) return null` | line 60: `if (user) return null` | ✅ |
| legal footer 텍스트 | line 131-141: `계속하면 이용약관 및 개인정보처리방침에 동의하게 됩니다.` | line 186-221: 동일 텍스트 | ✅ |
| /terms 링크 | line 133: `href="/terms"` | line 199: `href="/terms"` | ✅ |
| /privacy 링크 | line 136: `href="/privacy"` | line 210: `href="/privacy"` | ✅ |
| 회원가입 링크 | href="/signup" (line 121-128) | AuthLinkV2 href="/signup" (line 180-184) | ✅ |
| consent gating | 없음 (login은 gating 없음) | 없음 (`OAuthButtonsV2` props에 disabled 미전달, line 152: `<OAuthButtonsV2 />`) | ✅ |
| 베타 비밀번호 처리 | 없음 (UI 노출 없음) | 없음 | ✅ |
| DisclaimerBanner | 없음 (login 페이지는 면책 배너 미대상) | 없음 | ✅ |

---

## 종합 판정

### signup/_v1

**판정: BLOCK**

사유:
- `NEXT_PUBLIC_SIGNUP_V2` 가 `.env.local`에 미설정 → 현재 v1이 production 활성
- v1을 삭제하면 `signup/page.tsx` line 17 `import SignupPageV1 from "./_v1/page-v1"` 가 즉시 build error 유발
- 5개 consent는 v2에 100% 동등하게 이식됨 — 기능 동등성 자체는 GO
- 단, v2 flag가 활성화되기 전에는 삭제 불가

**선행 조건 (이 순서로):**
1. `.env.local`에 `NEXT_PUBLIC_SIGNUP_V2=true` 추가 (또는 Railway/Vercel 환경변수 설정)
2. v2 렌더 확인 (브라우저 또는 빌드)
3. 그 후 삭제 PR 가능

---

### login/_v1

**판정: BLOCK**

사유:
- `NEXT_PUBLIC_LOGIN_V2` 가 `.env.local`에 미설정 → 현재 v1이 production 활성
- v1을 삭제하면 `login/page.tsx` line 17 `import LoginPageV1 from "./_v1/page-v1"` 가 즉시 build error 유발
- OAuth + legal footer + useAuth 모두 v2에 100% 동등하게 이식됨 — 기능 동등성 자체는 GO
- 단, v2 flag가 활성화되기 전에는 삭제 불가

**선행 조건 (이 순서로):**
1. `.env.local`에 `NEXT_PUBLIC_LOGIN_V2=true` 추가 (또는 Railway/Vercel 환경변수 설정)
2. v2 렌더 확인
3. 그 후 삭제 PR 가능

---

## v2 누락 항목 (PORT_FIRST)

PORT_FIRST 항목 없음 — 5개 consent 및 OAuth 기능이 v2에 100% 이식되어 있음.

단 하나 추적 필요한 항목:
- 정통망법 §50 server flush (`flushPendingMarketingConsent`) — v2 signup 주석 line 20-26에 PR #73 (`routes/consents.py`) 의존 명시. PR #73 머지 여부 미확인. 미머지 상태라면 마케팅 동의가 localStorage에만 저장되고 백엔드에 반영되지 않음. v1도 동일하게 localStorage만 저장하므로 v1과 동등한 상태. 추가 조사 대상: PR #73 상태 확인.

---

## 다음 액션

### BLOCK 해소 절차 (signup + login 동시)

1. **v2 flag 활성화**: `.env.local`에 2행 추가
   ```
   NEXT_PUBLIC_SIGNUP_V2=true
   NEXT_PUBLIC_LOGIN_V2=true
   ```
   Railway/Vercel 배포 시: 각 플랫폼 환경변수 패널에서 동일 추가.

2. **v2 렌더 확인**: 로컬 `npm run dev` 후 /signup, /login 접근 → Vantablack split layout 렌더 확인.

3. **삭제 PR 생성**:
   - 삭제 대상: `(auth)/signup/_v1/page-v1.tsx`, `(auth)/login/_v1/page-v1.tsx` (2파일)
   - PR 본문 인용: 본 문서 경로 + "5 consent 100% 동등 verified" + "OAuth 100% 동등 verified"
   - 30파일 미만 → 단일 PR 가능

4. **머지 후 1주 모니터링**: /signup, /login regression 발견 시 즉시 revert.

---

## 참조 파일 경로

| 파일 | 경로 | 라인수 |
|------|------|--------|
| signup _v1 | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/(auth)/signup/_v1/page-v1.tsx` | 405 |
| signup _v2 | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/(auth)/signup/_v2/page-v2.tsx` | 542 |
| login _v1 | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/(auth)/login/_v1/page-v1.tsx` | 145 |
| login _v2 | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/(auth)/login/_v2/page-v2.tsx` | 246 |
| signup page.tsx | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/(auth)/signup/page.tsx` | 27 |
| login page.tsx | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/app/(auth)/login/page.tsx` | 27 |
| OAuthButtonsV2 | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/src/components/auth/v2/oauth-buttons-v2.tsx` | 190 |
| .env.local | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/.env.local` | 7행 |
| .env.example | `/Users/seanbae/Desktop/취준/pivoxquant/frontend/.env.example` | line 45-46 |
