# Inbox — 확인했지만 아직 문서 레코드로 안 올린 단서

규칙: 날짜 · 무엇 · 어디서 알았나 · 다음 행동. 문서로 올리면 여기서 지운다.
"웹 검색" 은 2차 자료(법무법인·언론) 요약이라 원문 확인 전까지 수치·문구를 인용하지 않는다.

## ⚠️ 덱 정정 — 발표 자료에 틀린 문장이 있었다 (2026-11-11 원문 대조)

- **슬라이드 14 노트 "FSB 최종본(10-15)에서 개별 식별자 문구가 빠졌다" 는 틀렸다.** 원문 PDF(https://www.fsb.org/uploads/P151026-1.pdf, 75쪽) §2.3 Attribution, PDF p.30:
  "Visibility assigns individual unique identifiers to each AI agent … Unique identifiers for agents allow them to be easily differentiated from human users".
  빠진 것은 협의안의 '합성 직원(synthetic employee)' 문구뿐(최종본 0건). → 코딩 `intl-fsb-ai-sound-practices-2026-10.unique_id` 를 true 로, 인벤토리(p.30·31)도 true 로 정정. 매트릭스 INTL 칸 점수는 그대로(1 — FSB 는 자율).
  **논문·제출본에서 이 문장을 고쳐야 한다.** 같은 PDF 로 확인: 위험기반 승인 트리거 p.56, kill-switch 구현·테스트 p.57, 목표·권한·데이터 분리 p.41.

## 덱(2026-11-01) 이후 — 논문 수치 갱신 필요

| 날짜 | 무엇 | 어디서 | 다음 행동 |
|---|---|---|---|
| 2026-11-05 | 금융위 全금융권 간담회 — **침해 37개사 40건, 약 47.3만 건 유출(11-03 기준)**, 약 580개사 외부접점·내부통제 전수점검, 대형사부터 취약점 평가 연 2회 의무화, "AI 공격은 AI 로 방어" 망분리 전면해제 논의 | 금융위 보도자료 88086 본문 실측 | 문서 등록 완료 (`kr-fsc-press-2026-11-05`). **덱 슬라이드 5 의 "16개사·약 10만 건" 은 10-14 기준** — 논문에선 기준일을 명시하고 11-05 수치를 병기 |
| 2026-09-10 | NYDFS — Part 500 리스크 평가 수행·활용 안내서한 + 보도자료 pr20260910 | `watch` nydfs-cyber 링크 | 문서 등록 완료(`us-nydfs-letter-2026-09-10`), 본문 미독 → 코딩 |
| 2026-10-22 | NYDFS Cybersecurity Alert — PHP 치명 취약점 즉시 패치 | `watch` nydfs-cyber 링크 | 패치 기한 선례(제안 ②) 로만 참고. 문서 등록은 보류 |
| 2026 | OCC *2026 Cybersecurity and Financial System Resilience Report* | `watch` occ-bulletins 링크 — https://www.occ.gov/publications-and-resources/publications/cybersecurity-and-financial-system-resilience/files/2026-cybersecurity-report.html | 에이전트 언급 여부 확인 → 있으면 report(binding 0) 로 등록 |
| 2026-10 | FSB Chair letter to G20 (2026-10) — AI 작업 언급 | `watch` fsb-publications | 최종 보고서 보조 자료. 등록 보류 |
| 2026-11-11 | nist.gov/caisi 페이지 제목이 "Center for Advancing Innovation and Standards for **Super Intelligence (CAISSI)**" 로 표기됨 | 2026-11-11 HTTP 200 실측 | 명칭 변경인지 확인. 논문에서 CAISI 표기 시점 주석 필요 |

## 덱에 없었던 2026 상반기 한국 문서 (맥락)

| 날짜 | 무엇 | 어디서 | 다음 행동 |
|---|---|---|---|
| 2026-05-26 | 금융위 「고성능 AI 관련 금융권 보안위협 대응 간담회」(05-22) — 보안목적 AI 활용 망분리 긴급 완화, 금융AI보안연구소 신설, 가이드라인 예고 | 금융위 보도자료 86972 본문 실측 | 연표에 맥락으로 넣을지 결정 |
| 2026-06-01 | 금융위 민간 기술자문단 발족 (AI·보안·법 7명, 12월까지) | 보도자료 87018 | 맥락 |
| 2026-06-10 | 금융위원장–5대 금융지주 「AX시대 해킹·보이스피싱 대응 간담회」 | 보도자료 87076 | 맥락 |
| 2026-07-02 | **「프런티어 AI 보안위협 금융분야 대응요령」 가이드라인 + AI 보안테스트·패치 전산장애 면책** | 보도자료 87240 본문 실측 | 문서 등록 완료(`kr-fsc-frontier-ai-guide-2026-07`). 가이드라인 본문(hwp/pdf 첨부) 받아 7개 통제 코딩 |
| 2026-09-16 | 프런티어 AI 보안위협 금융권 상황대응반 **제6차** 회의 (PG업권) | 보도자료 87727 | 상황대응반 1~6차 날짜를 모아 연표에 — "경고가 있었다" 논지의 1차 근거 |

## URL 을 못 찾은 것

- ~~금융위 2026-06-18 보도자료~~ → **찾음** https://www.fsc.go.kr/no010101/87142 (2026-11-11 2차 코더 보고 → HTTP 200·제목 직접 확인). 문서에 반영.
- ~~금보원 AI 에이전트 보안 평가기준 원문~~ → 보도자료 **찾음** https://www.fsec.or.kr/bbs/detail?menuNo=69&bbsNo=12122 (6분야 17항목 목록). 세부 기준 전문은 비공개 — 2026 「AI REDTEAM REPORT」 공개 예정. fnnews 의 '5분야' 는 보도자료의 '6분야' 와 다르다 — 1차 자료를 따른다.
- FINRA 2026 Oversight Report 의 AI 섹션 직접 링크 (…/artificial-intelligence 는 404).
- ~~금감원·금보원 2026 침투테스트 운영기준(04-29)~~ → 공동 보도자료 **찾음** https://www.fsec.or.kr/bbs/detail?menuNo=69&bbsNo=11944 (게시 04-30). 별도 운영기준 문서는 없음.
- 재무부 FS AI RMF 랜딩 URL 이 다른 페이지로 리다이렉트(2026-11-11). 2차 코더는 cyberriskinstitute.org 의 Guidebook 으로 읽었다 — 그 URL 은 직접 확인 전.
- 연준 SR 26-2 첨부 p.3 각주 3 — 생성형·에이전틱 AI 를 범위에서 뺀다고 명시(2차 코더가 원문으로 확인). '에이전트를 이름 붙여 제외' 한 구속력 문서의 사례.

## 교수·실무자 피드백에서 나온 추가 기준점 (등록 전 검토)

- **ISO/IEC 42001:2023** — 등록했지만 미독(`intl-iso-iec-42001-2023`, 전부 null). 유료 표준이라 요약본으로 코딩할지 결정.
- **TISAX AL3** — 자동차 산업 정보보안 평가(ENX). 금융 규제 비교엔 맞지 않아 등록 보류. 보안 담당자 인터뷰 인용 시 맥락으로만.
- 기업 보안 담당자 답변(2026-11)은 **1인 응답** — 인용하려면 본인 동의·익명화, 그리고 IRB 필요 여부 확인.
