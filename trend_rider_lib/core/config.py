"""
Configuration models for Trend Rider library.
"""
from pydantic import BaseModel, Field


class TrendRiderConfig(BaseModel):
    """Configuration parameters for Trend Rider analysis system."""

    # EMA Parameters
    ema_weekly_period: int = Field(default=21, ge=1, description="Weekly EMA period")
    ema_daily_fast: int = Field(default=34, ge=1, description="Daily fast EMA (EMA34)")
    ema_daily_slow: int = Field(default=55, ge=1, description="Daily slow EMA (EMA55)")
    warmup_weeks: int = Field(default=25, ge=1, description="Initial warmup period in weeks")

    # Zone Parameters
    buy_zone_upper_pct: float = Field(
        default=0.05,
        ge=0,
        le=1,
        description="Buy zone upper bound as % above EMA21 (5% = 0.05)"
    )
    downtrend_trigger_pct: float = Field(
        default=0.10,
        ge=0,
        le=1,
        description="Downtrend trigger as % below EMA21 (10% = 0.10)"
    )

    # Qualification Parameters
    tr_qualify_weeks: int = Field(
        default=40,
        ge=1,
        description="Weeks in uptrend to achieve TR qualification"
    )

    # Trading Parameters
    trade_target_pct: float = Field(
        default=0.50,
        ge=0,
        description="Trade target profit percentage (50% = 0.50)"
    )
    trade_initial_sl_pct: float = Field(
        default=0.10,
        ge=0,
        le=1,
        description="Initial stop loss as % below entry (10% = 0.10)"
    )
    trade_tsl_step_pct: float = Field(
        default=0.10,
        ge=0,
        description="Trailing stop loss step increment percentage"
    )
    max_concurrent_trades: int = Field(
        default=1,
        ge=1,
        description="Maximum concurrent trades per stock"
    )

    # Uptrend Strength Thresholds
    strength_weak_threshold: float = Field(
        default=0.70,
        description="Threshold for weak uptrend (% closes above EMA)"
    )
    strength_developing_threshold: float = Field(
        default=0.80,
        description="Threshold for developing uptrend"
    )
    strength_moderate_threshold: float = Field(
        default=0.90,
        description="Threshold for moderate uptrend"
    )
    strength_strong_threshold: float = Field(
        default=1.00,
        description="Threshold for strong uptrend"
    )

    class Config:
        """Pydantic configuration."""
        validate_assignment = True
