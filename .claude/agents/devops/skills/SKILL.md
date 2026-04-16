# DevOps Skills
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


## deploy
- 배포: Vercel/Railway 배포 관리
- `빌드 확인, 환경변수, 프리뷰 배포`

## env-setup
- 환경 설정: 개발/스테이징/프로덕션 환경 구성
- `.env 관리, 시크릿 로테이션`

## monitoring
- 모니터링: 서비스 상태 및 에러 추적
- `Vercel Analytics, Railway 로그, Supabase 대시보드`

## db-migration
- DB 마이그레이션: 스키마 변경 관리
- `Supabase 마이그레이션, 롤백 계획`

## cost-optimize
- 비용 최적화: 인프라 비용 절감
- `프리티어 활용, 캐싱, CDN, 번들 최적화`
