# PivoxQuant 서비스 개요 (변호사 자문 첨부 자료)

**작성일**: 2026-05-18
**대상**: 금융규제·자본시장법 전문 변호사
**목적**: PivoxQuant 서비스 구조 이해 → Q1-Q15 자문 의견서 작성 기반 자료

---

## 1. 사업자 정보 (사업자등록증 발급 완료 2026-05-08)

| 항목 | 값 |
|---|---|
| **등록번호** | 459-01-03808 |
| **상호** | 피복스퀀트 (PivoxQuant) |
| **대표자** | 배상현 (생년월일 2004-01-15) |
| **개업일** | 2026-05-08 |
| **사업장 소재지** | 서울특별시 성동구 독서당로 272, 107동 401호 (금호동4가, 금호동대우아파트) |
| **과세유형** | 일반과세자 |
| **업태** | 정보통신업 |
| **종목** | 영상물 제공 서비스업 / 오디오물 제공 서비스업 / **데이터베이스 및 온라인 정보 제공업** |
| **발급기관** | 성동세무서장 |
| **사업자등록증 PDF** | `/Users/seanbae/Desktop/취준/사업자등록증-pivoxquant.pdf` (별도 첨부) |

**관련 변호사 자문**: Q5 (사업자등록 미완 상태 가격 광고 회피), Q8 (업태 적합성 — 전자상거래업 추가 등재 필요성)

---

## 2. 핵심 비즈니스 모델

### 2.1 컨셉 — "User as CFO"
- 사용자 본인 데이터(포트폴리오·거래 내역) 기반 **AI Artifact 자동 생성·발송** 서비스
- **챗봇/대화형 X** — 정기 발송형 (단방향 푸시)
- Personal Capital 모델(미국 PFM 도구) 한국 변형 — **자기 데이터 한정 PFM 도구**로 포지셔닝
- 자본시장법 §101 면제 트랙 정합 (별첨 `section-101-exemption-decision.md` 참조)

### 2.2 AI Artifact 17종 (자동 생성 컨텐츠)
대표 예시:
- **Weekly Memo** — 매주 일요일 사용자 포트폴리오 주간 요약(이메일 + PDF 링크)
- **Brag Card** — 사용자 거래 성과 시각화 카드
- **Earnings Pre-Brief** — 사용자 보유 종목 실적 발표 전 정리
- 그 외 14종 (Risk Snapshot, Sector Drift, Companion Note 등)

**핵심 제약** (§101 면제 트랙 방어선):
- 모든 Artifact = **본인 보유 종목 한정** 분석
- 불특정 다수 대상 정보 제공 X
- 1:1 자문 X
- "이 종목 매수/매도" 직접 권유 X (forbidden_terms.py 필터)

### 2.3 사용자 흐름
1. 가입 → OAuth (Google/Kakao)
2. 20문항 questionnaire → 8 페르소나 분류
3. portfolio 등록 (KIS API 연동 또는 수동 입력)
4. **매주 일요일 Weekly Memo 자동 발송** (이메일 + PDF link)
5. 결제 → tier 활성화 (Stripe)

### 2.4 결제 구조 (3-tier)
| Tier | 가격 | 기능 |
|---|---|---|
| Free | ₩0 | Weekly Memo 1회/월 |
| Pro | **₩9,900/월** | Weekly Memo 주 1회 + Artifact 17종 일부 |
| Premium | **₩19,900/월** | 전 기능 + Earnings Pre-Brief + 실시간 알림 |

**관련 변호사 자문**: Q11 (Free 사용자 손해배상 한도 무효 가능성), Q15 (가분적 디지털콘텐츠 환불)

---

## 3. 기술 스택 (Tech Stack)

| 영역 | 기술 |
|---|---|
| Frontend | Next.js 16 (React), TypeScript, Tailwind 4, PWA |
| Backend | **Flask 3 + SQLAlchemy + gunicorn** (NOT Supabase) |
| DB | **PostgreSQL on Railway** |
| Auth | Authlib OAuth (Google/Kakao) + Flask-Login session |
| Hosting | Vercel (frontend), Railway (backend + DB) |
| Realtime | SSE (Server-Sent Events) via Flask |
| Payment | **Stripe Live** (KRW) |

