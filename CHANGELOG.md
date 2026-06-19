# Changelog

All meaningful changes to this project are documented here.

## 2026-06-19

- Converted StockContext, UptrendRecord, SignalEvent, TrendEventRecord, and
  TradeRecord to `@dataclass`.
- `tr_qualified` is now enforced as a one-way latch via `__setattr__` —
  once `True`, it can never be reset to `False`.
- Consolidated two serialization layers (`models.py:to_dict/from_dict` and
  `fsm_serializer.py:serialize_context/deserialize_context`) into single
  generic functions. The `fsm_serializer` module remains as a thin public
  façade that handles only the custom tuple-history format.
- `context_from_dict` is now an alias for `StockContext.from_dict`; no caller
  changes required.