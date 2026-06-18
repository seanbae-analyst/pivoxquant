# Virtual-user sweep — 2026-06-11

- users: 20 (8 personas × free/pro/premium × 8 portfolio archetypes)
- HTTP calls: 991 (in-process test client, isolated SQLite, ₩0)
- started: 2026-06-11T14:39:12.636267+00:00
- findings: 40 (P0 0 / P1 0 / P2 0 / P3 40)

## Findings

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu1[growth/free/empty]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu1[growth/free/empty]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu2[value/free/empty]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu2[value/free/empty]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu3[balanced/pro/kr_only]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu3[balanced/pro/kr_only]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu4[income/premium/kr_only]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu4[income/premium/kr_only]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu5[quant/free/kr_only]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu5[quant/free/kr_only]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu6[beginner/free/us_only]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu6[beginner/free/us_only]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu7[speculator/pro/us_only]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu7[speculator/pro/us_only]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu8[daytrader/premium/us_only]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu8[daytrader/premium/us_only]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu9[growth/free/mixed]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu9[growth/free/mixed]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu10[value/free/mixed]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu10[value/free/mixed]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu11[balanced/pro/mixed]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu11[balanced/pro/mixed]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu12[income/premium/mixed]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu12[income/premium/mixed]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu13[quant/free/mixed]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu13[quant/free/mixed]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu14[beginner/free/mixed]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu14[beginner/free/mixed]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu15[speculator/pro/fractional]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu15[speculator/pro/fractional]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu16[daytrader/premium/fractional]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu16[daytrader/premium/fractional]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu17[growth/free/huge_qty]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu17[growth/free/huge_qty]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu18[value/free/one_share]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu18[value/free/one_share]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu19[balanced/pro/kosdaq]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu19[balanced/pro/kosdaq]`
  - {"code":"FORBIDDEN","error":"admin only"}

- **[P3] GET art-bymonth -> 400 (allowed [200])** — `vu20[income/premium/kosdaq]`
  - {"code":"INVALID_MONTH_FORMAT","error":"month must be YYYY-MM","error_kr":"month\ub294 YYYY-MM \ud615\uc2dd\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."}

- **[P3] GET inbox -> 403 (allowed [200, 204, 400, 404])** — `vu20[income/premium/kosdaq]`
  - {"code":"FORBIDDEN","error":"admin only"}

