"""Tax-computation helpers (pure, deterministic, test-friendly).

Currently houses the Korean overseas-equity capital-gains (해외주식 양도소득세)
estimator used by the profile CSV export. Strictly a *calculation/record*
surface — it produces raw computed facts (realised P&L, estimated tax) from the
user's own stored trades. It gives NO advice, NO 절세 전략, NO filing service.
"""
