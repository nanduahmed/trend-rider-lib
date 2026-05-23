"""
Trailing Stop Loss engine for trade management.
"""
from typing import Tuple

from ..core.config import TrendRiderConfig


class TSLEngine:
    """
    Trailing Stop Loss engine.
    Manages step-wise trailing stop loss calculations with fixed increments.
    """

    def __init__(self, config: TrendRiderConfig):
        """
        Initialize TSL engine.

        Args:
            config: TrendRiderConfig with trading parameters
        """
        self.config = config

    def calculate_tsl(
        self,
        entry_price: float,
        highest_price: float,
        current_price: float
    ) -> Tuple[float, int]:
        """
        Calculate current stop loss based on highest price reached.

        The stop loss moves up in fixed increments based on how many
        steps have been achieved. Each step is tsl_step_pct of entry price.

        Example:
        - Entry: 100, Initial SL: 90 (10% below)
        - Price reaches 110: SL moves to 100 (1 step achieved)
        - Price reaches 120: SL moves to 110 (2 steps achieved)

        Args:
            entry_price: Entry price of the trade
            highest_price: Highest price seen since entry
            current_price: Current price (not used, kept for interface)

        Returns:
            Tuple of (current_stop_loss, steps_achieved)
        """
        initial_sl_pct = self.config.trade_initial_sl_pct
        tsl_step_pct = self.config.trade_tsl_step_pct

        # Calculate how many steps have been achieved
        price_gain = highest_price - entry_price
        price_gain_pct = price_gain / entry_price
        steps_achieved = int(price_gain_pct / tsl_step_pct)

        if steps_achieved == 0:
            # Still at initial SL
            current_sl = entry_price * (1 - initial_sl_pct)
        else:
            # Trail the SL based on steps achieved
            # Each step moves SL up by tsl_step_pct from entry
            current_sl = entry_price * (1 + (steps_achieved - 1) * tsl_step_pct)

        return current_sl, steps_achieved

    def should_exit(
        self,
        entry_price: float,
        current_price: float,
        current_sl: float
    ) -> Tuple[bool, str]:
        """
        Check if position should be exited.

        Args:
            entry_price: Entry price of the trade
            current_price: Current price
            current_sl: Current stop loss level

        Returns:
            Tuple of (should_exit: bool, reason: str)
            reason is "" if no exit, "TARGET" if target hit, "STOP_LOSS" if SL hit
        """
        target_price = entry_price * (1 + self.config.trade_target_pct)

        # Check target hit first (priority)
        if current_price >= target_price:
            return True, "TARGET"

        # Check stop loss hit
        if current_price <= current_sl:
            return True, "STOP_LOSS"

        return False, ""

    def calculate_profit_loss(
        self,
        entry_price: float,
        exit_price: float
    ) -> float:
        """
        Calculate profit/loss percentage.

        Args:
            entry_price: Entry price of the trade
            exit_price: Exit price of the trade

        Returns:
            Profit/loss as percentage (e.g., 50.0 for 50% gain)
        """
        return ((exit_price - entry_price) / entry_price) * 100
