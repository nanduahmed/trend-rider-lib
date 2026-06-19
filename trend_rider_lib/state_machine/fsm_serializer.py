"""
FSM state serialization and deserialization for persistence.

This module is a thin public façade.  The heavy lifting (datetime↔str,
Enum↔str, nested dataclass handling) is done by the generic serializer in
``core.dataclass_serializer``.  Only the custom tuple‑history format
``(datetime, float) → [iso_str, value]`` is handled here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..core.models import StockContext, UptrendRecord

# ---------------------------------------------------------------------------
# History helpers – custom tuple format not expressible via dataclass type
# annotations alone.
# ---------------------------------------------------------------------------


def _serialize_history(history: List[Tuple[Optional[datetime], float]]) -> List[list]:
    """Convert ``[(date, price), …]`` → ``[[iso_str, price], …]``."""
    return [
        [item[0].isoformat() if item[0] else None, item[1]]
        for item in history
    ]


def _deserialize_history(data: Optional[List[list]]) -> List[Tuple[Optional[datetime], float]]:
    """Convert ``[[iso_str, price], …]`` → ``[(datetime, price), …]``."""
    history: List[Tuple[Optional[datetime], float]] = []
    for item in data or []:
        if not item:
            continue
        date_value = datetime.fromisoformat(item[0]) if item[0] else None
        if date_value is None:
            continue
        history.append((date_value, item[1]))
    return history


# ---------------------------------------------------------------------------
# Public API – thin wrappers
# ---------------------------------------------------------------------------


def serialize_context(context: StockContext) -> Dict[str, Any]:
    """Serialize StockContext → dict (delegates to ``StockContext.to_dict``)."""
    d = context.to_dict()

    # History lists need the custom tuple→list encoding
    if context.current_uptrend:
        d["current_uptrend"] = serialize_uptrend(context.current_uptrend)
    d["uptrend_history"] = [serialize_uptrend(u) for u in (context.uptrend_history or [])]

    return d


def deserialize_context(data: Dict[str, Any]) -> StockContext:
    """Deserialize dict → StockContext (delegates to ``StockContext.from_dict``)."""
    # Pop history sub‑dicts so the generic serializer doesn't see them
    cu_data = data.pop("current_uptrend", None)
    uh_data = data.pop("uptrend_history", None)

    ctx = StockContext.from_dict(data)

    # Restore uptrends with custom history deserialization
    if cu_data and isinstance(cu_data, dict):
        ctx.current_uptrend = deserialize_uptrend(cu_data)
    if uh_data and isinstance(uh_data, list):
        ctx.uptrend_history = [deserialize_uptrend(u) for u in uh_data if isinstance(u, dict)]

    return ctx


def serialize_uptrend(uptrend: UptrendRecord) -> Dict[str, Any]:
    """Serialize UptrendRecord → dict (delegates to ``UptrendRecord.to_dict``)."""
    d = uptrend.to_dict()

    # Overwrite history fields with the custom tuple→list format
    for hist_field in (
        "weekly_close_history", "daily_close_history",
        "daily_ema21_history", "daily_ema34_history", "daily_ema55_history",
    ):
        val = getattr(uptrend, hist_field, [])
        d[hist_field] = _serialize_history(val)

    return d


def deserialize_uptrend(data: Dict[str, Any]) -> UptrendRecord:
    """Deserialize dict → UptrendRecord (delegates to ``UptrendRecord.from_dict``)."""
    # Extract history fields before the generic serializer processes them
    history_fields: Dict[str, list] = {}
    for hist_field in (
        "weekly_close_history", "daily_close_history",
        "daily_ema21_history", "daily_ema34_history", "daily_ema55_history",
    ):
        if hist_field in data:
            history_fields[hist_field] = data.pop(hist_field)

    record = UptrendRecord.from_dict(data)

    # Restore history with custom format conversion
    for field_name, raw in history_fields.items():
        setattr(record, field_name, _deserialize_history(raw))

    return record