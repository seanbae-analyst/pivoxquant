# Analytics Skills
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


## kpi-track
- KPI 추적: 핵심 지표 모니터링
- `DAU, MAU, 리텐션, 거래량, 전환율`

## data-query
- 데이터 쿼리: Supabase SQL 분석
- `유저 행동, 매매 패턴, 기능 사용률`

## dashboard-build
- 대시보드 구축: 데이터 시각화
- `차트, 그래프, 실시간 메트릭`

## cohort-analysis
- 코호트 분석: 사용자 그룹별 행동 비교
- `가입 시기별, 요금제별, 활성도별`
