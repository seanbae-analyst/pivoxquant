"""
PivoxQuant — S&P 500 Benchmark Backtest (5-year)
=================================================

Runs three PivoxQuant quant strategies vs SPY baseline on 5+ years of daily data.

Data source: yfinance (free, adjusted OHLCV, no API budget concern).
Universe: 30 S&P 500 mega-caps + sector reps (frozen list; survivorship bias acknowledged).
Benchmark: SPY (and QQQ for reference).

Strategies:
  A) Quant Score Top-N monthly rebalance (PivoxQuant 4-pillar scoring)
  B) Strategy A + Risk-Defense overlay (VIX + drawdown based cash raising)
  C) Multi-Model (TSMOM momentum + MeanReversion bands blended)

Outputs:
  tests/backtest_results/equity_curves.png
  tests/backtest_results/drawdown.png
  tests/backtest_results/monthly_heatmap.png
  tests/backtest_results/rolling_sharpe.png
  tests/backtest_results/metrics.json
  docs/BACKTEST_RESULTS.md

Design rules (per Iron Rules):
  - engine.py / quant_models.py / risk_defense.py READ-ONLY (reuse Backtester._calc_score)
  - Transaction cost 0.1% (commission proxy) + 0.1% slippage round-trip = 0.2% per turnover
  - Sharpe uses rf=4.5% (US Treasury 5Y avg 2021-2026)
  - No look-ahead: score at month-end T uses data <= T only; holding is T+1..next rebal
  - Price data is adjusted close (yfinance auto_adjust=True) — splits + dividends handled
  - Sanity: SPY expected 5Y CAGR ~10-12%, Sharpe ~0.5-0.8. Anomaly if outside.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Project root so we can import the real PivoxQuant scoring
ROOT = Path("/Users/seanbae/Desktop/취준/stockpilot")
sys.path.insert(0, str(ROOT))

# Load .env for Alpaca/FMP keys so DataFetcher can authenticate
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

# Matplotlib — headless
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

OUT_DIR = ROOT / "tests" / "backtest_results"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Universe — S&P 500 mega-caps + sector reps (frozen as of 2026-04).
# Survivorship bias: these are names that exist today; we do NOT replay delisted
# constituents. Disclosed in the report.
# ──────────────────────────────────────────────────────────────────────────────
UNIVERSE = [
    # Tech (heavy weight since S&P is tech-heavy)
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "ORCL",
    "ADBE", "CSCO", "CRM", "INTC", "AMD",
    # Financials
    "JPM", "BAC", "WFC", "GS", "V", "MA",
    # Health care
    "JNJ", "UNH", "LLY", "PFE", "MRK",
    # Consumer
    "WMT", "HD", "PG", "KO", "PEP", "MCD", "COST",
    # Energy / Industrials / Staples / Utilities
    "XOM", "CVX", "CAT", "BA", "HON",
    # Comm / Media
    "NFLX", "DIS", "T",
]
BENCHMARKS = ["SPY", "QQQ"]
ALL_TICKERS = UNIVERSE + BENCHMARKS

START = "2020-12-01"   # ~5y lookback + warmup
END   = "2026-04-18"   # data as of report
RF_RATE = 0.045        # annual risk-free (US 5Y avg 2021-2026)
TOP_N = 15             # number of stocks held each month (equal-weight)
ROUND_TRIP_COST = 0.002  # 0.1% commission + 0.1% slippage


# ──────────────────────────────────────────────────────────────────────────────
# Data fetch
# ──────────────────────────────────────────────────────────────────────────────
def fetch_prices() -> dict:
    """Return dict of DataFrames (close/high/low/open/volume), index=date UTC-naive,
    columns=ticker. Uses PivoxQuant DataFetcher -> Alpaca (US, no rate limit)."""
    from data_fetcher import DataFetcher
    fetcher = DataFetcher()

    print(f"[data] downloading {len(ALL_TICKERS)} tickers via Alpaca (5y) ...")
    closes, highs, lows, opens, vols = {}, {}, {}, {}, {}
    for tk in ALL_TICKERS:
        try:
            h = fetcher.get_price_history(tk, period="5y")
            if h is None or h.empty:
                print(f"  {tk}: no data")
                continue
            # Normalize index to tz-naive midnight date for joining
            idx_raw = pd.to_datetime(h.index).tz_localize(None) if h.index.tz is not None else pd.to_datetime(h.index)
            idx = idx_raw.normalize()  # strip time component -> midnight
            closes[tk] = pd.Series(h["Close"].values, index=idx)
            highs[tk]  = pd.Series(h["High"].values, index=idx)
            lows[tk]   = pd.Series(h["Low"].values, index=idx)
            opens[tk]  = pd.Series(h["Open"].values, index=idx)
            vols[tk]   = pd.Series(h["Volume"].values, index=idx)
        except Exception as e:
            print(f"  {tk}: error {e}")

    close_df = pd.DataFrame(closes)
    # Normalize: keep daily timestamps, sort
    close_df = close_df.sort_index()
    high_df  = pd.DataFrame(highs).reindex(close_df.index)
    low_df   = pd.DataFrame(lows).reindex(close_df.index)
    open_df  = pd.DataFrame(opens).reindex(close_df.index)
    vol_df   = pd.DataFrame(vols).reindex(close_df.index)

    print(f"[data] usable tickers: {close_df.shape[1]}  rows: {close_df.shape[0]}")
    print(f"[data] date range: {close_df.index.min().date()} .. {close_df.index.max().date()}")
    return {"close": close_df, "high": high_df, "low": low_df, "volume": vol_df, "open": open_df}


# ──────────────────────────────────────────────────────────────────────────────
# Scoring — reuse Backtester._calc_score (the real PivoxQuant quant score)
# ──────────────────────────────────────────────────────────────────────────────
from backtester import Backtester  # noqa: E402


def score_asof(bundle: dict, ticker: str, asof: pd.Timestamp) -> float | None:
    """Compute PivoxQuant quant score using data <= asof (no look-ahead)."""
    try:
        c = bundle["close"][ticker].loc[:asof].dropna().values
        if len(c) < 260:   # need enough for TSMOM/52wk
            return None
        h = bundle["high"][ticker].loc[:asof].dropna().values
        l = bundle["low"][ticker].loc[:asof].dropna().values
        v = bundle["volume"][ticker].loc[:asof].dropna().values
        o = bundle["open"][ticker].loc[:asof].dropna().values
        n = min(len(c), len(h), len(l), len(v), len(o))
        c, h, l, v, o = c[-n:], h[-n:], l[-n:], v[-n:], o[-n:]
        return float(Backtester._calc_score(c, h, l, v, is_korean=False, opens=o))
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Regime / Risk-Defense overlay (Strategy B)
# Simplified VIX proxy: SPY realized vol 20d. When spikes > threshold, raise cash.
# Mirrors risk_defense.py philosophy without importing (read-only rule).
# ──────────────────────────────────────────────────────────────────────────────
def spy_realized_vol(spy_close: pd.Series, asof: pd.Timestamp, window: int = 20) -> float:
    s = spy_close.loc[:asof].pct_change().dropna().tail(window)
    if len(s) < window:
        return 0.15
    return float(s.std() * np.sqrt(252))


def equity_cash_ratio(vol_ann: float, spy_dd: float) -> float:
    """
    Translate vol + drawdown into an equity exposure fraction.
    Mirrors risk_defense.py 7-Layer principle: more risk -> less equity.
      low vol / low dd  -> 1.00
      mid vol / mid dd  -> 0.80
      high vol / deep dd -> 0.50
      crisis            -> 0.30
    """
    exposure = 1.0
    if vol_ann > 0.35:    # ~VIX > 35
        exposure = min(exposure, 0.50)
    elif vol_ann > 0.25:
        exposure = min(exposure, 0.75)
    elif vol_ann > 0.18:
        exposure = min(exposure, 0.90)

    if spy_dd < -0.20:
        exposure = min(exposure, 0.40)
    elif spy_dd < -0.10:
        exposure = min(exposure, 0.70)
    return max(0.30, exposure)


# ──────────────────────────────────────────────────────────────────────────────
# TSMOM + MeanReversion blend (Strategy C)
# ──────────────────────────────────────────────────────────────────────────────
def tsmom_mr_score(bundle: dict, ticker: str, asof: pd.Timestamp) -> float | None:
    """12-month return - 1-month return, standardized (Moskowitz TSMOM + MR tilt)."""
    try:
        c = bundle["close"][ticker].loc[:asof].dropna()
        if len(c) < 260:
            return None
        r_12m = c.iloc[-1] / c.iloc[-252] - 1    # 12-month momentum
        r_1m  = c.iloc[-1] / c.iloc[-21]  - 1    # short-term (we AVOID chasing)
        # MeanReversion tilt: z-score last 20d
        rets = c.pct_change().dropna().tail(60)
        z = (rets.iloc[-1] - rets.mean()) / (rets.std() + 1e-9)
        # Composite: momentum minus short-term chase minus positive z (overbought)
        return float(r_12m - 0.5 * r_1m - 0.15 * z)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Portfolio backtest engine — monthly rebalance, equal-weight top-N
# ──────────────────────────────────────────────────────────────────────────────
def run_portfolio(
    bundle: dict,
    scoring_fn,
    name: str,
    top_n: int = TOP_N,
    overlay: bool = False,
) -> pd.Series:
    """
    Returns daily equity curve (starting at 1.0) as a pd.Series indexed by date.
    Monthly rebalance on last business day of each month.
    """
    closes = bundle["close"][UNIVERSE].dropna(how="all")
    spy    = bundle["close"]["SPY"].dropna()
    dates  = closes.index

    # Rebalance on the LAST trading day of each month that exists in our index.
    # resample("ME").last() returns the value on the last trading day but labels
    # it with the month-end calendar date, which may not be in our index — so we
    # work with a set of actual trading-day-rebalance-dates.
    months = closes.index.to_series().groupby(pd.Grouper(freq="ME")).last()
    rebalance_days = set(pd.to_datetime(months.values))
    # Start rebalancing after 1-year warmup (need 252 bars for TSMOM/52wk)
    warmup_cutoff = pd.Timestamp(START) + pd.Timedelta(days=365)
    rebalance_days = {d for d in rebalance_days if d >= warmup_cutoff}

    equity = 1.0
    curve = {}
    current_weights: dict[str, float] = {}   # ticker -> weight of portfolio
    last_rebalance = None

    # Track SPY peak for drawdown overlay
    spy_peak = spy.iloc[0]

    for t in dates:
        if t < warmup_cutoff:
            continue

        # Is this a rebalance day? (last trading day of the month, or first bar after warmup)
        is_rebal = (last_rebalance is None) or (t in rebalance_days)
        if is_rebal:
            # Compute scores as of prior close
            asof = t
            scored = []
            for tk in UNIVERSE:
                s = scoring_fn(bundle, tk, asof)
                if s is not None:
                    scored.append((tk, s))

            if not scored:
                # Hold whatever we had
                if last_rebalance is None:
                    curve[t] = equity
                    last_rebalance = t
                    continue
            else:
                scored.sort(key=lambda x: x[1], reverse=True)
                top = [tk for tk, _ in scored[:top_n]]

                # Overlay — cash fraction
                if overlay:
                    spy_peak = max(spy_peak, spy.loc[asof])
                    spy_dd = spy.loc[asof] / spy_peak - 1.0
                    vol = spy_realized_vol(spy, asof)
                    eq_frac = equity_cash_ratio(vol, spy_dd)
                else:
                    eq_frac = 1.0

                new_weights = {tk: eq_frac / len(top) for tk in top}

                # Transaction cost on turnover
                if last_rebalance is not None:
                    all_tk = set(new_weights) | set(current_weights)
                    turnover = sum(
                        abs(new_weights.get(tk, 0) - current_weights.get(tk, 0))
                        for tk in all_tk
                    )
                    # One-way cost — we charge half the round-trip on the turnover
                    equity *= (1.0 - 0.5 * ROUND_TRIP_COST * turnover)

                current_weights = new_weights
                last_rebalance = t

        # Mark-to-market using daily returns
        if last_rebalance is not None and t > last_rebalance:
            try:
                prev_idx = dates.get_loc(t) - 1
                if prev_idx < 0:
                    continue
                t_prev = dates[prev_idx]
                port_ret = 0.0
                for tk, w in current_weights.items():
                    c_now = closes[tk].get(t)
                    c_prev = closes[tk].get(t_prev)
                    if pd.isna(c_now) or pd.isna(c_prev) or c_prev == 0:
                        continue
                    port_ret += w * (c_now / c_prev - 1.0)
                # Cash portion earns rf / 252
                cash_w = max(0.0, 1.0 - sum(current_weights.values()))
                port_ret += cash_w * (RF_RATE / 252)
                equity *= (1.0 + port_ret)
            except Exception:
                pass

        curve[t] = equity

    s = pd.Series(curve, name=name).sort_index()
    return s


def buy_hold(bundle: dict, ticker: str) -> pd.Series:
    c = bundle["close"][ticker].dropna()
    start = pd.Timestamp(START) + pd.Timedelta(days=365)
    c = c[c.index >= start]
    return (c / c.iloc[0]).rename(ticker)


# ──────────────────────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────────────────────
def annualize_return(eq: pd.Series) -> float:
    n_years = (eq.index[-1] - eq.index[0]).days / 365.25
    return (eq.iloc[-1] / eq.iloc[0]) ** (1 / n_years) - 1


def max_drawdown(eq: pd.Series) -> float:
    peak = eq.cummax()
    dd = eq / peak - 1.0
    return dd.min()


def metrics(eq: pd.Series, benchmark: pd.Series | None = None) -> dict:
    daily = eq.pct_change().dropna()
    if len(daily) < 2:
        return {}
    mean_ann = daily.mean() * 252
    vol_ann = daily.std() * np.sqrt(252)
    sharpe = (mean_ann - RF_RATE) / vol_ann if vol_ann > 0 else 0
    downside = daily[daily < 0]
    sortino = (mean_ann - RF_RATE) / (downside.std() * np.sqrt(252)) if len(downside) > 1 else 0
    mdd = max_drawdown(eq)
    calmar = (mean_ann) / abs(mdd) if mdd < 0 else 0

    total_ret = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = annualize_return(eq)

    monthly_eq = eq.resample("M").last()
    monthly_ret = monthly_eq.pct_change().dropna()
    best_month = monthly_ret.max()
    worst_month = monthly_ret.min()

    out = {
        "total_return": round(float(total_ret) * 100, 2),
        "cagr": round(float(cagr) * 100, 2),
        "sharpe": round(float(sharpe), 2),
        "sortino": round(float(sortino), 2),
        "calmar": round(float(calmar), 2),
        "max_drawdown": round(float(mdd) * 100, 2),
        "volatility": round(float(vol_ann) * 100, 2),
        "best_month": round(float(best_month) * 100, 2),
        "worst_month": round(float(worst_month) * 100, 2),
    }

    if benchmark is not None:
        bench = benchmark.reindex(eq.index).ffill()
        bench_daily = bench.pct_change().dropna()
        joined = pd.concat([daily, bench_daily], axis=1).dropna()
        joined.columns = ["strat", "bench"]
        if len(joined) > 30:
            cov = np.cov(joined["strat"], joined["bench"])
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0
            bench_ann = joined["bench"].mean() * 252
            alpha = (mean_ann - RF_RATE) - beta * (bench_ann - RF_RATE)
            active = joined["strat"] - joined["bench"]
            ir = (active.mean() * 252) / (active.std() * np.sqrt(252)) if active.std() > 0 else 0
            # Monthly win rate vs bench
            m_strat = eq.resample("M").last().pct_change().dropna()
            m_bench = benchmark.reindex(eq.index).ffill().resample("M").last().pct_change().dropna()
            mm = pd.concat([m_strat, m_bench], axis=1).dropna()
            mm.columns = ["s", "b"]
            wr = (mm["s"] > mm["b"]).mean() if len(mm) else 0
            out.update({
                "beta": round(float(beta), 2),
                "alpha": round(float(alpha) * 100, 2),
                "information_ratio": round(float(ir), 2),
                "monthly_win_rate_vs_spy": round(float(wr) * 100, 1),
            })

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Plotting
# ──────────────────────────────────────────────────────────────────────────────
def plot_equity(curves: dict[str, pd.Series], path: Path):
    plt.figure(figsize=(12, 6))
    for name, s in curves.items():
        plt.plot(s.index, s.values, label=name, linewidth=1.8)
    plt.title("PivoxQuant vs S&P 500 — Equity Curve (5Y)", fontsize=14, fontweight="bold")
    plt.xlabel("Date"); plt.ylabel("Growth of $1")
    plt.legend(loc="upper left")
    plt.grid(alpha=0.3)
    plt.gca().xaxis.set_major_locator(mdates.YearLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def plot_drawdown(curves: dict[str, pd.Series], path: Path):
    plt.figure(figsize=(12, 4.5))
    for name, s in curves.items():
        dd = (s / s.cummax() - 1.0) * 100
        plt.plot(dd.index, dd.values, label=name, linewidth=1.4)
    plt.title("Drawdown (%) — PivoxQuant vs SPY", fontsize=13, fontweight="bold")
    plt.xlabel("Date"); plt.ylabel("Drawdown %")
    plt.axhline(0, color="black", linewidth=0.5)
    plt.legend(loc="lower left")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def plot_monthly_heatmap(eq: pd.Series, path: Path, title="Monthly Returns"):
    m = eq.resample("M").last().pct_change().dropna() * 100
    df = pd.DataFrame({
        "year": m.index.year,
        "month": m.index.month,
        "ret": m.values,
    })
    pivot = df.pivot(index="year", columns="month", values="ret")
    plt.figure(figsize=(10, 4 + 0.3 * len(pivot)))
    vmax = max(abs(pivot.min().min()), abs(pivot.max().max()))
    plt.imshow(pivot.values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    plt.colorbar(label="Return %")
    plt.xticks(range(12), ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
    plt.yticks(range(len(pivot)), pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                plt.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8)
    plt.title(title, fontweight="bold")
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def plot_rolling_sharpe(curves: dict[str, pd.Series], path: Path, window=252):
    plt.figure(figsize=(12, 4.5))
    for name, s in curves.items():
        r = s.pct_change().dropna()
        roll = r.rolling(window).apply(
            lambda x: (x.mean() * 252 - RF_RATE) / (x.std() * np.sqrt(252)) if x.std() > 0 else 0,
            raw=False,
        )
        plt.plot(roll.index, roll.values, label=name, linewidth=1.4)
    plt.title(f"Rolling {window}d Sharpe Ratio", fontweight="bold")
    plt.axhline(0, color="black", linewidth=0.5)
    plt.axhline(1, color="green", linestyle="--", linewidth=0.5, alpha=0.4)
    plt.xlabel("Date"); plt.ylabel("Sharpe (ann.)")
    plt.legend(loc="upper left")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    t0 = datetime.now()
    bundle = fetch_prices()

    # Make sure universe survived download
    global UNIVERSE
    UNIVERSE = [t for t in UNIVERSE if t in bundle["close"].columns]
    print(f"[universe] {len(UNIVERSE)} tickers after data filter")

    print("\n[strategy A] PivoxQuant 4-pillar Quant Score, Top-N=%d monthly rebalance ..." % TOP_N)
    curve_A = run_portfolio(bundle, score_asof, "Strategy A — Quant Score", overlay=False)

    print("\n[strategy B] A + Risk-Defense Overlay (VIX + drawdown based cash) ...")
    curve_B = run_portfolio(bundle, score_asof, "Strategy B — Risk-Defense", overlay=True)

    print("\n[strategy C] TSMOM + MeanReversion blend ...")
    curve_C = run_portfolio(bundle, tsmom_mr_score, "Strategy C — Multi-Model", overlay=False)

    # Benchmarks — buy-and-hold aligned to the same start
    spy_bh = buy_hold(bundle, "SPY").rename("SPY (Benchmark)")
    qqq_bh = buy_hold(bundle, "QQQ").rename("QQQ")
    common_start = max(curve_A.index.min(), spy_bh.index.min())
    spy_bh = spy_bh[spy_bh.index >= common_start] / spy_bh[spy_bh.index >= common_start].iloc[0]
    qqq_bh = qqq_bh[qqq_bh.index >= common_start] / qqq_bh[qqq_bh.index >= common_start].iloc[0]

    # Align equity curves to same start to equalize growth-of-$1 comparison
    for c in (curve_A, curve_B, curve_C):
        c.drop(c.index[c.index < common_start], inplace=True, errors="ignore")

    # ── Metrics ──────────────────────────────────────────────────
    print("\n[metrics] computing ...")
    m_A = metrics(curve_A, spy_bh);  m_A["strategy"] = "A — Quant Score"
    m_B = metrics(curve_B, spy_bh);  m_B["strategy"] = "B — Risk-Defense"
    m_C = metrics(curve_C, spy_bh);  m_C["strategy"] = "C — Multi-Model"
    m_S = metrics(spy_bh);           m_S["strategy"] = "SPY (B&H)"
    m_Q = metrics(qqq_bh);           m_Q["strategy"] = "QQQ (B&H)"

    all_m = [m_A, m_B, m_C, m_S, m_Q]
    for m in all_m:
        print(f"  {m['strategy']:<25} CAGR={m['cagr']:6.2f}%  Sharpe={m['sharpe']:.2f}  MDD={m['max_drawdown']:6.2f}%")

    # ── Plots ────────────────────────────────────────────────────
    print("\n[plots] rendering ...")
    curves = {
        "Strategy A — Quant Score": curve_A,
        "Strategy B — Risk-Defense": curve_B,
        "Strategy C — Multi-Model":  curve_C,
        "SPY (Benchmark)": spy_bh,
        "QQQ": qqq_bh,
    }
    plot_equity(curves, OUT_DIR / "equity_curves.png")
    plot_drawdown({k: v for k, v in curves.items() if "QQQ" not in k}, OUT_DIR / "drawdown.png")
    plot_rolling_sharpe(curves, OUT_DIR / "rolling_sharpe.png")
    plot_monthly_heatmap(curve_A, OUT_DIR / "monthly_heatmap_A.png", "Strategy A — Monthly Returns (%)")
    plot_monthly_heatmap(curve_B, OUT_DIR / "monthly_heatmap_B.png", "Strategy B — Monthly Returns (%)")
    plot_monthly_heatmap(spy_bh,  OUT_DIR / "monthly_heatmap_SPY.png", "SPY — Monthly Returns (%)")

    # ── JSON dump ────────────────────────────────────────────────
    with open(OUT_DIR / "metrics.json", "w") as f:
        json.dump({
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "start": str(curve_A.index.min().date()),
                "end":   str(curve_A.index.max().date()),
                "universe_size": len(UNIVERSE),
                "top_n_per_month": TOP_N,
                "round_trip_cost": ROUND_TRIP_COST,
                "rf_rate": RF_RATE,
            },
            "strategies": all_m,
        }, f, indent=2)

    print(f"\n[done] elapsed {(datetime.now()-t0).total_seconds():.1f}s")
    print(f"[done] artifacts in {OUT_DIR}")

    return {
        "curves": curves,
        "metrics": {m["strategy"]: m for m in all_m},
        "curve_A": curve_A, "curve_B": curve_B, "curve_C": curve_C,
        "spy": spy_bh, "qqq": qqq_bh,
    }


if __name__ == "__main__":
    main()
