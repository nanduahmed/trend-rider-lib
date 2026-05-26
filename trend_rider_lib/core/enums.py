"""
Core enumerations for Trend Rider library.
"""
from enum import Enum, auto


class State(Enum):
    """FSM states for stock analysis."""
    WARMUP = auto()
    OBSERVING = auto()
    BUY_ZONE = auto()
    UPTREND = auto()
    ABOVE_BUY_ZONE = auto()
    DOWNTREND = auto()
    RECOVERING = auto()


class Classification(Enum):
    """Stock classification based on qualification and status."""
    UNQUALIFIED = auto()
    PRIME = auto()
    PRIME_WAITLIST = auto()
    MOMENTUM = auto()
    MOMENTUM_WAITLIST = auto()


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
