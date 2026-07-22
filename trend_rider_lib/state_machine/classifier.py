"""
Stock classification logic based on qualification and status.
"""
from ..core.enums import Classification, State, UptrendSubstate
from ..core.models import StockContext


def classify_stock(context: StockContext) -> Classification:
    """
    Classify stock based on current context.

    Classification rules:
    1. If RECOVERING → UNQUALIFIED
    2. If not tr_qualified → UNQUALIFIED
    3. If tr_qualified and uptrend_weeks >= 40:
       - If in BUY_ZONE substate (within UPTREND) → PRIME
       - If NOT_IN_BUY_ZONE substate → PRIME_WAITLIST
    4. If tr_qualified and uptrend_weeks < 40:
       - If is_buyzone → MOMENTUM (for post-recovery < 40 weeks)
       - If NOT is_buyzone → MOMENTUM_WAITLIST
    5. If in RECOVERING macro-state → RECOVERING (classification matches macro-state)

    Args:
        context: Current stock context

    Returns:
        Classification enum value
    """
    if context.current_state == State.RECOVERING:
        return Classification.RECOVERING

    if not context.tr_qualified:
        return Classification.UNQUALIFIED

    # Check for graduation from Momentum to Prime
    if context.uptrend_weeks >= 40:
        if context.uptrend_substate == UptrendSubstate.BUY_ZONE.name:
            return Classification.PRIME
        else:
            return Classification.PRIME_WAITLIST

    # Momentum classifications (post-recovery, < 40 weeks)
    if context.is_crossover_detected:
        if context.uptrend_substate == UptrendSubstate.BUY_ZONE.name:
            return Classification.MOMENTUM
        else:
            return Classification.MOMENTUM_WAITLIST

    return Classification.UNQUALIFIED


def update_classification(context: StockContext) -> None:
    """
    Update classification in context based on current state.

    Args:
        context: Stock context to update (modified in place)
    """
    context.classification = classify_stock(context)