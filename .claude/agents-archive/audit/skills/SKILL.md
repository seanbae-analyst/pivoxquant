# Audit Skills (Goldman Standard)
## ⚖️ Iron Rules (필수 — sub-skill 사용 시 절대 위반 금지)

1. **No assumption skipping** — "충돌 우려" "범위 밖일 듯" 같은 추측으로 스킵 금지. 의심되면 caller에게 escalate.
2. **Partial ≠ Complete** — 7개 중 4개만 끝났으면 "완료" 아님. INCOMPLETE 보고 + 남은 N개 명시.
3. **Reasoning ≠ Verification** — 도구 권한 거부됐으면 "수학적으로 검증" 금지. 즉시 "BLOCKED: <tool>" 명시 + 수동 검증 요청.
4. **Evidence required** — "OK" "정상" "통과" 보고 시 반드시 증거 첨부 (curl 응답 / file diff / build exit code / DOM snapshot).
5. **Brand: PivoxQuant** (NOT stockpilot) — 모든 출력 통일.
6. **Permission denied = ESCALATE** — 침묵 금지. "Bash 거부됨, 사용자 직접 실행 요청" 명시.

## 완료 보고 템플릿 (필수)

```
## ✅ Completion Checklist
- [ ] 항목 1: ✅완료/❌미완(이유)
- [ ] 항목 2: ...
- [ ] 모든 항목 verified (증거 첨부): ✅/❌

## Status: COMPLETE / INCOMPLETE / BLOCKED
```

---


## full-audit
- 전체 검수: 재무+기술+제품+법규 종합 검수
- `Goldman Standard 5단계 전수 검사, PASS/CONDITIONAL/FAIL 판정`

## financial-review
- 재무 검수: 수익 모델, 비용 구조, 런웨이 검증
- `Unit economics, 전환율 가정, 번레이트, 30% 버퍼 적용`

## risk-assessment
- 리스크 평가: 5대 리스크 카테고리 분석
- `Market/Regulatory/Technical/Operational/Reputational Risk`

## code-audit
- 코드 감사: 프로덕션 레디니스 검증
- `보안, 스케일링, 데이터 정합성, 장애 복구`

## deal-review
- 딜 리뷰: 파트너십, 계약, 투자 조건 검토
- `조건 분석, 숨겨진 리스크, 협상 포인트`

## pre-launch
- 출시 전 검수: Go/No-Go 최종 판정
- `체크리스트 전수 확인, 리스크 수용 여부 결정`

## stress-test
- 스트레스 테스트: 최악의 시나리오 시뮬레이션
- `유저 0명, API 장애, 규제 변경, 자금 소진 시나리오`

## numbers-check
- 숫자 검증: 모든 수치/추정/예측 크로스체크
- `출처 확인, 가정 검증, 보수적 재계산`
