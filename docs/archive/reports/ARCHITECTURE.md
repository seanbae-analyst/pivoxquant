# PivoxQuant — Architecture

Last updated: 2026-05-02 (partial reorg)

## Layout

```
pivoxquant/
├── app.py            # Flask create_app() factory
├── run.py             # Dev entry point (port 5050)
├── config.py          # Config classes
├── extensions.py      # Singleton db / login_manager
├── security.py        # CORS / RateLimit / CSRF / session
│
├── routes/            # Flask blueprints (38 files, 285+ endpoints)
├── models/            # SQLAlchemy ORM models
├── services/          # Business logic
│   ├── kis/           # ✅ KIS broker integration (consolidated 2026-05-02)
│   │   ├── service.py
│   │   ├── token_manager.py
│   │   └── websocket_service.py
│   ├── data/          # FMP / Alpaca adapters
│   ├── broker/        # Broker abstractions
│   ├── artifacts/     # PDF / email artifact pipelines
│   ├── profile/       # Investor profiling
│   ├── twin/          # AI twin
│   └── ...
│
├── migrations/        # Alembic
├── tests/             # pytest (1310+ cases)
├── frontend/          # Next.js 16
└── ...
```

## Top-level .py modules (not yet packaged)

The following modules sit at project root and are imported by 1–8 files each. They were **intentionally left in place** to keep this reorg bounded — moving them all touches ~70 importers and risks regressions.

| File | Importers | Logical group | Future home |
|---|---|---|---|
| `engine.py` | 4 | quant | `services/quant/` |
| `quant_models.py` | 6 | quant | `services/quant/` |
| `risk_defense.py` | 4 | quant | `services/quant/` |
| `risk_models.py` | 2 | quant | `services/quant/` |
| `portfolio_models.py` | 1 | quant | `services/quant/` |
| `signal_models.py` | 3 | quant | `services/quant/` |
| `backtester.py` | 4 | quant | `services/quant/` |
| `canslim.py` | 1 | quant | `services/quant/` |
| `indicators.py` | 1 | quant | `services/quant/` |
| `data_fetcher.py` | 7 | data | `services/data/` |
| `fmp_service.py` | 8 | data | `services/data/` |
| `edgar_service.py` | 3 | data | `services/data/` |
| `realtime_service.py` | 2 | data | `services/data/` |
| `ai_service.py` | 3 | ai | `services/ai/` |
| `ai_models.py` | 1 | ai | `services/ai/` |
| `investor_profiles.py` | 1 | profile | `services/profile/` |
| `questionnaire.py` | 1 | profile | `services/profile/` |
| `autotrader.py` | 1 | trading (disabled) | `services/trading/` |
| `daytrade_service.py` | 1 | trading | `services/trading/` |

## Reorg principles applied (2026-05-02)

1. **Bounded scope** — only one logical group migrated per pass (KIS).
2. **Backwards-compatible re-exports** — `services/kis/__init__.py` exposes the public symbols so callers can use either the explicit submodule or the package shortcut.
3. **Explicit re-exports**, not wildcard `from x import *`, so dead imports surface as TypeErrors at boot rather than silently disappearing.
4. **Test mock-paths updated** alongside imports — old `patch("kis_token_manager.requests.post")` rewrites became `patch("services.kis.token_manager.requests.post")`. Without this, tests would silently no-op and pass without exercising the patched code.

## Future migrations (deferred)

Each group above can be migrated independently using the same pattern:
1. `mkdir services/<group>/`
2. `git mv <root>.py services/<group>/<short>.py`
3. Add `services/<group>/__init__.py` with explicit re-exports.
4. `sed` rewrite imports across `routes/`, `services/`, `models/`, `tests/`, `migrations/`.
5. Update `patch("<old>.x")` mock paths in tests.
6. `pytest -q` — must stay green.
7. Commit per group.

Do **not** batch multiple groups into one commit — bisect-ability matters more than commit count.
