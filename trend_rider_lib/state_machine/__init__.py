"""
State Machine module for stock trend analysis.
"""
from .fsm import StockFSM
from .classifier import classify_stock, update_classification
from .fsm_serializer import (
    serialize_context,
    deserialize_context,
    serialize_uptrend,
    deserialize_uptrend,
)

__all__ = [
    "StockFSM",
    "classify_stock",
    "update_classification",
    "serialize_context",
    "deserialize_context",
    "serialize_uptrend",
    "deserialize_uptrend",
]
