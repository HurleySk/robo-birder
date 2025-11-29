"""Configuration loader for Robo-Birder."""

import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is invalid YAML.
    """
    if config_path is None:
        config_path = os.environ.get("ROBO_BIRDER_CONFIG", DEFAULT_CONFIG_PATH)

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config


def get_webhook_url(config: dict[str, Any], override_url: str | None = None) -> str:
    """Get webhook URL, with optional override.

    Args:
        config: Configuration dictionary.
        override_url: Optional override URL (e.g., from summary config).

    Returns:
        Webhook URL to use.
    """
    if override_url:
        return override_url
    return config["discord"]["webhook_url"]


def get_current_season(config: dict[str, Any]) -> str:
    """Determine current season based on config definitions.

    Args:
        config: Configuration dictionary with season definitions.

    Returns:
        Current season name: 'spring', 'summer', 'fall', or 'winter'.
    """
    from datetime import datetime

    now = datetime.now()
    month, day = now.month, now.day

    seasons = config.get("seasons", {})

    # Default season boundaries if not configured
    defaults = {
        "spring": (3, 20),
        "summer": (6, 21),
        "fall": (9, 22),
        "winter": (12, 21),
    }

    boundaries = []
    for season_name in ["spring", "summer", "fall", "winter"]:
        season_cfg = seasons.get(season_name, {})
        start_month = season_cfg.get("start_month", defaults[season_name][0])
        start_day = season_cfg.get("start_day", defaults[season_name][1])
        boundaries.append((start_month, start_day, season_name))

    # Sort by month/day
    boundaries.sort(key=lambda x: (x[0], x[1]))

    # Find current season
    current_season = boundaries[-1][2]  # Default to last (winter wraps around)
    for start_month, start_day, season_name in boundaries:
        if (month, day) >= (start_month, start_day):
            current_season = season_name

    return current_season


def get_season_start_date(config: dict[str, Any], season: str, year: int) -> "datetime":
    """Get the start date of a season for a given year.

    Args:
        config: Configuration dictionary.
        season: Season name.
        year: Year.

    Returns:
        datetime object for season start.
    """
    from datetime import datetime

    seasons = config.get("seasons", {})
    defaults = {
        "spring": (3, 20),
        "summer": (6, 21),
        "fall": (9, 22),
        "winter": (12, 21),
    }

    season_cfg = seasons.get(season, {})
    start_month = season_cfg.get("start_month", defaults[season][0])
    start_day = season_cfg.get("start_day", defaults[season][1])

    return datetime(year, start_month, start_day)
