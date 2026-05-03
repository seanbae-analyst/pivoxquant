"""
PivoxQuant Risk Defense System -- 7-Layer Portfolio Protection
Institutional-grade risk management adapted for retail investors.

Each layer operates independently. When ANY layer triggers,
it overrides individual stock signals to protect the portfolio.

Layer 1: VaR-based risk exposure analysis
Layer 2: Correlation spike alert
Layer 3: VIX hedge trigger
Layer 4: Tail Risk Parity auto-rebalance
Layer 5: Daily loss limit (circuit breaker)
Layer 6: Sector concentration limit
Layer 7: Dynamic cash management (regime-aware)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple


class RiskDefenseSystem:
    """7-layer portfolio risk defense. Call check_all() each bar."""

    PROFILE_DEFENSE_CONFIGS = {
        "passive_index_hugger": {
            "var_threshold_pct": 1.5,
            "correlation_alert_threshold": 0.65,
            "vix_caution": 22, "vix_panic": 30,
            "daily_loss_limit_pct": 1.0,
            "max_sector_pct": 30,
            "bear_cash_pct": 55, "transition_cash_pct": 35, "bull_cash_pct": 10,
            "target_mdd": 10.0,
        },
        "steady_accumulator": {
            "var_threshold_pct": 2.0,
            "correlation_alert_threshold": 0.7,
            "vix_caution": 23, "vix_panic": 32,
            "daily_loss_limit_pct": 1.5,
            "max_sector_pct": 35,
            "bear_cash_pct": 45, "transition_cash_pct": 25, "bull_cash_pct": 8,
            "target_mdd": 10.0,
        },
        "swing_trader": {
            "var_threshold_pct": 3.0,
            "correlation_alert_threshold": 0.75,
            "vix_caution": 25, "vix_panic": 35,
            "daily_loss_limit_pct": 2.5,
            "max_sector_pct": 40,
            "bear_cash_pct": 35, "transition_cash_pct": 15, "bull_cash_pct": 5,
            "target_mdd": 12.0,
        },
        "momentum_rider": {
            "var_threshold_pct": 3.5,
            "correlation_alert_threshold": 0.75,
            "vix_caution": 27, "vix_panic": 38,
            "daily_loss_limit_pct": 3.0,
            "max_sector_pct": 45,
            "bear_cash_pct": 40, "transition_cash_pct": 15, "bull_cash_pct": 3,
            "target_mdd": 15.0,
        },
        "value_hunter": {
            "var_threshold_pct": 2.5,
            "correlation_alert_threshold": 0.7,
            "vix_caution": 25, "vix_panic": 35,
            "daily_loss_limit_pct": 2.0,
            "max_sector_pct": 35,
            "bear_cash_pct": 40, "transition_cash_pct": 20, "bull_cash_pct": 5,
            "target_mdd": 12.0,
        },
        "risk_managed_growth": {
            "var_threshold_pct": 2.0,
            "correlation_alert_threshold": 0.65,
            "vix_caution": 22, "vix_panic": 30,
            "daily_loss_limit_pct": 1.5,
            "max_sector_pct": 30,
            "bear_cash_pct": 50, "transition_cash_pct": 30, "bull_cash_pct": 8,
            "target_mdd": 11.0,
        },
        "aggressive_scalper": {
            "var_threshold_pct": 4.0,
            "correlation_alert_threshold": 0.8,
            "vix_caution": 30, "vix_panic": 40,
            "daily_loss_limit_pct": 3.5,
            "max_sector_pct": 50,
            "bear_cash_pct": 30, "transition_cash_pct": 10, "bull_cash_pct": 0,
            "target_mdd": 18.0,
        },
        "macro_rotator": {
            "var_threshold_pct": 2.5,
            "correlation_alert_threshold": 0.7,
            "vix_caution": 24, "vix_panic": 33,
            "daily_loss_limit_pct": 2.0,
            "max_sector_pct": 40,
            "bear_cash_pct": 45, "transition_cash_pct": 25, "bull_cash_pct": 5,
            "target_mdd": 12.0,
        },
    }

    def __init__(self, config: dict = None):
        self.config = config or self.default_config()
        self._portfolio_peak: float = 0.0
        self._daily_pnl: float = 0.0
        self._halted_today: bool = False
        self._cash_target: float = 0.0  # 0 = fully invested
        self._warnings: List[str] = []

    @classmethod
    def from_profile(cls, profile_name: str):
        """Create a RiskDefenseSystem pre-configured for a specific investment profile.
        Merges profile overrides on top of the full default config so all
        layer keys are always present."""
        base = cls.default_config()
        overrides = cls.PROFILE_DEFENSE_CONFIGS.get(profile_name, {})
        base.update(overrides)
        return cls(config=base)

    @staticmethod
    def default_config() -> dict:
        return {
            # Layer 1: VaR-based risk exposure analysis
            "var_threshold_pct": 3.0,       # if daily VaR > 3% of portfolio, flag
            "var_reduction_factor": 0.5,    # risk contribution scaling factor

            # Layer 2: Correlation spike alert
            "correlation_alert_threshold": 0.7,  # avg pairwise corr > 0.7 = danger
            "correlation_cash_increase": 20,     # risk level increase on correlation spike

            # Layer 3: VIX hedge trigger
            "vix_caution": 25,    # VIX > 25 = elevated risk
            "vix_panic": 35,      # VIX > 35 = extreme risk

            # Layer 4: Tail Risk Parity auto-rebalance
            "tail_imbalance_threshold": 3.0,  # worst position contributes 3x avg => flag

            # Layer 5: Daily loss limit
            "daily_loss_limit_pct": 2.0,  # -2% daily = halt all trading

            # Layer 6: Sector concentration limit
            "max_sector_pct": 40,  # no single sector > 40%

            # Layer 7: Dynamic cash management
            "bear_cash_pct": 40,        # BEAR regime = 40% cash
            "transition_cash_pct": 20,  # TRANSITION = 20% cash
            "bull_cash_pct": 5,         # BULL = 5% cash minimum
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check_all(self, portfolio_state: dict) -> dict:
        """
        Run all 7 defense layers. Returns actions to take.

        portfolio_state keys:
            positions        : list of dicts with ticker, value, sector,
                               returns_20d, weight
            portfolio_value  : float (total portfolio value)
            daily_return     : float (today's portfolio return, percent)
            vix              : float or None (current VIX level)
            regime           : str  (BULL / MILD_BULL / TRANSITION /
                                     MILD_BEAR / BEAR)
            returns_matrix   : np.ndarray (n_days x n_positions) of daily
                               returns used for VaR / correlation
        """
        actions: dict = {
            "risk_exposure": [],       # [(ticker, risk_contribution_pct, reason)]
            "regime_risk_level": 0,    # regime-derived risk level (0-100)
            "halt_trading": False,     # stop all new trades
            "warnings": [],            # human-readable warnings
            "defense_score": 100,      # 100 = all safe, 0 = max defense
            "layers_triggered": [],    # which layers fired
        }

        positions = portfolio_state.get("positions", [])
        portfolio_value = portfolio_state.get("portfolio_value", 0)
        daily_return = portfolio_state.get("daily_return", 0)
        vix = portfolio_state.get("vix")
        regime = portfolio_state.get("regime", "TRANSITION")
        returns_matrix = portfolio_state.get("returns_matrix")

        # NaN/Inf guard -- sanitize returns before any layer reads them
        if returns_matrix is not None:
            if np.any(~np.isfinite(returns_matrix)):
                returns_matrix = np.nan_to_num(
                    returns_matrix, nan=0.0, posinf=0.0, neginf=0.0
                )

        if not positions or portfolio_value <= 0:
            return actions

        # Track portfolio peak for drawdown
        self._portfolio_peak = max(self._portfolio_peak, portfolio_value)

        # Run each layer independently
        self._layer1_var(actions, positions, returns_matrix, portfolio_value)
        self._layer2_correlation(actions, returns_matrix)
        self._layer3_vix(actions, vix)
        self._layer4_tail_risk(actions, positions, returns_matrix)
        self._layer5_daily_loss(actions, daily_return)
        self._layer6_sector_concentration(actions, positions)
        self._layer7_cash_management(actions, regime)

        # Clamp defense score to [0, 100]
        actions["defense_score"] = max(0, min(100, actions["defense_score"]))

        # Overall status
        score = actions["defense_score"]
        if score >= 80:
            actions["status"] = "GREEN"
        elif score >= 50:
            actions["status"] = "YELLOW"
        else:
            actions["status"] = "RED"

        self._warnings = actions["warnings"]
        return actions

    # ------------------------------------------------------------------
    # Layer 1: VaR-based risk exposure analysis
    # ------------------------------------------------------------------

    def _layer1_var(
        self,
        actions: dict,
        positions: list,
        returns_matrix: Optional[np.ndarray],
        portfolio_value: float,
    ) -> None:
        """If 95% daily VaR exceeds threshold, flag the riskiest position's risk contribution."""
        if returns_matrix is None or returns_matrix.shape[0] < 20:
            return
        if returns_matrix.shape[1] == 0:
            return

        n_pos = len(positions)
        if n_pos == 0:
            return
        weights = np.array(
            [p.get("weight") or (1.0 / n_pos) for p in positions],
            dtype=np.float64,
        )
        # Drop-alignment guard (2026-04-24, Bug A): _build_returns_matrix may
        # skip tickers whose price history is too short, so
        # returns_matrix.shape[1] can be < len(positions). Before, the matmul
        # would raise and kill the whole check_all() → all 7 layers "—".
        if weights.shape[0] != returns_matrix.shape[1]:
            n = returns_matrix.shape[1]
            weights = np.ones(n, dtype=np.float64) / n
        # Zero-weight portfolio (all positions valued at 0) guard.
        ws = float(weights.sum())
        if ws <= 0 or not np.isfinite(ws):
            weights = np.ones(returns_matrix.shape[1], dtype=np.float64) / returns_matrix.shape[1]
        else:
            weights = weights / ws

        # Portfolio-level daily returns
        port_returns = returns_matrix @ weights

        # Historical 95% VaR (negative percentile flipped to positive loss)
        var_95 = -float(np.percentile(port_returns, 5)) * portfolio_value
        var_pct = var_95 / portfolio_value * 100

        if var_pct <= self.config["var_threshold_pct"]:
            return

        # Identify riskiest position by individual VaR contribution
        individual_vars: List[Tuple[str, float]] = []
        for i, pos in enumerate(positions):
            if i < returns_matrix.shape[1]:
                pos_var = -float(np.percentile(returns_matrix[:, i], 5)) * pos.get(
                    "value", 0
                )
                individual_vars.append((pos.get("ticker", f"pos_{i}"), pos_var))

        if not individual_vars:
            return

        individual_vars.sort(key=lambda x: x[1], reverse=True)
        riskiest_ticker, riskiest_var = individual_vars[0]
        total_var = sum(v for _, v in individual_vars)
        risk_contribution = (riskiest_var / total_var * 100) if total_var > 0 else 0

        actions["risk_exposure"].append(
            (
                riskiest_ticker,
                round(risk_contribution, 1),
                f"VaR {var_pct:.1f}% exceeds {self.config['var_threshold_pct']}% threshold",
            )
        )
        actions["layers_triggered"].append("L1_VAR")
        actions["defense_score"] -= 15
        actions["warnings"].append(
            f"Portfolio daily VaR is {var_pct:.1f}% -- elevated risk"
        )

    # ------------------------------------------------------------------
    # Layer 2: Correlation spike
    # ------------------------------------------------------------------

    def _layer2_correlation(
        self,
        actions: dict,
        returns_matrix: Optional[np.ndarray],
    ) -> None:
        """Alert when average pairwise correlation spikes above threshold."""
        if returns_matrix is None:
            return
        if returns_matrix.shape[1] < 2 or returns_matrix.shape[0] < 20:
            return

        recent = returns_matrix[-20:]
        corr_matrix = np.corrcoef(recent.T)
        n = corr_matrix.shape[0]
        if n < 2:
            return

        mask = ~np.eye(n, dtype=bool)
        avg_corr = float(np.nanmean(corr_matrix[mask]))

        if avg_corr <= self.config["correlation_alert_threshold"]:
            return

        actions["regime_risk_level"] = max(
            actions["regime_risk_level"],
            self.config["correlation_cash_increase"],
        )
        actions["layers_triggered"].append("L2_CORRELATION")
        actions["defense_score"] -= 15
        actions["warnings"].append(
            f"Portfolio correlation {avg_corr:.2f} -- diversification breakdown risk"
        )

    # ------------------------------------------------------------------
    # Layer 3: VIX hedge trigger
    # ------------------------------------------------------------------

    def _layer3_vix(self, actions: dict, vix: Optional[float]) -> None:
        """Set risk level based on VIX level (caution vs panic)."""
        if vix is None:
            return

        if vix >= self.config["vix_panic"]:
            actions["regime_risk_level"] = max(actions["regime_risk_level"], 80)
            actions["layers_triggered"].append("L3_VIX_PANIC")
            actions["defense_score"] -= 30
            actions["warnings"].append(
                f"VIX {vix:.0f} -- panic level, extreme defense active"
            )
        elif vix >= self.config["vix_caution"]:
            actions["regime_risk_level"] = max(actions["regime_risk_level"], 50)
            actions["layers_triggered"].append("L3_VIX_CAUTION")
            actions["defense_score"] -= 15
            actions["warnings"].append(
                f"VIX {vix:.0f} -- elevated, defensive positioning"
            )

    # ------------------------------------------------------------------
    # Layer 4: Tail Risk imbalance
    # ------------------------------------------------------------------

    def _layer4_tail_risk(
        self,
        actions: dict,
        positions: list,
        returns_matrix: Optional[np.ndarray],
    ) -> None:
        """Flag positions whose tail-risk contribution exceeds threshold."""
        if returns_matrix is None or returns_matrix.shape[0] < 20:
            return
        if returns_matrix.shape[1] == 0:
            return

        n_pos = len(positions)
        if n_pos == 0:
            return
        weights = np.array(
            [p.get("weight") or (1.0 / n_pos) for p in positions],
            dtype=np.float64,
        )
        # Same drop-alignment + zero-sum guard as _layer1_var (see Bug A notes).
        if weights.shape[0] != returns_matrix.shape[1]:
            n = returns_matrix.shape[1]
            weights = np.ones(n, dtype=np.float64) / n
        ws = float(weights.sum())
        if ws <= 0 or not np.isfinite(ws):
            weights = np.ones(returns_matrix.shape[1], dtype=np.float64) / returns_matrix.shape[1]
        else:
            weights = weights / ws
        port_returns = returns_matrix @ weights

        # 5th percentile as tail threshold
        var_threshold = float(np.percentile(port_returns, 5))
        tail_mask = port_returns <= var_threshold

        if tail_mask.sum() == 0:
            return

        # Component expected shortfall (average loss in the tail)
        component_losses = np.mean(returns_matrix[tail_mask], axis=0) * weights
        avg_contrib = float(np.mean(np.abs(component_losses)))

        if avg_contrib <= 0:
            return

        for i, pos in enumerate(positions):
            if i >= len(component_losses):
                continue
            ratio = abs(float(component_losses[i])) / avg_contrib
            if ratio > self.config["tail_imbalance_threshold"]:
                risk_contribution_pct = round(ratio / max(n_pos, 1) * 100, 1)
                actions["risk_exposure"].append(
                    (
                        pos.get("ticker", f"pos_{i}"),
                        risk_contribution_pct,
                        f"Tail risk contribution {ratio:.1f}x average",
                    )
                )
                if "L4_TAIL_RISK" not in actions["layers_triggered"]:
                    actions["layers_triggered"].append("L4_TAIL_RISK")
                actions["defense_score"] -= 10

    # ------------------------------------------------------------------
    # Layer 5: Daily loss limit (circuit breaker)
    # ------------------------------------------------------------------

    def _layer5_daily_loss(self, actions: dict, daily_return: float) -> None:
        """Halt all new trading if daily portfolio loss exceeds limit."""
        if self._halted_today:
            return  # already halted, don't re-trigger

        if daily_return > -self.config["daily_loss_limit_pct"]:
            return

        self._halted_today = True  # set when triggered
        actions["halt_trading"] = True
        actions["layers_triggered"].append("L5_DAILY_LOSS")
        actions["defense_score"] -= 20
        actions["warnings"].append(
            f"Daily loss {daily_return:.1f}% exceeds "
            f"-{self.config['daily_loss_limit_pct']}% limit -- trading halted"
        )

    # ------------------------------------------------------------------
    # Layer 6: Sector concentration limit
    # ------------------------------------------------------------------

    def _layer6_sector_concentration(
        self, actions: dict, positions: list
    ) -> None:
        """Flag positions when any single sector exceeds weight limit."""
        sector_weights: Dict[str, float] = {}
        for pos in positions:
            sector = pos.get("sector", "Unknown")
            sector_weights[sector] = (
                sector_weights.get(sector, 0) + pos.get("weight", 0) * 100
            )

        for sector, weight in sector_weights.items():
            if weight <= self.config["max_sector_pct"]:
                continue

            sector_positions = [
                p for p in positions if p.get("sector") == sector
            ]
            if not sector_positions:
                continue

            # Flag the largest position in the overweight sector
            largest = max(sector_positions, key=lambda p: p.get("value", 0))
            weight - self.config["max_sector_pct"]
            actions["risk_exposure"].append(
                (
                    largest.get("ticker", "?"),
                    round(weight, 1),
                    f"Sector {sector} at {weight:.0f}% exceeds "
                    f"{self.config['max_sector_pct']}% limit",
                )
            )
            if "L6_SECTOR_CONCENTRATION" not in actions["layers_triggered"]:
                actions["layers_triggered"].append("L6_SECTOR_CONCENTRATION")
            actions["defense_score"] -= 10

    # ------------------------------------------------------------------
    # Layer 7: Dynamic cash management
    # ------------------------------------------------------------------

    def _layer7_cash_management(self, actions: dict, regime: str) -> None:
        """Set regime-derived risk level based on market regime."""
        regime_upper = (regime or "TRANSITION").upper()

        if regime_upper in ("BEAR", "MILD_BEAR"):
            risk_level = self.config["bear_cash_pct"]
        elif regime_upper == "TRANSITION":
            risk_level = self.config["transition_cash_pct"]
        else:
            risk_level = self.config["bull_cash_pct"]

        actions["regime_risk_level"] = max(
            actions["regime_risk_level"], risk_level
        )
        if risk_level > 10:
            actions["layers_triggered"].append("L7_CASH_MGMT")

    # ------------------------------------------------------------------
    # Cash Re-Entry Logic
    # ------------------------------------------------------------------

    def check_reentry(self, portfolio_state: dict) -> dict:
        """Check if conditions are safe to re-deploy cash into positions.
        Only triggers when cash is above target and defense conditions have cleared."""

        regime = portfolio_state.get("regime", "TRANSITION")
        vix = portfolio_state.get("vix")
        current_cash_pct = portfolio_state.get("current_cash_pct", 0)

        # Target cash for current regime
        regime_upper = (regime or "TRANSITION").upper()
        if regime_upper in ("BULL", "MILD_BULL"):
            target_cash = self.config.get("bull_cash_pct", 5)
        elif regime_upper == "TRANSITION":
            target_cash = self.config.get("transition_cash_pct", 20)
        else:
            target_cash = self.config.get("bear_cash_pct", 40)

        # VIX check -- don't re-enter if VIX is elevated
        if vix and vix >= self.config.get("vix_caution", 25):
            return {"reentry": False, "reason": f"VIX {vix:.0f} still elevated"}

        # If current cash > target by 10%+, suggest re-deployment
        excess_cash = current_cash_pct - target_cash
        if excess_cash > 10:
            deploy_pct = min(excess_cash * 0.5, 20)  # deploy half of excess, max 20% at a time
            return {
                "reentry": True,
                "deploy_pct": round(deploy_pct, 1),
                "target_cash_pct": target_cash,
                "current_cash_pct": round(current_cash_pct, 1),
                "reason": f"Regime {regime}, VIX safe, excess cash {excess_cash:.0f}%",
            }

        return {"reentry": False, "reason": "Cash at or below target"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_defense_summary(self) -> dict:
        """Human-readable defense status."""
        return {
            "portfolio_peak": round(self._portfolio_peak, 2),
            "active_warnings": list(self._warnings),
            "config": dict(self.config),
        }

    def reset_daily(self) -> None:
        """Reset daily circuit breaker state (call at start of each trading day)."""
        self._halted_today = False
        self._daily_pnl = 0.0

    def reset(self) -> None:
        """Reset internal state (e.g. between backtest runs)."""
        self._portfolio_peak = 0.0
        self._daily_pnl = 0.0
        self._halted_today = False
        self._cash_target = 0.0
        self._warnings = []
