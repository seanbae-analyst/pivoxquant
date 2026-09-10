# PivoxQuant — `scripts/` cron & one-shot utilities

Operational scripts triggered by Claude Code scheduled-tasks (Max plan, $0)
or run on-demand by the CEO. Zero non-stdlib deps wherever practical.

## CAUS — 폐기됨 (2026-09-01)

Continuous Autonomous User Simulation(브라우저 sim 유저 1명/일 + Playwright
시나리오 10종)은 **삭제됐다.** 시나리오가 겨냥하던 URL 10개 중 9개가 8-31 prune
으로 사라져서, 매일 도는 QA 가 **없는 제품을 검사하고 있었다** (`/signals`
`/watchlist` `/reports` `/pricing` `/simulator/what-if` `/features` `/risk`
`/companion` `/home` — 전부 삭제됨). 남아 있던 건 오탐뿐이라 CEO 결정으로 retire.

함께 삭제된 것: `caus_daily_sweep.py` · `caus_auto_fix.py` · `caus_scenarios/`
· `check_caus_today.sh` · `routes/sim_onboard.py` · 스케줄러의
`ops_caus_daily_sweep` · 테스트 4종 · `docs/qa/auto-sim-reports/`(43건) ·
`docs/specs/continuous-user-sim-spec.md` · `playwright` 의존성.

**남긴 것**: `users.is_simulated` 컬럼 + migration 032 + 이메일/푸시의
`is_simulated` 가드. `scripts/qa/virtual_user_sweep.py` 가 아직 sim 유저를
만들고, 그 가드가 **합성 유저에게 실제 메일이 나가는 걸 막는다.**
합성 유저 QA 가 필요하면 이제 그쪽이 유일한 경로다.

## Other cron scripts

> 2026-08-31 프룬: 삭제된 화면(alerts / signals / reports·artifact)을 위해서만
> 존재하던 `check_price_alerts.py` · `seed_alerts.py` · `run_benchmark_backtest.py`
> 는 제거됨. 실제 스케줄의 SoT 는 `services/scheduler/cron_jobs.py` 다.

| Script | Cadence | Purpose |
|--------|---------|---------|
| `pivox_report.py` | on-demand (CEO) | 본인 토스증권 계좌를 read-only 로 읽어 거울 리포트 → `reports/personal/`. 유저 기능 아님. `docs/ops/toss-personal-report.md` |
| `morning_brief/build_brief_kpi.py` | Daily 06:00 KST | CEO morning brief (KPI) |
| `nightly/*.py` | Daily 02:00~ KST | ops 점검 (db backup, ssl, env, error-rate, 이메일 컴플라이언스 등) |
| `legal_monitor/*.py` | Daily 09:00 KST | Regulatory change scanner |
| `legal/lawyer_packet_build.py` | Weekly | 변호사 패킷 빌드 |

All run inside Claude Code scheduled-tasks (Max plan) — see
`docs/AUTONOMOUS_OPS.md` for the orchestration overview.
