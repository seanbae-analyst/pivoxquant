"""services.reports — 유저 본인 기록으로 만드는 리포트 렌더러.

현재 식구는 월간 거울 리포트 하나뿐이다
(:mod:`services.reports.mirror_pdf`). 발송(라우트·크론·이메일)은 이 패키지
바깥의 일이고, 여기에는 **순수 조회 + 계산 + 렌더**만 산다.

이 패키지의 규칙 — 새 모듈을 붙일 때도 그대로 지킨다:

* 점수·등급·순위 금지. ``services.behavior.scorer`` 를 import 하지 않는다.
* 추천·조언 금지. 관측한 사실만 적는다 (자본시장법 §49).  // legal-ok
* 외부 시세 금지. 유저가 직접 기록한 체결가·수량만 쓴다 (FMP 약관 §2.2.2).
* 면책 문구는 :mod:`services.legal.disclaimers` SoT 에서만 가져온다.
"""
