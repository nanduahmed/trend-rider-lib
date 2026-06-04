"""
FSM state serialization and deserialization for persistence.
"""
from datetime import datetime
from typing import Dict, Any, Optional

from ..core.models import StockContext, UptrendRecord
from ..core.enums import State, Classification, UptrendStrength, SignalType


def _serialize_history(history):
    return [
        [item[0].isoformat() if item[0] else None, item[1]]
        for item in history
    ]


def _deserialize_history(data):
    history = []
    for item in data or []:
        if not item:
            continue
        date_value = datetime.fromisoformat(item[0]) if item[0] else None
        if date_value is None:
            continue
        history.append((date_value, item[1]))
    return history


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
        'tr_qualified': bool(context.tr_qualified),
        'trend_start_date': context.trend_start_date.isoformat() if context.trend_start_date else None,
        'trend_end_date': context.trend_end_date.isoformat() if context.trend_end_date else None,
        'daily_ema21_cross_date': context.daily_ema21_cross_date.isoformat() if context.daily_ema21_cross_date else None,
        'daily_ema21_cross_price': context.daily_ema21_cross_price,
        'daily_downtrend_trigger_date': context.daily_downtrend_trigger_date.isoformat() if context.daily_downtrend_trigger_date else None,
        'daily_downtrend_trigger_price': context.daily_downtrend_trigger_price,
        'first_buy_zone_date': context.first_buy_zone_date.isoformat() if context.first_buy_zone_date else None,
        'first_buy_zone_price': context.first_buy_zone_price,
        'trend_cycle_id': context.trend_cycle_id,
        'positive_crossover_date': context.positive_crossover_date.isoformat() if context.positive_crossover_date else None,
        'positive_crossover_price': context.positive_crossover_price,
        'buy_signal_emitted': bool(context.buy_signal_emitted),
        'last_buy_signal_date': context.last_buy_signal_date.isoformat() if context.last_buy_signal_date else None,
        'last_buy_signal_type': context.last_buy_signal_type.name if isinstance(context.last_buy_signal_type, SignalType) else context.last_buy_signal_type,
        'last_buy_signal_crossover_date': context.last_buy_signal_crossover_date.isoformat() if context.last_buy_signal_crossover_date else None,
        'uptrend_start_date': context.uptrend_start_date.isoformat() if context.uptrend_start_date else None,
        'uptrend_weeks': int(context.uptrend_weeks),
        'closes_above_ema': int(context.closes_above_ema),
        'closes_below_ema': int(context.closes_below_ema),
        'is_buyzone': bool(context.is_buyzone),
        'is_crossover_detected': bool(context.is_crossover_detected),
        'crossover_date': context.crossover_date.isoformat() if context.crossover_date else None,
        'crossover_price': context.crossover_price,
        'classification': context.classification.name if isinstance(context.classification, Classification) else context.classification,
        'last_ema21': context.last_ema21,
        'last_ema34': context.last_ema34,
        'last_ema55': context.last_ema55,
        'last_close': context.last_close,
        'last_update': context.last_update.isoformat() if context.last_update else None,
        'warmup_complete': bool(context.warmup_complete),
        'candle_count': int(context.candle_count),
        'weekly_candle_count': int(context.weekly_candle_count),
        'current_uptrend': serialize_uptrend(context.current_uptrend) if context.current_uptrend else None,
        'uptrend_history': [serialize_uptrend(u) for u in context.uptrend_history],
        'longName': context.longName,
        'sector': context.sector,
        'industry': context.industry,
        'marketCap': context.marketCap,
        'website': context.website,
        'nextDividendDate': context.nextDividendDate,
        'isin': context.isin,
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
    context.trend_start_date = datetime.fromisoformat(data['trend_start_date']) if data.get('trend_start_date') else None
    context.trend_end_date = datetime.fromisoformat(data['trend_end_date']) if data.get('trend_end_date') else None
    context.daily_ema21_cross_date = datetime.fromisoformat(data['daily_ema21_cross_date']) if data.get('daily_ema21_cross_date') else None
    context.daily_ema21_cross_price = data.get('daily_ema21_cross_price')
    context.daily_downtrend_trigger_date = datetime.fromisoformat(data['daily_downtrend_trigger_date']) if data.get('daily_downtrend_trigger_date') else None
    context.daily_downtrend_trigger_price = data.get('daily_downtrend_trigger_price')
    context.first_buy_zone_date = datetime.fromisoformat(data['first_buy_zone_date']) if data.get('first_buy_zone_date') else None
    context.first_buy_zone_price = data.get('first_buy_zone_price')
    context.trend_cycle_id = data.get('trend_cycle_id')
    context.positive_crossover_date = datetime.fromisoformat(data['positive_crossover_date']) if data.get('positive_crossover_date') else None
    context.positive_crossover_price = data.get('positive_crossover_price')
    context.buy_signal_emitted = data.get('buy_signal_emitted', False)
    context.last_buy_signal_date = datetime.fromisoformat(data['last_buy_signal_date']) if data.get('last_buy_signal_date') else None
    context.last_buy_signal_type = SignalType[data['last_buy_signal_type']] if data.get('last_buy_signal_type') else None
    context.last_buy_signal_crossover_date = datetime.fromisoformat(data['last_buy_signal_crossover_date']) if data.get('last_buy_signal_crossover_date') else None
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
    context.weekly_candle_count = data.get('weekly_candle_count', 0)

    if data.get('current_uptrend'):
        context.current_uptrend = deserialize_uptrend(data['current_uptrend'])

    context.uptrend_history = [deserialize_uptrend(u) for u in data.get('uptrend_history', [])]

    # Restore metadata fields
    context.longName = data.get('longName')
    context.sector = data.get('sector')
    context.industry = data.get('industry')
    context.marketCap = data.get('marketCap')
    context.website = data.get('website')
    context.nextDividendDate = data.get('nextDividendDate')
    context.isin = data.get('isin')

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
        'cycle_id': uptrend.cycle_id,
        'start_state': uptrend.start_state,
        'end_state': uptrend.end_state,
        'start_price': uptrend.start_price,
        'end_price': uptrend.end_price,
        'start_date': uptrend.start_date.isoformat() if uptrend.start_date else None,
        'end_date': uptrend.end_date.isoformat() if uptrend.end_date else None,
        'first_buy_zone_date': uptrend.first_buy_zone_date.isoformat() if uptrend.first_buy_zone_date else None,
        'first_buy_zone_price': uptrend.first_buy_zone_price,
        'daily_ema21_cross_date': uptrend.daily_ema21_cross_date.isoformat() if uptrend.daily_ema21_cross_date else None,
        'daily_ema21_cross_price': uptrend.daily_ema21_cross_price,
        'daily_downtrend_trigger_date': uptrend.daily_downtrend_trigger_date.isoformat() if uptrend.daily_downtrend_trigger_date else None,
        'daily_downtrend_trigger_price': uptrend.daily_downtrend_trigger_price,
        'num_weeks': uptrend.num_weeks,
        'closes_above_ema': uptrend.closes_above_ema,
        'closes_below_ema': uptrend.closes_below_ema,
        'pct_closes_above': uptrend.pct_closes_above,
        'strength': uptrend.strength.name if uptrend.strength else None,
        'highest_price': uptrend.highest_price,
        'highest_price_date': uptrend.highest_price_date.isoformat() if uptrend.highest_price_date else None,
        'lowest_price': uptrend.lowest_price,
        'lowest_price_date': uptrend.lowest_price_date.isoformat() if uptrend.lowest_price_date else None
        , 'roc_1w_pct': uptrend.roc_1w_pct,
        'roc_3w_pct': uptrend.roc_3w_pct,
        'roc_6m_pct': uptrend.roc_6m_pct,
        'roc_9m_pct': uptrend.roc_9m_pct,
        'max_profit_pct': uptrend.max_profit_pct,
        'trend_roc_pct': uptrend.trend_roc_pct,
        'ema21_slope': uptrend.ema21_slope,
        'ema34_55_spread': uptrend.ema34_55_spread,
        'ema34_55_spread_pct': uptrend.ema34_55_spread_pct,
        'efficiency_ratio': uptrend.efficiency_ratio,
        'ath_price': uptrend.ath_price,
        'ath_date': uptrend.ath_date.isoformat() if uptrend.ath_date else None,
        'distance_from_ath_abs': uptrend.distance_from_ath_abs,
        'distance_from_ath_pct': uptrend.distance_from_ath_pct,
        'weekly_close_history': _serialize_history(uptrend.weekly_close_history),
        'daily_close_history': _serialize_history(uptrend.daily_close_history),
        'daily_ema21_history': _serialize_history(uptrend.daily_ema21_history),
        'daily_ema34_history': _serialize_history(uptrend.daily_ema34_history),
        'daily_ema55_history': _serialize_history(uptrend.daily_ema55_history),
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
    record.cycle_id = data.get('cycle_id')
    record.start_state = data.get('start_state')
    record.end_state = data.get('end_state')
    record.start_price = data.get('start_price')
    record.end_price = data.get('end_price')
    record.end_date = datetime.fromisoformat(data['end_date']) if data.get('end_date') else None
    record.first_buy_zone_date = datetime.fromisoformat(data['first_buy_zone_date']) if data.get('first_buy_zone_date') else None
    record.first_buy_zone_price = data.get('first_buy_zone_price')
    record.daily_ema21_cross_date = datetime.fromisoformat(data['daily_ema21_cross_date']) if data.get('daily_ema21_cross_date') else None
    record.daily_ema21_cross_price = data.get('daily_ema21_cross_price')
    record.daily_downtrend_trigger_date = datetime.fromisoformat(data['daily_downtrend_trigger_date']) if data.get('daily_downtrend_trigger_date') else None
    record.daily_downtrend_trigger_price = data.get('daily_downtrend_trigger_price')
    record.num_weeks = data.get('num_weeks', 0)
    record.closes_above_ema = data.get('closes_above_ema', 0)
    record.closes_below_ema = data.get('closes_below_ema', 0)
    record.pct_closes_above = data.get('pct_closes_above', 0.0)
    record.strength = UptrendStrength[data['strength']] if data.get('strength') else None
    record.highest_price = data.get('highest_price')
    record.highest_price_date = datetime.fromisoformat(data['highest_price_date']) if data.get('highest_price_date') else None
    record.lowest_price = data.get('lowest_price')
    record.lowest_price_date = datetime.fromisoformat(data['lowest_price_date']) if data.get('lowest_price_date') else None
    record.roc_1w_pct = data.get('roc_1w_pct')
    record.roc_3w_pct = data.get('roc_3w_pct')
    record.roc_6m_pct = data.get('roc_6m_pct')
    record.roc_9m_pct = data.get('roc_9m_pct')
    record.max_profit_pct = data.get('max_profit_pct')
    record.trend_roc_pct = data.get('trend_roc_pct')
    record.ema21_slope = data.get('ema21_slope')
    record.ema34_55_spread = data.get('ema34_55_spread')
    record.ema34_55_spread_pct = data.get('ema34_55_spread_pct')
    record.efficiency_ratio = data.get('efficiency_ratio')
    record.ath_price = data.get('ath_price')
    record.ath_date = datetime.fromisoformat(data['ath_date']) if data.get('ath_date') else None
    record.distance_from_ath_abs = data.get('distance_from_ath_abs')
    record.distance_from_ath_pct = data.get('distance_from_ath_pct')
    record.weekly_close_history = _deserialize_history(data.get('weekly_close_history'))
    record.daily_close_history = _deserialize_history(data.get('daily_close_history'))
    record.daily_ema21_history = _deserialize_history(data.get('daily_ema21_history'))
    record.daily_ema34_history = _deserialize_history(data.get('daily_ema34_history'))
    record.daily_ema55_history = _deserialize_history(data.get('daily_ema55_history'))

    return record
