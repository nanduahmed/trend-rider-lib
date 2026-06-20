"""
Generic serializer / deserializer for @dataclass instances.

Supports:
- datetime → ISO string (and back)
- Enum → .name (and back)
- Nested dataclass instances (recursive)
- list[...] of dataclass instances
- NaN → None for float fields
- @property-backed fields (read via property, write via setter)
- Optional[T] fields where value is None
"""
from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

T = TypeVar("T")


def to_dict(obj: Any) -> Dict[str, Any]:
    """Serialize any @dataclass instance to a JSON-compatible dict.

    Handles datetime → ISO string, Enum → name, nested dataclasses,
    lists of dataclasses, and NaN → None.
    """
    if not is_dataclass(obj):
        raise TypeError(f"Expected a dataclass instance, got {type(obj).__name__}")

    result: Dict[str, Any] = {}
    cls = type(obj)

    for f in fields(cls):
        # Skip private fields that are not exposed as properties
        name = f.name

        # Read the value — could be a plain field or a @property
        raw = _get_field_value(obj, name)
        if raw is None:
            result[name] = None
            continue

        result[name] = _encode_value(raw)

    return result


def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
    """Reconstruct a @dataclass instance from a dict.

    Handles ISO string → datetime, Enum name → Enum, nested dicts → nested
    dataclass, lists of dicts → lists of dataclass, and None → None.
    """
    if not is_dataclass(cls):
        raise TypeError(f"Expected a dataclass type, got {cls.__name__}")

    init_kwargs: Dict[str, Any] = {}
    post_init_kwargs: Dict[str, Any] = {}

    for f in fields(cls):
        if f.name not in data:
            continue

        raw = data[f.name]
        target_type = f.type

        # Unwrap Optional[T]
        actual_type, is_optional = _unwrap_optional(target_type)

        if raw is None:
            init_kwargs[f.name] = None
            continue

        # Resolve the decoded value
        decoded = _decode_value(raw, actual_type, f.name)
        init_kwargs[f.name] = decoded

    # Build the instance
    # Use init=False fields separately (e.g., _tr_qualified)
    init_fields = {k: v for k, v in init_kwargs.items()}
    obj = cls(**init_fields)

    # Now set values that go through property setters (not __init__ fields)
    for f in fields(cls):
        if f.name not in data:
            continue
        # If the field has a property with a setter on the class, use it
        prop = _get_property(cls, f.name)
        if prop is not None and prop.fset is not None:
            raw = data[f.name]
            target_type = f.type
            actual_type, is_optional = _unwrap_optional(target_type)
            decoded = _decode_value(raw, actual_type, f.name)
            prop.fset(obj, decoded)

    return obj


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_field_value(obj: Any, name: str) -> Any:
    """Read a field value, respecting @property accessors."""
    cls = type(obj)
    prop = _get_property(cls, name)
    if prop is not None:
        return prop.fget(obj)
    return getattr(obj, name)


def _get_property(cls: type, name: str):
    """Return the property descriptor for *name* on *cls*, or None."""
    for base in cls.__mro__:
        if name in base.__dict__:
            attr = base.__dict__[name]
            if isinstance(attr, property):
                return attr
    return None


def _encode_value(val: Any) -> Any:
    """Recursively encode a value for JSON."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, Enum):
        return val.name
    if is_dataclass(val):
        return to_dict(val)
    if isinstance(val, list):
        return [_encode_value(item) for item in val]
    if isinstance(val, tuple):
        return [_encode_value(item) for item in val]
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def _decode_value(val: Any, target_type: type, field_name: str) -> Any:
    """Recursively decode a JSON-compatible value into *target_type*."""
    # datetime from ISO string
    if target_type is datetime and isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return val

    # Enum from name string
    if isinstance(target_type, type) and issubclass(target_type, Enum) and isinstance(val, str):
        try:
            return target_type[val]
        except (KeyError, ValueError):
            return val

    # Nested dataclass from dict
    if is_dataclass(target_type) and isinstance(val, dict):
        return from_dict(target_type, val)

    # List of dataclass from list of dicts
    if target_type is not None and hasattr(target_type, "__origin__"):
        origin = getattr(target_type, "__origin__", None)
        args = getattr(target_type, "__args__", [])
        if origin is list and len(args) == 1 and isinstance(val, list):
            item_type = args[0]
            if is_dataclass(item_type):
                return [from_dict(item_type, item) if isinstance(item, dict) else item for item in val]
            return [_decode_value(item, item_type, field_name) for item in val]

    return val


def _unwrap_optional(tp) -> tuple[type, bool]:
    """Given a type annotation, return (inner_type, is_optional).

    Examples:
        Optional[datetime] → (datetime, True)
        datetime           → (datetime, False)
        Optional[List[int]] → (List[int], True)
    """
    origin = getattr(tp, "__origin__", None)
    args = getattr(tp, "__args__", [])
    if origin is type(Union) or (hasattr(tp, "_name") and tp._name == "Optional"):
        # Optional[X] = Union[X, None]
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return non_none_args[0], True
    return tp, False
