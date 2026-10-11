"""Deliberately narrow canonical data format shared by the local experiments."""
from __future__ import annotations
import hashlib
import json
import re
from typing import Any

class Rejected(ValueError):
    """Expected refusal; the reason code intentionally contains no input values."""

def canonical(value: Any) -> bytes:
    def check(v: Any, depth: int = 0) -> None:
        if depth > 20:
            raise Rejected('DATA_TOO_DEEP')
        if v is None or type(v) in (str, bool, int):
            if type(v) is int and not -(2**63) <= v < 2**63:
                raise Rejected('INTEGER_RANGE')
            return
        if type(v) is list:
            if len(v) > 10000:
                raise Rejected('DATA_TOO_LARGE')
            for x in v:
                check(x, depth + 1)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for x in v.values():
                check(x, depth + 1)
            return
        # Floats, custom objects and implicit string conversion are forbidden.
        raise Rejected('UNSUPPORTED_DATA_TYPE')
    check(value)
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode('ascii')
    if len(raw) > 1_000_000:
        raise Rejected('DATA_TOO_LARGE')
    return raw

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def integer(value: Any, lo: int, hi: int, code: str = 'INVALID_INTEGER') -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise Rejected(code)
    return value

def label(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}', value):
        raise Rejected('INVALID_LABEL')
    return value

def sha256_text(value: Any) -> str:
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise Rejected('INVALID_DIGEST')
    return value
