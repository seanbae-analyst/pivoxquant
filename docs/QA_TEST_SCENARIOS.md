# QA Test Scenarios (User Story 기반)

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

## 2. Market 데이터
- /market 페이지 -> US 탭: S&P500, NASDAQ, DOW 값 존재
- KR 탭: KOSPI, KOSDAQ 값 존재
- 섹터 성과 차트 렌더

## 3. 타임머신
- 기본값 계산 -> 결과 카드 렌더
- 공유 링크 ?ticker=AAPL&start_date=2020-01-01&amount=1000 -> 폼 프리필
- 결과로 자동 스크롤

## 4. 시그널
- /signals 페이지 -> 포지션 있으면 시그널 카드 표시
- Positive/Negative/Neutral 필터

## 5. Discover
- /discover -> 종목 스캔 결과 표시 (50+ 종목)

## 6. Watchlist
- AAPL 검색 -> 추가 -> 목록에 표시 -> 삭제

## 7. Settings
- 언어 토글 (한/영)
- 프로필 표시
- 로그아웃

## 8. 모바일 (375x812)
- Bottom nav 모든 탭
- 메뉴 시트 열기/닫기
- 포트폴리오 추가 모달

## 9. 엣지 케이스
- 빈 입력으로 검색
- 존재하지 않는 티커 "ZZZZZ"
- 수량 0 / 음수 / 소수점
- 단가 0 / 음수
- 극단적 금액 ($0.01, $999,999,999)
