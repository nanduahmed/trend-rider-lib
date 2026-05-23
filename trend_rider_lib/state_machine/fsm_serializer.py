"""
FSM state serialization and deserialization for persistence.
"""
from datetime import datetime
from typing import Dict, Any, Optional

from ..core.models import StockContext, UptrendRecord
from ..core.enums import State, Classification, UptrendStrength


def serialize_context(context: StockContext) -> Dict[str, Any]:
    """
    Serialize StockContext to dictionary for persistence.

    Args:
        context: StockContext to serialize

    Returns:
        Dictionary with all context data
    """
    return {
        'ticker': context.ticker,
        'current_state': context.current_state.name if isinstance(context.current_state, State) else context.current_state,
        'tr_qualified': context.tr_qualified,
        'uptrend_start_date': context.uptrend_start_date.isoformat() if context.uptrend_start_date else None,
        'uptrend_weeks': context.uptrend_weeks,
        'closes_above_ema': context.closes_above_ema,
        'closes_below_ema': context.closes_below_ema,
        'is_buyzone': context.is_buyzone,
        'is_crossover_detected': context.is_crossover_detected,
        'crossover_date': context.crossover_date.isoformat() if context.crossover_date else None,
        'crossover_price': context.crossover_price,
        'classification': context.classification.name if isinstance(context.classification, Classification) else context.classification,
        'last_ema21': context.last_ema21,
        'last_ema34': context.last_ema34,
        'last_ema55': context.last_ema55,
        'last_close': context.last_close,
        'last_update': context.last_update.isoformat() if context.last_update else None,
        'warmup_complete': context.warmup_complete,
        'candle_count': context.candle_count,
        'current_uptrend': serialize_uptrend(context.current_uptrend) if context.current_uptrend else None,
        'uptrend_history': [serialize_uptrend(u) for u in context.uptrend_history]
    }


def deserialize_context(data: Dict[str, Any]) -> StockContext:
    """
    Deserialize dictionary to StockContext.

    Args:
        data: Dictionary with serialized context data

    Returns:
        Reconstructed StockContext
    """
    context = StockContext(ticker=data['ticker'])

    context.current_state = State[data['current_state']] if data.get('current_state') else State.WARMUP
    context.tr_qualified = data.get('tr_qualified', False)
    context.uptrend_start_date = datetime.fromisoformat(data['uptrend_start_date']) if data.get('uptrend_start_date') else None
    context.uptrend_weeks = data.get('uptrend_weeks', 0)
    context.closes_above_ema = data.get('closes_above_ema', 0)
    context.closes_below_ema = data.get('closes_below_ema', 0)
    context.is_buyzone = data.get('is_buyzone', False)
    context.is_crossover_detected = data.get('is_crossover_detected', False)
    context.crossover_date = datetime.fromisoformat(data['crossover_date']) if data.get('crossover_date') else None
    context.crossover_price = data.get('crossover_price')
    context.classification = Classification[data['classification']] if data.get('classification') else Classification.UNQUALIFIED
    context.last_ema21 = data.get('last_ema21')
    context.last_ema34 = data.get('last_ema34')
    context.last_ema55 = data.get('last_ema55')
    context.last_close = data.get('last_close')
    context.last_update = datetime.fromisoformat(data['last_update']) if data.get('last_update') else None
    context.warmup_complete = data.get('warmup_complete', False)
    context.candle_count = data.get('candle_count', 0)

    if data.get('current_uptrend'):
        context.current_uptrend = deserialize_uptrend(data['current_uptrend'])

    context.uptrend_history = [deserialize_uptrend(u) for u in data.get('uptrend_history', [])]

    return context


def serialize_uptrend(uptrend: UptrendRecord) -> Dict[str, Any]:
    """
    Serialize UptrendRecord to dictionary.

    Args:
        uptrend: UptrendRecord to serialize

    Returns:
        Dictionary representation
    """
    return {
        'start_date': uptrend.start_date.isoformat() if uptrend.start_date else None,
        'end_date': uptrend.end_date.isoformat() if uptrend.end_date else None,
        'num_weeks': uptrend.num_weeks,
        'closes_above_ema': uptrend.closes_above_ema,
        'closes_below_ema': uptrend.closes_below_ema,
        'pct_closes_above': uptrend.pct_closes_above,
        'strength': uptrend.strength.name if uptrend.strength else None,
        'highest_price': uptrend.highest_price,
        'highest_price_date': uptrend.highest_price_date.isoformat() if uptrend.highest_price_date else None,
        'lowest_price': uptrend.lowest_price,
        'lowest_price_date': uptrend.lowest_price_date.isoformat() if uptrend.lowest_price_date else None
    }


def deserialize_uptrend(data: Dict[str, Any]) -> UptrendRecord:
    """
    Deserialize UptrendRecord from dictionary.

    Args:
        data: Dictionary with serialized uptrend data

    Returns:
        Reconstructed UptrendRecord
    """
    record = UptrendRecord(
        start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else datetime.now()
    )
    record.end_date = datetime.fromisoformat(data['end_date']) if data.get('end_date') else None
    record.num_weeks = data.get('num_weeks', 0)
    record.closes_above_ema = data.get('closes_above_ema', 0)
    record.closes_below_ema = data.get('closes_below_ema', 0)
    record.pct_closes_above = data.get('pct_closes_above', 0.0)
    record.strength = UptrendStrength[data['strength']] if data.get('strength') else None
    record.highest_price = data.get('highest_price')
    record.highest_price_date = datetime.fromisoformat(data['highest_price_date']) if data.get('highest_price_date') else None
    record.lowest_price = data.get('lowest_price')
    record.lowest_price_date = datetime.fromisoformat(data['lowest_price_date']) if data.get('lowest_price_date') else None

    return record
