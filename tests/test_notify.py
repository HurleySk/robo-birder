"""Tests for watchlist notification logic."""

from unittest.mock import patch
from robo_birder.notify import (
    check_watchlist,
    is_on_cooldown,
    set_cooldown,
    handle_detection,
)


class TestCheckWatchlist:
    def test_watchlisted_species_detected(self, sample_detection, watchlist_config):
        """Pileated Woodpecker is on the watchlist - should return True."""
        assert check_watchlist(sample_detection, watchlist_config) is True

    def test_unlisted_species_not_detected(self, sample_detection_unlisted, watchlist_config):
        """Northern Cardinal is NOT on the watchlist - should return False."""
        assert check_watchlist(sample_detection_unlisted, watchlist_config) is False

    def test_case_insensitive_match(self, sample_detection, watchlist_config):
        """Match should be case-insensitive."""
        watchlist_config["watchlist"]["species"] = ["pileated woodpecker"]
        assert check_watchlist(sample_detection, watchlist_config) is True

    def test_disabled_watchlist(self, sample_detection, watchlist_config_disabled):
        """Disabled watchlist returns False."""
        assert check_watchlist(sample_detection, watchlist_config_disabled) is False


class TestWatchlistCooldown:
    def test_not_on_cooldown_initially(self, tmp_path):
        """Species not on cooldown if never notified."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            assert is_on_cooldown("watchlist:Dryocopus pileatus", 60) is False

    def test_on_cooldown_after_set(self, tmp_path):
        """Species is on cooldown after set_cooldown."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            set_cooldown("watchlist:Dryocopus pileatus")
            assert is_on_cooldown("watchlist:Dryocopus pileatus", 60) is True

    def test_separate_from_realtime_cooldown(self, tmp_path):
        """Watchlist cooldown key is separate from realtime cooldown key."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            set_cooldown("Dryocopus pileatus")  # realtime key
            assert is_on_cooldown("watchlist:Dryocopus pileatus", 60) is False


class TestHandleDetectionWatchlist:
    @patch("robo_birder.notify.get_bird_image_url", return_value="https://example.com/bird.jpg")
    @patch("robo_birder.notify.send_watchlist_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(False, None))
    def test_watchlisted_species_sends_watchlist_alert(
        self, mock_new, mock_watchlist_alert, mock_img, sample_detection, watchlist_config, tmp_path
    ):
        """Watchlisted species that is not new sends watchlist alert."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            result = handle_detection(sample_detection, watchlist_config)

        assert result is True
        mock_watchlist_alert.assert_called_once()
        _, kwargs = mock_watchlist_alert.call_args
        assert kwargs.get("is_new_species", False) is False

    @patch("robo_birder.notify.get_bird_image_url", return_value="https://example.com/bird.jpg")
    @patch("robo_birder.notify.send_watchlist_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(True, "First ever sighting!"))
    def test_watchlisted_new_species_sends_combined_alert(
        self, mock_new, mock_watchlist_alert, mock_img, sample_detection, watchlist_config, tmp_path
    ):
        """Watchlisted species that IS new sends one combined alert."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            result = handle_detection(sample_detection, watchlist_config)

        assert result is True
        mock_watchlist_alert.assert_called_once()
        _, kwargs = mock_watchlist_alert.call_args
        assert kwargs["is_new_species"] is True
        assert kwargs["new_reason"] == "First ever sighting!"

    @patch("robo_birder.notify.get_bird_image_url", return_value=None)
    @patch("robo_birder.notify.send_new_species_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(True, "First ever sighting!"))
    def test_non_watchlisted_new_species_uses_existing_alert(
        self, mock_new, mock_new_alert, mock_img, sample_detection_unlisted, watchlist_config, tmp_path
    ):
        """Non-watchlisted new species uses the existing new species alert path."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            result = handle_detection(sample_detection_unlisted, watchlist_config)

        assert result is True
        mock_new_alert.assert_called_once()

    @patch("robo_birder.notify.get_bird_image_url", return_value=None)
    @patch("robo_birder.notify.send_watchlist_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(False, None))
    def test_watchlist_cooldown_suppresses_repeat(
        self, mock_new, mock_watchlist_alert, mock_img, sample_detection, watchlist_config, tmp_path
    ):
        """Second watchlist detection within cooldown window is suppressed."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            handle_detection(sample_detection, watchlist_config)
            mock_watchlist_alert.reset_mock()

            result = handle_detection(sample_detection, watchlist_config)

        assert result is False
        mock_watchlist_alert.assert_not_called()

    @patch("robo_birder.notify.get_bird_image_url", return_value=None)
    @patch("robo_birder.notify.send_watchlist_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(True, "First ever sighting!"))
    def test_new_species_bypasses_watchlist_cooldown(
        self, mock_new, mock_watchlist_alert, mock_img, sample_detection, watchlist_config, tmp_path
    ):
        """New species detection bypasses watchlist cooldown."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            # Set cooldown (simulate recent notification)
            set_cooldown(f"watchlist:{sample_detection.scientific_name}")

            result = handle_detection(sample_detection, watchlist_config)

        assert result is True
        mock_watchlist_alert.assert_called_once()


class TestHandleDetectionEdgeCases:
    @patch("robo_birder.notify.get_bird_image_url", return_value=None)
    @patch("robo_birder.notify.send_watchlist_alert", return_value=False)
    @patch("robo_birder.notify.check_new_species", return_value=(False, None))
    def test_watchlist_alert_failure_returns_false_no_cooldown(
        self, mock_new, mock_alert, mock_img, sample_detection, watchlist_config, tmp_path
    ):
        """Webhook failure returns False and does not set cooldown."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            result = handle_detection(sample_detection, watchlist_config)
        assert result is False

    @patch("robo_birder.notify.get_bird_image_url", return_value=None)
    @patch("robo_birder.notify.send_watchlist_alert", return_value=False)
    @patch("robo_birder.notify.send_new_species_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(True, "First ever sighting!"))
    def test_watchlist_failure_falls_back_to_new_species_alert(
        self, mock_new, mock_new_alert, mock_watchlist_alert, mock_img,
        sample_detection, watchlist_config, tmp_path
    ):
        """If watchlist alert fails for a new species, falls back to new-species alert."""
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            result = handle_detection(sample_detection, watchlist_config)
        assert result is True
        mock_new_alert.assert_called_once()

    @patch("robo_birder.notify.get_bird_image_url", return_value=None)
    @patch("robo_birder.notify.send_detection_alert", return_value=True)
    @patch("robo_birder.notify.check_new_species", return_value=(False, None))
    def test_non_watchlisted_non_new_uses_realtime(
        self, mock_new, mock_realtime_alert, mock_img,
        sample_detection_unlisted, tmp_path
    ):
        """Non-watchlisted, non-new species with realtime enabled uses realtime path."""
        config = {
            "discord": {"webhook_url": "https://discord.com/api/webhooks/test/test"},
            "birdnet": {
                "db_type": "sqlite",
                "db_path": ":memory:",
                "base_url": "http://localhost:8080",
            },
            "watchlist": {"enabled": False, "species": []},
            "new_species": {"enabled": False},
            "realtime": {
                "enabled": True,
                "min_confidence": 0.5,
                "cooldown_minutes": 5,
                "species_whitelist": [],
                "species_blacklist": [],
            },
        }
        cooldown_file = tmp_path / "cooldowns.json"
        with patch("robo_birder.notify.COOLDOWN_FILE", cooldown_file):
            result = handle_detection(sample_detection_unlisted, config)
        assert result is True
        mock_realtime_alert.assert_called_once()
