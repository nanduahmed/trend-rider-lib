"""
Unit tests for indicator calculations.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from trend_rider_lib.indicators import (
    compute_zone_flags,
    mark_warmup_complete,
)
from trend_rider_lib.indicators.ema_engine import incremental_ema


class TestFlagComputer:
    """Test zone flag calculations."""

    def create_df_with_ema21(self, prices: list, ema21_values: list) -> pd.DataFrame:
        """Create test DataFrame with prices and EMA21."""
        dates = [datetime(2023, 1, 1) + timedelta(weeks=i) for i in range(len(prices))]
        df = pd.DataFrame({
            'Close': prices,
            'EMA21': ema21_values,
            'timeframe': ['weekly'] * len(prices)
        }, index=dates)
        return df

    def test_buyzone_flag_true_when_in_range(self):
        """Flag should be True when price in buy zone."""
        df = self.create_df_with_ema21(
            prices=[102.0],  # Between 100 and 105
            ema21_values=[100.0]
        )

        result = compute_zone_flags(df, buy_zone_upper_pct=0.05)

        assert result.loc[result.index[0], 'is_buyzone'] == True
        assert result.loc[result.index[0], 'is_above_buyzone'] == False

    def test_above_buyzone_flag_true_when_above_upper(self):
        """Flag should be True when price above upper bound."""
        df = self.create_df_with_ema21(
            prices=[106.0],  # Above 105
            ema21_values=[100.0]
        )

        result = compute_zone_flags(df, buy_zone_upper_pct=0.05)

        assert result.loc[result.index[0], 'is_above_buyzone'] == True
        assert result.loc[result.index[0], 'is_buyzone'] == False

    def test_downtrend_trigger_when_below_threshold(self):
        """Flag should be True when price below 90% of EMA21."""
        df = self.create_df_with_ema21(
            prices=[89.0],  # Below 90
            ema21_values=[100.0]
        )

        result = compute_zone_flags(df, downtrend_trigger_pct=0.10)

        assert result.loc[result.index[0], 'is_downtrend_trigger'] == True

    def test_no_flags_on_nan_ema(self):
        """Flags should be False when EMA21 is NaN."""
        df = pd.DataFrame({
            'Close': [100.0],
            'EMA21': [np.nan],
            'timeframe': ['weekly']
        }, index=[datetime(2023, 1, 1)])

        result = compute_zone_flags(df)

        assert result.loc[result.index[0], 'is_buyzone'] == False
        assert result.loc[result.index[0], 'is_above_buyzone'] == False
        assert result.loc[result.index[0], 'is_downtrend_trigger'] == False

    def test_multiple_rows(self):
        """Should handle multiple rows correctly."""
        prices = [100, 102, 106, 89, 98]
        ema21_values = [100, 100, 100, 100, 100]

        df = self.create_df_with_ema21(prices, ema21_values)
        result = compute_zone_flags(df, buy_zone_upper_pct=0.05, downtrend_trigger_pct=0.10)

        # Row 0: 100, EMA21 100 → not in buyzone (need > EMA21)
        assert result.iloc[0]['is_buyzone'] == False

        # Row 1: 102, EMA21 100 → in buyzone (100 < 102 <= 105)
        assert result.iloc[1]['is_buyzone'] == True

        # Row 2: 106, EMA21 100 → above buyzone (106 > 105)
        assert result.iloc[2]['is_above_buyzone'] == True

        # Row 3: 89, EMA21 100 → downtrend trigger (89 < 90)
        assert result.iloc[3]['is_downtrend_trigger'] == True

        # Row 4: 98, EMA21 100 → neither (98 > 90, but not > 100)
        assert result.iloc[4]['is_buyzone'] == False
        assert result.iloc[4]['is_above_buyzone'] == False


class TestWarmupComplete:
    """Test warmup period marking."""

    def test_warmup_complete_marking(self):
        """Rows after warmup should be marked complete."""
        dates = [datetime(2023, 1, 1) + timedelta(weeks=i) for i in range(30)]
        df = pd.DataFrame({
            'Close': [100.0] * 30,
            'timeframe': ['weekly'] * 30
        }, index=dates)

        result = mark_warmup_complete(df, warmup_weeks=25)

        # First 24 rows should be False (0-24 = 25 rows)
        for i in range(25):
            assert result.iloc[i]['warmup_complete'] == False

        # Rows 25+ should be True
        for i in range(25, 30):
            assert result.iloc[i]['warmup_complete'] == True

    def test_warmup_complete_below_threshold(self):
        """All should be False if total rows < warmup_weeks."""
        dates = [datetime(2023, 1, 1) + timedelta(weeks=i) for i in range(20)]
        df = pd.DataFrame({
            'Close': [100.0] * 20,
            'timeframe': ['weekly'] * 20
        }, index=dates)

        result = mark_warmup_complete(df, warmup_weeks=25)

        # All should be False (not enough weeks)
        assert (result['warmup_complete'] == False).all()


class TestIncrementalEMA:
    """Test incremental EMA calculation."""

    def test_incremental_ema_formula(self):
        """Incremental EMA should follow correct formula."""
        previous_ema = 100.0
        new_price = 105.0
        period = 21

        # Formula: k = 2 / (period + 1) = 2/22 ≈ 0.0909
        # EMA = price * k + previous_ema * (1 - k)
        # EMA = 105 * 0.0909 + 100 * 0.9091 ≈ 100.45

        result = incremental_ema(previous_ema, new_price, period)

        k = 2.0 / (period + 1)
        expected = new_price * k + previous_ema * (1 - k)

        assert abs(result - expected) < 0.001

    def test_incremental_ema_converges(self):
        """Repeated calls with same price should converge to price."""
        ema = 100.0
        price = 110.0
        period = 21

        # Apply incremental EMA multiple times
        for _ in range(100):
            ema = incremental_ema(ema, price, period)

        # Should converge to price
        assert abs(ema - price) < 0.01

    def test_incremental_ema_oscillates_if_alternating(self):
        """EMA should dampen oscillations."""
        ema = 100.0
        period = 21
        k = 2.0 / (period + 1)

        # Alternate between 100 and 110
        for _ in range(10):
            ema = incremental_ema(ema, 110.0, period)
            ema = incremental_ema(ema, 100.0, period)

        # Should be near 105 (midpoint)
        assert 104 < ema < 106
