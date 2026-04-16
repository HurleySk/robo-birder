"""Tests for watchlist Discord embed formatting."""

from unittest.mock import patch
from robo_birder.discord import send_watchlist_alert, COLOR_WATCHLIST


def test_watchlist_alert_basic(sample_detection):
    """Watchlist alert has correct color and title."""
    with patch("robo_birder.discord.send_webhook", return_value=True) as mock:
        result = send_watchlist_alert(
            "https://discord.com/api/webhooks/test/test",
            sample_detection,
            image_url="https://example.com/bird.jpg",
            birdnet_base_url="http://localhost:8080",
        )

    assert result is True
    payload = mock.call_args[0][1]
    embed = payload["embeds"][0]
    assert embed["color"] == COLOR_WATCHLIST
    assert "WATCHLIST" in embed["title"]
    assert "Pileated Woodpecker" in embed["title"]
    assert "NEW" not in embed["title"]


def test_watchlist_alert_with_new_species(sample_detection):
    """Watchlist + new species shows combined title and reason."""
    with patch("robo_birder.discord.send_webhook", return_value=True) as mock:
        result = send_watchlist_alert(
            "https://discord.com/api/webhooks/test/test",
            sample_detection,
            image_url=None,
            birdnet_base_url="http://localhost:8080",
            is_new_species=True,
            new_reason="First ever sighting!",
        )

    assert result is True
    payload = mock.call_args[0][1]
    embed = payload["embeds"][0]
    assert "WATCHLIST" in embed["title"]
    assert "NEW" in embed["title"]

    # Check that the new species reason appears in fields
    field_values = " ".join(f["value"] for f in embed["fields"])
    assert "First ever sighting!" in field_values


def test_watchlist_alert_has_detection_link(sample_detection):
    """Watchlist alert includes link to BirdNet Go detection."""
    with patch("robo_birder.discord.send_webhook", return_value=True) as mock:
        send_watchlist_alert(
            "https://discord.com/api/webhooks/test/test",
            sample_detection,
            birdnet_base_url="http://localhost:8080",
        )

    payload = mock.call_args[0][1]
    embed = payload["embeds"][0]
    assert embed["url"] == "http://localhost:8080/ui/detections/42"


def test_watchlist_color_is_distinct():
    """Watchlist color is distinct from other alert colors."""
    from robo_birder.discord import COLOR_NEW_SPECIES, COLOR_DETECTION, COLOR_SUMMARY

    assert COLOR_WATCHLIST != COLOR_NEW_SPECIES
    assert COLOR_WATCHLIST != COLOR_DETECTION
    assert COLOR_WATCHLIST != COLOR_SUMMARY
