# PivoxQuant TODO 통합 문서

> 2026-04-19 cleanup 패스에서 코드베이스 전체의 TODO/FIXME/DEPRECATED
> 주석을 모아 정리한 문서. 해결 시 해당 주석과 본 항목을 함께 제거할 것.

---

## Bug / 정합성 (2)

- [ ] `routes/counterfactual.py:486` — **TODO(fx-historical)**: counterfactual
      시뮬레이션이 ingress/egress 양쪽에 현재 USD/KRW 환율을 사용. 과거 시점
      환율로 보정해야 과거 원화 손익이 정확.
      (동일 이슈 참조: 같은 파일 line 736 주석)

- [ ] `routes/autotrade.py:22` — **TODO(multi-user)**: autotrader 싱글턴을
      직접 변이하는 구조가 멀티유저 환경에서 안전하지 않음. 유저별 분리
      필요.

## Enhancement (3)

- [ ] `services/thesis_service.py:86` — `price_change_30d=0.0` 하드코딩.
      스냅샷에서 계산해서 채워야 함.

- [ ] `services/thesis_service.py:87` — `recent_news=""` 하드코딩. 뉴스
      서비스에서 fetch 해 와야 함.

- [ ] `security.py:366` — 프론트엔드 CSP에서 `'unsafe-inline'` 제거
      (script-src, style-src). Next.js nonce 도입 필요.

## Refactor / Deployment (2)

- [ ] `routes/__init__.py:47` — agent_worker를 메인 이미지에 번들링하거나
      별도 서비스로 분리. 현재는 로컬 개발 시 별도 프로세스 필요.

- [ ] `routes/artifacts.py:274` — **DEPRECATED**: per-type weekly-memo/
      brag-card/earnings-prebrief 라우트는 QA/legacy 용도로만 유지.
      프론트 호출이 모두 `/api/artifacts/list|download|preview`로 이전
      되면 제거.

---

## 이미 처리된 항목

_(이 섹션은 처리할 때마다 옮겨서 append)_
