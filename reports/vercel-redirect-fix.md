# Vercel Redirect Chain Collapse — CEO 단계별 가이드

**작성일**: 2026-04-23
**목적**: Lighthouse "Redirect chain" 항목 제거 (+1,220 ms LCP)
**대상 사용자**: 배상현 (Vercel Dashboard 접속 계정)

## 현재 상태 (FAIL)

Lighthouse 측정 결과:
```
pivoxquant.com           → www.pivoxquant.com   (308 Permanent Redirect)
www.pivoxquant.com       → /beta-gate           (307 Temporary Redirect from middleware)
```

두 단계 redirect 때문에 첫 요청이 **~1.2초** 지연됨. 모바일 3G에서는 더 커짐.

## 목표 (PASS)

```
pivoxquant.com           → /beta-gate           (307, 단일 hop)
www.pivoxquant.com       → pivoxquant.com       (308, one-time 정규화. 유저는 보통 이 도메인 안 씀)
```

또는 더 깔끔하게:
```
www.pivoxquant.com       → pivoxquant.com       (308, canonical)
pivoxquant.com           → (middleware가 /beta-gate 판단)
```

요점: **apex 도메인(pivoxquant.com)을 primary**로 지정해서 www → apex 1회만 튀게 만드는 것.

---

## 단계별 작업 (약 3분 소요)

### Step 1. Vercel 로그인
1. https://vercel.com 접속
2. 우측 상단 **Log in** → GitHub 계정(`seanbae-analyst`)으로 로그인
3. 프로젝트 목록에서 **pivoxquant** 클릭 (또는 `stockpilot-frontend`로 등록되어 있을 수 있음)

### Step 2. Domains 설정 페이지 진입
1. 상단 탭 중 **Settings** 클릭
2. 좌측 사이드바에서 **Domains** 클릭
3. 도메인 리스트가 보임:
   - `pivoxquant.com`
   - `www.pivoxquant.com`
   - `<project>-<hash>.vercel.app` (자동 생성)

### Step 3. Primary 도메인 확인 및 변경

**현재 primary가 무엇인지 먼저 확인** — 각 도메인 우측에 "Primary" 뱃지가 붙어 있는 것이 primary.

**만약 `www.pivoxquant.com`이 primary라면 (현재 의심 상태)**:
1. `pivoxquant.com` 줄 우측의 `⋯` (점 3개) 메뉴 클릭
2. **Set as Primary Domain** 클릭
3. 확인 다이얼로그 나오면 **Confirm** 클릭

**만약 `pivoxquant.com`이 이미 primary라면**:
- 그대로 두고 Step 4로.

### Step 4. Redirect 방향 확인
Primary를 `pivoxquant.com`으로 바꾸면 Vercel이 자동으로:
- `www.pivoxquant.com` → `pivoxquant.com` (308) redirect 만듦
- apex로 온 요청은 그대로 통과

각 도메인 줄 아래 작은 회색 글씨로 redirect 동작이 표시됨. 다음과 같이 읽히는지 확인:
- `pivoxquant.com` — (primary 뱃지 있음, redirect 설명 없음)
- `www.pivoxquant.com` — `Redirects to pivoxquant.com (308)`

### Step 5. 검증 (터미널에서)

배포 완료 후 약 30초~1분 대기 (Vercel Edge 전파 시간).

```bash
# apex는 middleware로 바로 이동 (beta-gate)
curl -sI https://pivoxquant.com | grep -E "(HTTP|location)"
# 기대: HTTP/2 307, location: /beta-gate  (또는 실제 랜딩이면 200)

# www는 apex로 1회만 튀어야 함
curl -sI https://www.pivoxquant.com | grep -E "(HTTP|location)"
# 기대: HTTP/2 308, location: https://pivoxquant.com/

# 전체 체인 추적
curl -sIL https://pivoxquant.com | grep -E "(HTTP|location)"
# 기대: hop 2개 이하
```

### Step 6. Lighthouse 재측정
```bash
# 로컬에서
npx lighthouse https://pivoxquant.com --preset=desktop --only-categories=performance --quiet --chrome-flags="--headless"
```
"Avoid multiple page redirects" 항목이 PASS (초록)로 바뀌어야 함.

---

## 주의사항

### ⚠️ 절대 하지 말아야 할 것
- **Custom redirect** 추가 금지: `/api/*`, `/beta-gate` 같은 커스텀 경로에 Vercel Dashboard에서 redirect rule을 추가하면 middleware와 충돌.
- **Remove domain** 금지: `www.pivoxquant.com`을 지우면 기존 구글/네이버에 인덱싱된 www 링크가 죽음. 반드시 유지하고 redirect target만 apex로.

### ⏱️ 전파 시간
- Vercel Edge: 30초 이내
- DNS (가비아 → 브라우저 캐시): 최대 5분
- 즉시 확인하려면 브라우저 시크릿창 또는 `--disable-cache`로 test.

### 🔄 롤백 방법
문제가 생기면 Step 3을 반대로: `www.pivoxquant.com`을 primary로 되돌리기.

---

## 부록: 왜 이게 1.2초를 줄이는가

```
[현재 FAIL]
t=0ms    GET pivoxquant.com             → TLS handshake 200ms
t=200ms  308 Location: www.pivoxquant.com
t=200ms  GET www.pivoxquant.com         → TLS handshake 150ms (HSTS preload 있으면 더 짧음)
t=350ms  307 Location: /beta-gate
t=350ms  GET /beta-gate                 → TTFB ~300ms
t=650ms  HTML 도착
---
Total redirect overhead: ~1,220 ms on mobile 3G (Lighthouse emulation)

[수정 후]
t=0ms    GET pivoxquant.com             → TLS handshake 200ms
t=200ms  307 /beta-gate
t=200ms  GET /beta-gate                 → TTFB ~300ms
t=500ms  HTML 도착
---
Saving: ~1,100-1,220 ms
```

이 fix 하나만으로도 모바일 Lighthouse 성능 점수가 **59 → 70+**로 상승할 것으로 예상.
