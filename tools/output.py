import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def clamp_limit(limit: int, *, default: int = 25, maximum: int = 100) -> int:
    """Clamp user-facing pagination limits to context-safe bounds."""
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = default
    return max(1, min(maximum, value))


def clamp_offset(offset: int) -> int:
    try:
        return max(0, int(offset))
    except (TypeError, ValueError):
        return 0


def page_items(items: list[Any], *, limit: int, offset: int) -> tuple[list[Any], dict[str, Any]]:
    safe_limit = clamp_limit(limit)
    safe_offset = clamp_offset(offset)
    total = len(items)
    next_offset = safe_offset + safe_limit if safe_offset + safe_limit < total else None
    return items[safe_offset : safe_offset + safe_limit], {
        "limit": safe_limit,
        "offset": safe_offset,
        "total_count": total,
        "next_offset": next_offset,
        "has_more": next_offset is not None,
    }


def save_json_response(payload: Any, *, prefix: str) -> str:
    """Save a full tool payload to a local JSON file and return its path."""
    output_dir = Path(os.environ.get("MONARCH_MCP_OUTPUT_DIR", tempfile.gettempdir()))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}-{int(time.time() * 1000)}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def ensure_context_safe_response(
    payload: dict[str, Any],
    *,
    fallback: dict[str, Any],
    prefix: str,
    max_bytes: int = 750_000,
) -> dict[str, Any]:
    """Keep MCP tool results below client decode limits by saving oversized data."""
    encoded = json.dumps(payload, default=str).encode("utf-8")
    if len(encoded) <= max_bytes:
        return payload

    safe_payload = dict(fallback)
    safe_payload["full_response_path"] = save_json_response(payload, prefix=prefix)
    safe_payload["saved_due_to_size"] = True
    safe_payload["omitted_response_bytes"] = len(encoded)
    safe_payload["message"] = (
        "The requested detail payload was too large for an MCP tool result, "
        "so the full response was saved to full_response_path."
    )
    return safe_payload
