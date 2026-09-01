"""Saved sidebar filter combinations, stored per user."""

from __future__ import annotations

import json

from . import db
from .config import MAX_PRESET_NAME_LENGTH
from .utils import truncate


def save_filter_preset(user_id, name, payload) -> tuple[bool, str]:
    """Create or overwrite a named filter preset."""
    name = truncate(name, MAX_PRESET_NAME_LENGTH)
    if not name:
        return False, "Preset name cannot be empty."
    try:
        encoded = json.dumps(payload)
    except (TypeError, ValueError):
        return False, "These filters cannot be saved."
    db.execute(
        """
        INSERT INTO filter_presets (user_id, name, payload)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, name) DO UPDATE SET payload = excluded.payload
        """,
        (user_id, name, encoded),
    )
    return True, f"Preset '{name}' saved."


def get_filter_presets(user_id) -> list[dict]:
    """Every preset belonging to a user, ignoring any that fail to decode."""
    rows = db.fetch_all(
        "SELECT name, payload FROM filter_presets WHERE user_id = ? ORDER BY LOWER(name)",
        (user_id,),
    )
    presets = []
    for row in rows:
        try:
            presets.append({"name": row["name"], "payload": json.loads(row["payload"])})
        except (TypeError, ValueError):
            continue
    return presets


def delete_filter_preset(user_id, name) -> tuple[bool, str]:
    """Remove a preset by name."""
    removed = db.execute(
        "DELETE FROM filter_presets WHERE user_id = ? AND name = ?", (user_id, name)
    )
    if not removed:
        return False, "That preset no longer exists."
    return True, "Preset deleted."
