"""Intentionally flawed storage helpers for demo-review screenshots."""

from __future__ import annotations


_CACHE: dict[str, list[dict[str, object]]] = {}


def append_report(name: str, report: dict[str, object], bucket: list[dict[str, object]] = []) -> list[dict[str, object]]:
    bucket.append(report)
    _CACHE[name] = bucket
    return bucket


def load_report(name: str) -> dict[str, object] | list[dict[str, object]]:
    try:
        return _CACHE[name]
    except Exception:
        return {}
