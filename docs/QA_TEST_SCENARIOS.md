# QA Test Scenarios (User Story 기반)

> 2026-08-31 프룬 반영. 살아있는 화면만 대상: `/mirror` `/portfolio` `/journal`
> `/pre-trade` `/home` `/profile` `/settings` + auth + 공개 법적/지원 페이지.
> 삭제된 화면(signals / discover / market / watchlist / risk / ai-chat /
> reports / detail / features / simulator)의 시나리오는 함께 제거됨.

## 0. Dev Login (E2E 전용)
- POST `/api/auth/dev-login` with `{"secret": "<DEV_LOGIN_SECRET>"}` -> `{"ok": true, "user": {...}}`
- 잘못된 secret -> 401
- DEV_LOGIN_SECRET 미설정 시 -> 404

## 1. Portfolio 추가 플로우
- "nvidia" 검색 -> NVDA 자동완성 -> 선택
- 수량 10, 단가 $200 입력 -> 저장
- 포트폴리오 목록에 NVDA 10주 $200 표시 확인
- 달러 기호 ($) 존재 확인
- 삼성전자 "005930" 검색 -> 선택 -> 100주 W70,000 -> 저장
- 원화 기호 표시 확인
- 저장 후 다시 열어서 단가 값 보존 확인

## 2. Journal (기록)
- 매매 기록 작성 -> 저장 -> 목록에 표시
- 기록 수정/삭제 round-trip
- 빈 기록 상태(empty state) 문구 확인 — 가짜 수치 노출 금지

## 3. Pre-trade
- 매수/매도 전 체크인 작성 -> 저장
- 저장된 체크인이 이후 기록과 연결되는지 확인

## 4. Mirror (거울 홈)
- 기록 0건 유저: 빈 상태 안내만, 추정 수치 표시 금지
- 기록 있는 유저: 실제 기록 기반 요약만 표시

## 5. Settings / Profile
- 언어 토글 (한/영)
- 프로필 표시
- 로그아웃
- 회원탈퇴 (PIPA) 플로우 진입 확인

## 6. 모바일 (375x812)
- Bottom nav 모든 탭
- 메뉴 시트 열기/닫기
- 포트폴리오 추가 모달

## 7. 엣지 케이스
- 빈 입력으로 검색
- 존재하지 않는 티커 "ZZZZZ"
- 수량 0 / 음수 / 소수점
- 단가 0 / 음수
- 극단적 금액 ($0.01, $999,999,999)
