"""
Stock classification logic based on qualification and status.
"""
from ..core.enums import Classification, State
from ..core.models import StockContext


def classify_stock(context: StockContext) -> Classification:
    """
    Classify stock based on current context.

    Classification rules:
    1. If not tr_qualified → UNQUALIFIED
    2. If tr_qualified and uptrend_weeks >= 40:
       - If crossover NOT detected (original/continuous uptrend) → PRIME or PRIME_WAITLIST
       - If crossover detected (recovered from downtrend) → already graduated to PRIME/PRIME_WAITLIST
    3. If tr_qualified and uptrend_weeks < 40:
       - If is_buyzone → MOMENTUM (for post-recovery < 40 weeks)
       - If NOT is_buyzone → MOMENTUM_WAITLIST

    Args:
        context: Current stock context

    Returns:
        Classification enum value
    """
    if not context.tr_qualified:
        return Classification.UNQUALIFIED

    # Check for graduation from Momentum to Prime
    if context.uptrend_weeks >= context.config.tr_qualify_weeks if hasattr(context, 'config') else 40:
        if context.is_buyzone:
            return Classification.PRIME
        else:
            return Classification.PRIME_WAITLIST

    # Momentum classifications (post-recovery, < 40 weeks)
    if context.is_crossover_detected:
        if context.is_buyzone:
            return Classification.MOMENTUM
        else:
            return Classification.MOMENTUM_WAITLIST

    # Building toward prime (in original uptrend but < 40 weeks)
    # This shouldn't normally happen for tr_qualified stocks
    return Classification.UNQUALIFIED


def update_classification(context: StockContext) -> None:
    """
    Update classification in context based on current state.

    Args:
        context: Stock context to update (modified in place)
    """
    context.classification = classify_stock(context)
