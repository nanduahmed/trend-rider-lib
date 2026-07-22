"""
Core enumerations for Trend Rider library.
"""
from enum import Enum, auto


class State(Enum):
    """FSM macro-level states for stock analysis.

    UPTREND is a container (macro-state) with two substates
    defined in UptrendSubstate. The state machine is always
    in exactly one macro-state, and when that macro-state is
    UPTREND it is also in exactly one substate.

    Transitions between macro-states:
      WARMUP      → OBSERVING        (weekly_candle_count >= warmup_weeks)
      OBSERVING   → UPTREND          (weekly close > EMA21)
      UPTREND     → DOWNTREND        (weekly close < 0.90 × EMA21)
      DOWNTREND   → RECOVERING       (weekly close > EMA21)
      RECOVERING  → UPTREND          (daily EMA34 > EMA55 — bullish crossover)
      RECOVERING  → DOWNTREND        (weekly close < 0.90 × EMA21)

    Blocked transitions (one-way latches / disallowed paths):
      UPTREND     → OBSERVING        (never)
      UPTREND     → RECOVERING       (must go through DOWNTREND)
      DOWNTREND   → OBSERVING        (never)
      DOWNTREND   → UPTREND          (must go through RECOVERING)
      RECOVERING  → OBSERVING        (never)
      WARMUP      → (any except OBSERVING)
    """
    WARMUP = auto()
    OBSERVING = auto()
    UPTREND = auto()       # Macro-state; actual candle position tracked via UptrendSubstate
    DOWNTREND = auto()
    RECOVERING = auto()


class UptrendSubstate(Enum):
    """Substates within the UPTREND macro-state.

    These capture the current weekly candle's position relative
    to the EMA21 buy-zone band.  They DO NOT represent separate
    macro-level states — the trend cycle (UPTREND) is continuous.

    Transitions (within UPTREND only):
      BUY_ZONE          → NOT_IN_BUY_ZONE   (no qualifying green candle)
      NOT_IN_BUY_ZONE   → BUY_ZONE           (green candle qualifies buy zone)
    """
    BUY_ZONE = auto()
    NOT_IN_BUY_ZONE = auto()


class Classification(Enum):
    """Stock classification based on qualification and status."""
    UNQUALIFIED = auto()
    PRIME = auto()
    PRIME_WAITLIST = auto()
    MOMENTUM = auto()
    MOMENTUM_WAITLIST = auto()
    RECOVERING = auto()


class SignalType(Enum):
    """Types of signals emitted by the system."""
    UPTREND_START = auto()
    BUY_ENTRY = auto()
    REENTRY = auto()
    MOMENTUM_ENTRY = auto()
    DOWNTREND_START = auto()
    EMA_CROSSOVER = auto()
    TR_QUALIFIED = auto()


class TrendEventType(Enum):
    """Types of lifecycle events tracked outside the signal stream."""
    DAILY_EMA21_CONFIRMATION = auto()
    DAILY_POSITIVE_CROSSOVER = auto()
    DAILY_DOWNTREND_TRIGGER = auto()
    WEEKLY_TREND_START = auto()
    WEEKLY_TREND_END = auto()
    TR_QUALIFIED = auto()


class UptrendStrength(Enum):
    """Classification of uptrend strength based on close ratio."""
    WEAK = auto()  # <70% closes above EMA21
    DEVELOPING = auto()  # 70-80%
    MODERATE = auto()  # 80-90%
    STRONG = auto()  # 90-99%
    SUPER_STRONG = auto()  # 100%


class TradeStatus(Enum):
    """Status of a trade lifecycle."""
    OPEN = auto()
    CLOSED_TARGET = auto()
    CLOSED_SL = auto()
    CLOSED_TSL = auto()


class ExitReason(Enum):
    """Reason why a trade was exited."""
    TARGET_HIT = auto()
    STOP_LOSS = auto()
    TRAILING_STOP = auto()