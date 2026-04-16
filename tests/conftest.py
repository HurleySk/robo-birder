"""Shared test fixtures for robo-birder tests."""

import pytest
from datetime import datetime
from robo_birder.database import Detection


@pytest.fixture
def sample_detection():
    """A standard detection for testing."""
    return Detection(
        id=42,
        date="2026-04-16",
        time="14:30:00",
        begin_time=datetime(2026, 4, 16, 14, 30, 0),
        scientific_name="Dryocopus pileatus",
        common_name="Pileated Woodpecker",
        confidence=0.85,
        clip_name="clip_042.wav",
        species_code="pilwoo",
    )


@pytest.fixture
def sample_detection_unlisted():
    """A detection for a species NOT on the watchlist."""
    return Detection(
        id=43,
        date="2026-04-16",
        time="14:35:00",
        begin_time=datetime(2026, 4, 16, 14, 35, 0),
        scientific_name="Cardinalis cardinalis",
        common_name="Northern Cardinal",
        confidence=0.92,
        clip_name="clip_043.wav",
        species_code="norcar",
    )


@pytest.fixture
def watchlist_config():
    """Config with watchlist enabled."""
    return {
        "discord": {"webhook_url": "https://discord.com/api/webhooks/test/test"},
        "birdnet": {
            "db_type": "sqlite",
            "db_path": ":memory:",
            "base_url": "http://localhost:8080",
        },
        "watchlist": {
            "enabled": True,
            "species": ["Pileated Woodpecker", "Barred Owl", "Eastern Bluebird"],
            "cooldown_minutes": 60,
            "webhook_url": None,
        },
        "new_species": {
            "enabled": True,
            "min_confidence": 0.5,
            "cooldown_minutes": 5,
            "notify_on": {
                "first_ever": True,
                "first_of_year": True,
                "first_of_season": False,
            },
        },
        "realtime": {"enabled": False},
    }


@pytest.fixture
def watchlist_config_disabled():
    """Config with watchlist disabled."""
    return {
        "discord": {"webhook_url": "https://discord.com/api/webhooks/test/test"},
        "birdnet": {
            "db_type": "sqlite",
            "db_path": ":memory:",
            "base_url": "http://localhost:8080",
        },
        "watchlist": {"enabled": False, "species": [], "cooldown_minutes": 60},
        "new_species": {"enabled": False},
        "realtime": {"enabled": False},
    }
