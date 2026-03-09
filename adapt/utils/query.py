"""
adapt.utils.query
Utility functions for applying query parameters to data.
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def apply_filter(rows: List[Dict[str, Any]], filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply filter conditions to a list of row dictionaries."""
    if not filter_dict:
        return rows

    filtered = []
    for row in rows:
        if _matches_all_conditions(row, filter_dict):
            filtered.append(row)
    return filtered


def _matches_all_conditions(row: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
    """Check if row matches all filter conditions."""
    for key, condition in conditions.items():
        if key == "$and":
            # Handle $and operator for multiple conditions
            if isinstance(condition, list):
                for sub_condition in condition:
                    if isinstance(sub_condition, dict):
                        if not _matches_all_conditions(row, sub_condition):
                            return False
                    else:
                        return False  # Invalid $and format
            else:
                return False  # $and must be a list
        elif key not in row:
            return False
        elif isinstance(condition, dict):
            # Advanced conditions: {"$gt": 100}, {"$contains": "text"}
            if not _matches_condition(row[key], condition):
                return False
        else:
            # Simple equality
            if row[key] != condition:
                return False
    return True


def _matches_condition(value: Any, condition: Dict[str, Any]) -> bool:
    """Check if value matches a condition dict."""
    import re
    for op, val in condition.items():
        if op == "$gt" and not (value > val if value is not None else False):
            return False
        elif op == "$gte" and not (value >= val if value is not None else False):
            return False
        elif op == "$lt" and not (value < val if value is not None else False):
            return False
        elif op == "$lte" and not (value <= val if value is not None else False):
            return False
        elif op == "$contains" and (val not in str(value) if value is not None else True):
            return False
        elif op == "$startswith" and (not str(value).startswith(val) if value is not None else True):
            return False
        elif op == "$regex" and (not re.search(val, str(value)) if value is not None else True):
            return False
        elif op == "$eq" and value != val:
            return False
        elif op == "$ne" and value == val:
            return False
    return True


def apply_sort(rows: List[Dict[str, Any]], sort_key: str, order: str = "asc") -> List[Dict[str, Any]]:
    """Sort rows by a key."""
    if not sort_key:
        return rows
    reverse = order.lower() == "desc"
    try:
        return sorted(rows, key=lambda x: x.get(sort_key, ""), reverse=reverse)
    except TypeError:
        # Handle mixed types by converting to strings for sorting
        return sorted(rows, key=lambda x: str(x.get(sort_key, "")), reverse=reverse)


def apply_pagination(rows: List[Dict[str, Any]], offset: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Apply offset and limit to rows."""
    start = offset or 0
    end = start + limit if limit else None
    return rows[start:end]