**도메인**: https://pivoxquant.com

**해외 이전 데이터 처리자 (PIPA §28-8 대상)**:
- Anthropic (Claude API, US) — AI Artifact 생성
- Stripe (US) — 결제 처리
- Railway (US) — 백엔드/DB 호스팅
- Vercel (US) — 프론트엔드 호스팅

**관련 변호사 자문**: Q6 (Cross-border 동의 PIPA §28-8 + GDPR 충족 여부)

---

## 4. 데이터 소스 (공식 라이선스만)

**원칙**: yfinance/pykrx/네이버 finance 등 **비공식 스크래핑 영구 금지** (메모리 룰 `feedback_official_data_only`)

| 데이터 | 소스 |
|---|---|
| 한국 주식 시세 | **KIS API** (한국투자증권 공식) |
| 한국 기업 공시 | **DART OpenAPI** (금감원 공식) |
| KOSPI 지수 등 | **KRX Open Data Portal** (정부 공식) |
| 미국 주식 | Alpaca (BYO 키, read-only) |

---

## 5. 법적 포지셔닝 요약

### 5.1 자본시장법 §101 면제 트랙 유지 결정 (2026-05-04 CEO 확정)
- 유사투자자문업 신고/등록 안 함
- 4요건 정합성: 광고 없음 / 매월 청구 없음 / 특정성 회피 / 일반화된 정보 제공만
- 상세: 별첨 `section-101-exemption-decision.md`

### 5.2 신규 규제 7건 대응 (2026-04~05 스캔)
- HIGH 3건 (정통망법 §50 6% 과징금 / 유사투자자문업 양방향 채널 / AI 생성물 표시제)
- MEDIUM 3건 (PIPA 10% 과징금 / 금소법 6대 원칙 / 전자상거래법 가분적 디지털콘텐츠)
- LOW 1건 (KRX 라이선스)
- 상세: 별첨 `regulatory-impact-2026-05.md`

### 5.3 변호사 자문 큐 Q1-Q15
- P0 5건 (출시 차단 — 유료 결제 시작 전 필수)
- P1 6건 (출시 권고 fix)
- 시행령 추적 1건 + 마이데이터 회색지대 4건
- 상세: 별첨 `legal-questions-q1-q15.md`

---

## 6. 출시 일정

- **현재 상태**: 출시 D-day 임박 (2026-05-?)
- **베타테스터 계획**: 100명
- **차단 요인**: 변호사 의견서 수령 후 Stripe Live 활성화 진행
- 예상 의견서 비용: 300-500만원 (Q1-Q15 일괄)

---

## 7. 변호사 검토 요청 핵심 포인트

1. **§101 면제 트랙 정합성 사인** — 본 서비스 구조가 자본시장법 §101 면제 4요건 충족하는지
2. **업태 적합성** — 정보통신업/데이터베이스 단일 업태로 SaaS 유료결제 가능 여부 (전자상거래업 추가 등재 필요?)
3. **양방향 채널 해당 여부** — Artifact 단방향 푸시 vs 챗봇 인터페이스 경계선
4. **AI 생성물 표시제** — Artifact 라벨링 방식 (워터마크/자막/텍스트)
5. **약관 갱신 방향** — Free 손해배상 한도 분리 + 가분적 디지털콘텐츠 환불 정책

---

**관련 첨부 파일 (본 디렉터리)**:
- `service-overview.md` (본 문서)
- `section-101-exemption-decision.md` — §101 면제 트랙 결정문
- `regulatory-impact-2026-05.md` — 신규 규제 7건 영향도
- `legal-questions-q1-q15.md` — 변호사 자문 큐 Q1-Q15 정리본
- `README.md` — 사용법 + PDF 변환 가이드

**별도 첨부 (PDF)**:
- `사업자등록증-pivoxquant.pdf` (CEO 보유, `/Users/seanbae/Desktop/취준/`)
- 서비스 화면 — https://pivoxquant.com 라이브 접속
