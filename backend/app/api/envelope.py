"""The collection envelope (ADR-0011 convention): every ``GET`` of a list wraps its items."""

from __future__ import annotations

from typing import Any

_PAGE_SIZE = 20


def envelope(
    items: list[Any], *, page: int = 1, token: str | None = None
) -> dict[str, Any]:
    """Wrap ``items`` in the frozen ``{items, page, page_size, token}`` shape."""
    return {"items": items, "page": page, "page_size": _PAGE_SIZE, "token": token}
