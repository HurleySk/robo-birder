"""Scheduler state persistence for tracking when summaries were last sent."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STATE_FILE = "scheduler_state.json"


def load_state(config_path: str | None) -> dict[str, Any]:
    """Load scheduler state from file.

    Args:
        config_path: Path to config file (state file is stored in same directory).

    Returns:
        State dictionary with last_sent timestamps.
    """
    state_path = _get_state_path(config_path)
    if state_path.exists():
        try:
            with open(state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load state file: {e}")
    return {"last_sent": {}}


def save_state(state: dict[str, Any], config_path: str | None) -> None:
    """Save scheduler state to file.

    Args:
        state: State dictionary to save.
        config_path: Path to config file (state file is stored in same directory).
    """
    state_path = _get_state_path(config_path)
    try:
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save state file: {e}")


def record_summary_sent(name: str, timestamp: datetime, config_path: str | None) -> None:
    """Record that a summary was sent.

    Args:
        name: Name of the summary.
        timestamp: When the summary was sent.
        config_path: Path to config file.
    """
    state = load_state(config_path)
    state["last_sent"][name] = timestamp.isoformat()
    save_state(state, config_path)
    logger.debug(f"Recorded summary '{name}' sent at {timestamp}")


def get_last_sent(name: str, config_path: str | None) -> datetime | None:
    """Get when a summary was last sent.

    Args:
        name: Name of the summary.
        config_path: Path to config file.

    Returns:
        Datetime when summary was last sent, or None if never sent.
    """
    state = load_state(config_path)
    iso_str = state.get("last_sent", {}).get(name)
    if iso_str:
        try:
            return datetime.fromisoformat(iso_str)
        except ValueError:
            logger.warning(f"Invalid timestamp for '{name}': {iso_str}")
    return None


def _get_state_path(config_path: str | None) -> Path:
    """Get path to state file (same directory as config).

    Args:
        config_path: Path to config file.

    Returns:
        Path to state file.
    """
    if config_path:
        return Path(config_path).parent / STATE_FILE
    return Path.cwd() / STATE_FILE
