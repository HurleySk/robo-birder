"""Tests for watchlist configuration parsing."""

from robo_birder.config import get_watchlist_species, is_watchlist_enabled


def test_get_watchlist_species_returns_lowercase_set(watchlist_config):
    result = get_watchlist_species(watchlist_config)
    assert result == {"pileated woodpecker", "barred owl", "eastern bluebird"}


def test_get_watchlist_species_empty_when_disabled(watchlist_config_disabled):
    result = get_watchlist_species(watchlist_config_disabled)
    assert result == set()


def test_get_watchlist_species_empty_when_missing():
    config = {"discord": {"webhook_url": "test"}}
    result = get_watchlist_species(config)
    assert result == set()


def test_is_watchlist_enabled_true(watchlist_config):
    assert is_watchlist_enabled(watchlist_config) is True


def test_is_watchlist_enabled_false(watchlist_config_disabled):
    assert is_watchlist_enabled(watchlist_config_disabled) is False


def test_is_watchlist_enabled_missing_section():
    config = {"discord": {"webhook_url": "test"}}
    assert is_watchlist_enabled(config) is False
