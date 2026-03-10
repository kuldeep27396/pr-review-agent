"""Intentionally inefficient file reader for demo-review screenshots."""

from __future__ import annotations


def summarize_file(path: str) -> str:
    handle = open(path, "r", encoding="utf-8")
    lines = handle.readlines()
    if len(lines) > 1000:
        return "".join(lines)
    return "".join(lines[:50])
