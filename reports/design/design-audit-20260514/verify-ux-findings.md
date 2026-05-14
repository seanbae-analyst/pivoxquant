# PivoxQuant — verify-ux 제약 검증 findings — 2026-05-14

원 audit(`design-audit-20260514.md`)에서 검증 못 한 3개 제약(모바일 375 / 베타게이트 / 로그아웃)을 incognito + DevTools로 검증한 결과.

총 12건 고유: HIGH 1 / MEDIUM 7 / POLISH 2 / PASS 4 / BLOCKED 1.

---

## HIGH

### FINDING-MOB-001 · /login 모바일 375px 치명적 수평 오버플로우 (SHIP-BLOCKER)
- **Page:** `/login`
- **증거:** `pq-auth-shell-v2` 클래스가 `grid-template-columns: 735px 735px` → computed `width: 1470px`. 375px 뷰포트에서 3.92배 오버플로우. 반응형 미디어쿼리(sm:/md:) 전무. 우측 패널(로그인 폼) 화면 밖.
- **왜:** 모바일 신규 유저가 로그인 폼 자체에 접근 불가. "Meet your CFO" CTA → /login 도달하는 모든 모바일 유저 영향.
- **수정:** `pq-auth-shell-v2`에 반응형 추가 — 375~767px 싱글 컬럼(`grid-template-columns: 1fr`), 768px+ 2-column. 전체 auth surface(login/signup/onboarding) 동일 패턴 전수 점검.

---

## MEDIUM

### FINDING-MOB-002 · /login "Log in" 링크 터치 타깃 38px (44px 미달)
- **Page:** `/login` 네비
- **증거:** `Log in` 링크 height 38px / width 68px. WCAG 2.5.5 최소 44×44.
- **수정:** MOB-001 수정과 함께. 패딩으로 44px 확보.

### FINDING-MOB-003 / LAND-001 · 랜딩 히어로 컴플라이언스 문구 11px
- **Page:** 랜딩 히어로 섹션
- **증거:** `<p class="... text-[11px] italic ...">— Not investment advice. Informational research only. Past performance does not guarantee future results.</p>` computed 11px. iOS Safari 자동 zoom 트리거 가능.
- **왜:** 금소법·자본시장법 면책 문구가 가장 작은 폰트. 법적 + UX 위험 동시.
- **수정:** `text-[11px]` → 최소 `text-[13px]` 이상. 토큰화 권장(`--pq-text-body-sm`).

### FINDING-LAND-002 · 랜딩 푸터 컴플라이언스 문구 12px
- **Page:** 랜딩 푸터
- **증거:** "PivoxQuant is not a licensed investment advisor..." computed 12px center.
- **왜:** 히어로 11px + 푸터 12px — 면책 문구가 의도적으로 최소화됨. 규제기관이 "눈에 안 띄는 면책"으로 부정 평가 가능.
- **수정:** 최소 13~14px.

### FINDING-GATE-001 · 베타 게이트 form method="get" (JS 비활성 시 비번 URL 노출)
- **Page:** `/beta-gate`
- **증거:** `<form action="..." method="get">` + React `onSubmit` 핸들러. 정상 JS 환경은 안전하나 JS 비활성 시 `?password=XXXX`가 URL/히스토리/액세스로그에 남음.
- **왜:** `pivoxaudit` 이전 비번 GitHub 노출 전례. defense-in-depth.
- **수정:** form `method="post"` 설정. JS는 그대로 onSubmit intercept.

### FINDING-GATE-002 · 루트 URL `/` 베타 게이트 우회 가능 — **CEO 결정 필요**
- **Page:** `/` vs `/beta-gate`
- **증거:** 비인증 상태로 `/` 직접 접속 → 랜딩 페이지 전체 노출. 게이트는 `/beta-gate` 경로에만 존재.
- **판단:** 의도된 설계 가능성(랜딩=마케팅 공개, 앱 내부만 보호). "비공개 베타" 콘셉트와 불일치. **CEO 확인 필요 — fix 보류.**

### FINDING-LAND-004 · 랜딩 testimonials 섹션 부재
- **판단:** 베타 단계라 허용 가능. 정식 론칭 전 고려. **fix 보류(베타 허용).**

### FINDING-LAND-006 · GitHub repo 링크 푸터 공개 노출 — **CEO 결정 필요**
- **Page:** 랜딩 푸터
- **증거:** `<a href="https://github.com/seanbae-analyst/pivoxquant">GITHUB</a>`. repo public이면 경쟁자가 소스 열람 가능.
- **판단:** §101 면제 트랙 + 비공개 베타 맥락에서 repo 광고가 적절한지 **CEO 확인 필요 — fix 보류.**

---

## POLISH

### FINDING-GATE-004 · 베타 게이트 오류 메시지 브랜드 보이스 미적용
- **증거:** "잘못된 비밀번호입니다. 다시 시도해주세요" — 일반 문구.
- **수정:** 브랜드 보이스 적용(예: "CEO로부터 전달받은 코드를 확인해주세요").

### FINDING-LAND-007 · 랜딩 모바일 햄버거 버튼 40px (44px에 4px 부족)
- **증거:** `h-10 w-10` = 40×40px. `inline-flex items-center justify-center` 패딩으로 일부 보완.
- **수정:** `h-11 w-11` (44px) 또는 패딩 확대.

---

## PASS (수정 불필요)
- **FINDING-GATE-003** — 베타게이트 모바일 `max-w-md` 반응형 정상.
- **FINDING-LAND-003** — AI slop 없음. purple gradient/blob 0건. v3 준수.
- **FINDING-LAND-005** — Terms/Privacy/Contact 링크 정상 노출.
- **FINDING-LAND-008** — "Meet your CFO" CTA 44~48px 정상.

---

## BLOCKED
- **FINDING-MOB-004** — App 페이지 8개(/home /portfolio /risk /market /detail/* /signals /reports /settings) 모바일 검증 불가. production에 `/api/auth/dev-login` 없음 → 인증 불가. **별도 인증 세션 필요.** 단, 모바일 반응형 CSS 수정 자체는 소스 코드 점검으로 가능.
