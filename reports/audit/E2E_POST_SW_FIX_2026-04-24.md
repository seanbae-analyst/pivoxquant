# Post-SW-Fix 브라우저 실측 - 2026-04-24

## 실측 환경
- Frontend: http://localhost:3000
- Backend: http://localhost:5050
- 인증: dev-login (QA Tester / test@pivoxquant.dev)
- 실측 시각: 2026-04-24 14:19 KST

---

## SW fix 실측 (Scope #1)

**사전 작업**: SW 언레지스터 + 캐시 2개 삭제 후 reload, 5초 대기

- **skeleton 0개?** Y
  - 증거: `document.querySelectorAll('[class*="skeleton"],...').length` → 0
  - (이전 세션에서 68이 나온 건 CSS selector가 실제 skeleton 클래스와 불일치한 오탐이었음)
  - 화면 스크린샷(ss_58765lc4g): Portfolio 페이지 정상 렌더링, $0 / ₩0 / POSITIONS HELD 0 표시됨

- **/api/portfolio/positions status?** 200 OK (503 없음)
  - 증거: Network log →
    - `GET /api/portfolio/positions` → 200
    - `GET /api/portfolio/summary` → 200
    - `GET /api/portfolio/trades?limit=8` → 200
    - `GET /api/portfolio` → 200
  - 각 API 2회씩 (initial + reload) 모두 200 확인

- **Add Position 버튼?** Y
  - 증거: `document.querySelectorAll('button').map(b=>b.textContent)` →
    "**+ Add to book →**" 버튼 존재 (스크린샷 ss_58765lc4g 우측 상단에 시각 확인)
  - 참고: 버튼 텍스트가 "Add to book"이지 "Add Position"이 아님 (UI 텍스트 변경된 것으로 보임, 기능은 정상)

- **판정: BUG-1 fix VERIFIED**
  - 503 에러 없음, SW 관련 오프라인 차단 없음, 페이지 정상 렌더링

---

## Alpaca Connect (Scope #2)

- **버튼 존재?** Y — `ref_106: button "Connect Alpaca"` 발견 (Settings > Connections > Alpaca 섹션)
- **버튼 동작?** 모달 팝업 정상 오픈
- **관찰된 behavior**:
  - "CONNECT ALPACA" 버튼 클릭 → "Connect Alpaca" 모달 즉시 팝업
  - 모달 내 구성:
    - ENVIRONMENT 탭: **PAPER** (선택됨) / **LIVE · DISABLED** (비활성)
    - API KEY ID 입력 필드 (placeholder: PKXXXXXXXXXXXXXXXXXX)
    - API SECRET KEY 입력 필드
    - "CONNECT PAPER" 버튼 / "CANCEL" 버튼
    - 외부 링크: "ALPACA.MARKETS" (새 탭 열기)
    - 면책 문구: "Alpaca integration is paper-only. No live orders will be placed. This is not investment advice."
  - 클릭 직후 추가 API 호출 없음 (순수 클라이언트 사이드 모달)
  - 콘솔 에러 없음 (Alpaca 관련)
- **판정: PASS** — 모달 정상 동작, LIVE 거래 잠금(disabled) 확인됨

---

## 알림벨 & 프로필 (Scope #3)

- **알림벨: Y (동작은 하지만 시각적 버그 존재)**
  - DOM: `button[aria-label="Notifications"]` 존재, x=1350 y=8 w=40 h=40
  - 클릭 → "NOTIFICATIONS" 드롭다운 패널 오픈 확인 (스크린샷 ss_2992zkvmm, ss_3824rjdv8)
  - **버그 발견**: 알림 아이콘이 헤더에서 시각적으로 보이지 않음
    - `color: rgb(10, 10, 10)` (거의 검정 아이콘) + `backgroundColor: rgba(0,0,0,0)` (투명 배경) + 헤더 배경 검정 → 알림 아이콘 불가시
    - zoom 스크린샷에서도 QT 프로필 아이콘만 보이고 알림 아이콘은 육안 불가

- **프로필: Y (정상)**
  - QT 아이콘 클릭 → 드롭다운 메뉴 정상 오픈 (스크린샷 ss_51593i1st)
  - 메뉴 항목: My Profile / Settings / Billing / Keyboard shortcuts / Help & Docs / Sign out
  - 사용자 정보: "QA Tester / test@pivoxquant.dev / OBSERVER" 표시

- **BUG-1 fix 이후 자동 해결?**: 프로필 메뉴는 자동 해결. 알림벨은 동작하나 가시성 버그 별개로 존재.

---

## 발견 추가 버그

### BUG-NEW-1: 알림 아이콘 헤더 불가시 (검정 아이콘 / 검정 배경)
- **확신도**: 100%
- **증상**: 헤더 우측 알림 아이콘이 검정 배경에 검정색 아이콘으로 렌더링되어 육안으로 완전히 보이지 않음
- **재현**: 어느 페이지에서든 헤더 우측 끝을 보면 QT 프로필 아이콘만 보임. 알림 아이콘(종 모양)이 위치하지만 불가시
- **증거**:
  - DOM: `button[aria-label="Notifications"]` → `color: rgb(10,10,10)`, `backgroundColor: rgba(0,0,0,0)`, opacity: 1
  - zoom 스크린샷: QT 아이콘 좌측에 알림 아이콘 영역은 검정 빈 공간으로 보임
  - 클릭은 가능 (x=1350, y=8 정확히 클릭 시 드롭다운 열림)
- **추정 원인**: 헤더 컴포넌트에서 알림 아이콘의 stroke/color가 다크 배경에 맞지 않는 값(검정)으로 설정됨. 헤더 배경이 검정이므로 대비가 0
- **수정 방향**: 헤더 알림 버튼 아이콘 색상을 `currentColor`가 금색/흰색 계열이 되도록 CSS 수정 필요

### BUG-NEW-2 (낮은 확신 50%): OBSERVATION ALERTS 팝업이 알림 드롭다운을 가림
- **증상**: 알림벨 클릭 시 NOTIFICATIONS 드롭다운과 동시에 "OBSERVATION ALERTS" 팝업(Push 알림 허용 요청)이 겹쳐서 드롭다운이 완전히 가려짐
- **확인**: 두 요소가 z-index 충돌로 겹침 (스크린샷 ss_2992zkvmm)
- **추정 원인**: Push 알림 권한 요청 팝업이 알림벨 클릭 이벤트에 트리거되어 동시 발생, z-index 우선순위 충돌

---

## 전체 요약

| 항목 | 결과 |
|------|------|
| BUG-1 SW fix 검증 | VERIFIED |
| Alpaca Connect 모달 | PASS |
| 알림벨 동작 | 동작 O, 가시성 버그 있음 |
| 프로필 메뉴 | PASS |

- 사냥 페이지: 2개 (/portfolio, /settings)
- 발견: 2건 (HIGH 1건 - 알림아이콘 불가시, LOW 1건 - 팝업 겹침)
- 즉시 fix 필요: BUG-NEW-1 (알림 아이콘 색상)
- 추가 조사 필요: BUG-NEW-2 (팝업 z-index)

