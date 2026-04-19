# 6. 기술 전략 — PWA + 인프라

## PWA-First 전략

### 왜 PWA인가

| 항목 | PWA | 네이티브 앱 |
|------|-----|------------|
| 개발 비용 | **0원** (Next.js 설정만) | iOS+Android 별도 개발 |
| 배포 속도 | 서버 업데이트 즉시 | 앱스토어 심사 1~7일 |
| 설치 장벽 | URL 접속만으로 사용 | 스토어 → 다운 → 설치 |
| SEO | 검색엔진 노출 가능 | 앱스토어 내부만 |
| 스토어 수수료 | **0%** | 인앱결제 30% |
| 유지보수 | 단일 코드베이스 | 플랫폼별 별도 |

### PWA 성과 데이터

- 설치율: 네이티브 대비 **10배 높음**
- 전환율: 네이티브 대비 **36% 높음**
- 세션 시간: 일반 웹 대비 **78% 더 김**
- Pinterest: 신규 가입 **843% 증가**

### 한국 시장 PWA 주의사항

| 브라우저 | PWA 지원 | 푸시 | 주의 |
|---------|---------|------|------|
| Chrome (Android) | O | O | 완벽 지원 |
| 삼성 인터넷 | O | O | minimal-ui 미지원 |
| Safari (iOS) | 홈화면 추가 | O (16.4+) | standalone 필수 |
| **카카오톡 인앱** | **X** | X | **외부 브라우저 리다이렉트 필수** |
| **네이버 인앱** | **X** | X | 동일 |

> 한국에서 URL 공유의 대부분이 카카오톡을 통해 이루어지므로, 인앱 브라우저 감지 → Chrome/삼성 브라우저 자동 리다이렉트 로직이 **런칭 필수 기능**.

### 앱스토어 배포

- **Android**: TWA로 Play Store 등록 가능 (PWABuilder 활용)
- **iOS**: 홈화면 추가 유도 UX 강화 (App Store 등록 불가)

---

## 데이터 소스 전략

### 데이터 소스 전환 완료

| 항목 | FMP (현재) | Alpaca (US primary) |
|------|-----------|---------------------|
| 유형 | 공식 REST API | 공식 REST API |
| 안정성 | SLA 보장 | SLA 보장 |
| 상업 이용 | 허용 | 허용 |
| 무료 한도 | 250회/일 | 무제한 (시세) |
| 유료 | $15~29/월 | $9/월 |

### 데이터 소스 로드맵

| 단계 | MAU | 소스 | 월 비용 |
|------|-----|------|---------|
| 초기 | 0~500 | Alpaca (US) + KIS (KR) + FMP (fallback) | 0원 |
| 성장 | 500~1K | FMP 유료 or Polygon ($29) | 2~4만원 |
| 스케일 | 1K+ | Polygon + FMP 병행 | 6~10만원 |

---

## 기술 스택

### 현재 → 프로덕션

| 영역 | 현재 | 프로덕션 |
|------|------|---------|
| Frontend | Next.js 16 (localhost:3000) | Vercel |
| Backend | Flask (localhost:5050) | Railway |
| DB | SQLite | Supabase PostgreSQL |
| Auth | Flask session | NextAuth.js (Google/Kakao) |
| AI | Claude Haiku | Claude Haiku (유저당 토큰 캡) |
| 시세 데이터 | Alpaca + FMP | Alpaca + FMP |
| 브로커 US | Alpaca paper | Alpaca paper → live |
| 브로커 KR | KIS 모의 | KIS 모의 → 실거래 |
| CI/CD | 없음 | GitHub Actions |
| 모니터링 | 없음 | Sentry + UptimeRobot |
| 분석 | 없음 | PostHog (무료) |

### 인프라 비용 (월)

| 서비스 | 무료 한도 | 초과 시 |
|--------|-----------|---------|
| Vercel | 100GB BW | $20/월 |
| Railway | $5 크레딧 | ~$12/월 |
| Supabase | 500MB DB | $25/월 |
| FMP | 250회/일 | $15~29/월 |
| Sentry | 5K events | $26/월 |
| PostHog | 1M events | $0 |

---

## 배포 체크리스트

### W1~W2
- [ ] PostgreSQL 마이그레이션 (SQLAlchemy → Supabase)
- [x] FMP API 연동 완료
- [ ] NextAuth.js 설정 (Google/Kakao OAuth)

### W2
- [ ] PWA manifest.json + service worker
- [ ] 카카오/네이버 인앱 브라우저 리다이렉트

### W3
- [ ] Railway Procfile 작성
- [ ] Vercel 연결 (GitHub repo)
- [ ] 환경변수 정리 (.env → platform secrets)
- [ ] CORS 설정 (프로덕션 도메인만)
- [ ] 도메인 연결 + SSL

### W4
- [ ] 토스페이먼츠 연동
- [ ] GitHub Actions CI 파이프라인
- [ ] Sentry 에러 모니터링
- [ ] 유저당 토큰 캡 구현
