"""Per-thread runtime context (not visible to the LLM)."""

from __future__ import annotations

_context: dict[str, dict] = {}


def set_thread_context(thread_id: str, **kwargs) -> None:
    ctx = _context.setdefault(thread_id, {})
    ctx.update(kwargs)


def get_thread_context(thread_id: str) -> dict:
    return _context.get(thread_id, {})
