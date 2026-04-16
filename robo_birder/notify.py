"""Real-time notification handler for Robo-Birder."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import get_current_season, get_season_start_date, get_watchlist_species, get_webhook_url
from .database import (
    Detection,
    get_bird_image_url,
    get_detection_by_id,
    get_latest_detection,
    get_species_count,
    get_species_count_since,
    species_exists_in_db,
    species_seen_since,
    species_seen_this_year,
)
from .discord import send_detection_alert, send_new_species_alert, send_watchlist_alert

logger = logging.getLogger(__name__)

# Cooldown tracking file
COOLDOWN_FILE = Path("/tmp/robo_birder_cooldowns.json")


def load_cooldowns() -> dict[str, float]:
    """Load cooldown timestamps from file.

    Returns:
        Dictionary mapping species to last notification timestamp.
    """
    if not COOLDOWN_FILE.exists():
        return {}

    try:
        with open(COOLDOWN_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cooldowns(cooldowns: dict[str, float]) -> None:
    """Save cooldown timestamps to file.

    Args:
        cooldowns: Dictionary mapping species to last notification timestamp.
    """
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(cooldowns, f)
    except OSError as e:
        logger.warning(f"Failed to save cooldowns: {e}")


def is_on_cooldown(species: str, cooldown_minutes: int) -> bool:
    """Check if a species is on notification cooldown.

    Args:
        species: Species name (scientific or common).
        cooldown_minutes: Cooldown period in minutes.

    Returns:
        True if species is on cooldown.
    """
    if cooldown_minutes <= 0:
        return False

    cooldowns = load_cooldowns()
    last_notified = cooldowns.get(species, 0)
    cooldown_seconds = cooldown_minutes * 60

    return (time.time() - last_notified) < cooldown_seconds


def set_cooldown(species: str) -> None:
    """Set cooldown timestamp for a species.

    Args:
        species: Species name.
    """
    cooldowns = load_cooldowns()
    cooldowns[species] = time.time()

    # Clean up old entries (older than 24 hours)
    cutoff = time.time() - 86400
    cooldowns = {k: v for k, v in cooldowns.items() if v > cutoff}

    save_cooldowns(cooldowns)


def check_new_species(
    detection: Detection, config: dict[str, Any], db_config: dict[str, Any]
) -> tuple[bool, str | None]:
    """Check if a detection qualifies as a new species.

    Args:
        detection: Detection record.
        config: Configuration dictionary.
        db_config: Database configuration dict.

    Returns:
        Tuple of (is_new, reason_string).
    """
    new_species_config = config.get("new_species", {})

    if not new_species_config.get("enabled", False):
        return False, None

    min_confidence = new_species_config.get("min_confidence", 0.5)
    if detection.confidence < min_confidence:
        return False, None

    # Check cooldown to prevent duplicate alerts
    cooldown_minutes = new_species_config.get("cooldown_minutes", 5)
    if is_on_cooldown(detection.scientific_name, cooldown_minutes):
        return False, None

    notify_on = new_species_config.get("notify_on", {})
    scientific_name = detection.scientific_name

    # Check first ever (need to check if this is the ONLY occurrence)
    # Since the detection is already in the DB, we check for more than 1 occurrence
    if notify_on.get("first_ever", False):
        count = get_species_count(db_config, scientific_name)
        if count == 1:  # This detection is the only one
            return True, "First ever sighting!"

    # Check first of year
    if notify_on.get("first_of_year", False):
        year_start = datetime(datetime.now().year, 1, 1)
        # Check if there are other detections this year before this one
        count = get_species_count_since(db_config, scientific_name, year_start, detection.id)
        if count == 0:
            return True, f"First sighting of {datetime.now().year}!"

    # Check first of season
    if notify_on.get("first_of_season", False):
        current_season = get_current_season(config)
        year = datetime.now().year

        # Handle winter crossing year boundary
        if current_season == "winter" and datetime.now().month < 3:
            year -= 1

        season_start = get_season_start_date(config, current_season, year)
        count = get_species_count_since(db_config, scientific_name, season_start, detection.id)
        if count == 0:
            season_name = current_season.capitalize()
            return True, f"First sighting of {season_name}!"

    return False, None



def check_watchlist(detection: Detection, config: dict[str, Any]) -> bool:
    """Check if a detection is for a watchlisted species.

    Args:
        detection: Detection record.
        config: Configuration dictionary.

    Returns:
        True if species is on the watchlist.
    """
    watchlist = get_watchlist_species(config)
    if not watchlist:
        return False

    return detection.common_name.lower() in watchlist


def should_notify_realtime(
    detection: Detection, config: dict[str, Any]
) -> bool:
    """Check if a detection should trigger a realtime notification.

    Args:
        detection: Detection record.
        config: Configuration dictionary.

    Returns:
        True if notification should be sent.
    """
    realtime_config = config.get("realtime", {})

    if not realtime_config.get("enabled", False):
        return False

    # Check confidence threshold
    min_confidence = realtime_config.get("min_confidence", 0.7)
    if detection.confidence < min_confidence:
        return False

    # Check whitelist
    whitelist = realtime_config.get("species_whitelist", [])
    if whitelist:
        if (
            detection.common_name not in whitelist
            and detection.scientific_name not in whitelist
        ):
            return False

    # Check blacklist
    blacklist = realtime_config.get("species_blacklist", [])
    if detection.common_name in blacklist or detection.scientific_name in blacklist:
        return False

    # Check cooldown
    cooldown_minutes = realtime_config.get("cooldown_minutes", 5)
    if is_on_cooldown(detection.scientific_name, cooldown_minutes):
        return False

    return True


def handle_detection(detection: Detection, config: dict[str, Any]) -> bool:
    """Handle a new detection and send appropriate notifications.

    Priority order:
    1. Watchlisted + new species -> one watchlist-styled alert with new-species badge
    2. Watchlisted only -> watchlist alert (subject to watchlist cooldown)
    3. New species only -> existing new species alert
    4. Realtime enabled -> existing detection alert

    Args:
        detection: Detection record.
        config: Configuration dictionary.

    Returns:
        True if any notification was sent.
    """
    db_config = config["birdnet"]
    birdnet_base_url = db_config.get("base_url", "http://localhost:8080")

    # Get bird image
    image_url = get_bird_image_url(db_config, detection.scientific_name)

    # Check both conditions upfront
    is_watchlisted = check_watchlist(detection, config)
    is_new, new_reason = check_new_species(detection, config, db_config)

    # Priority 1 & 2: Watchlisted species
    if is_watchlisted:
        watchlist_config = config.get("watchlist", {})
        webhook_url = get_webhook_url(config, watchlist_config.get("webhook_url"))
        cooldown_minutes = watchlist_config.get("cooldown_minutes", 60)
        watchlist_cooldown_key = f"watchlist:{detection.scientific_name}"

        # New species bypasses watchlist cooldown.
        # Note: when a watchlisted species is on cooldown, it also suppresses
        # realtime notifications for that species. This is intentional — the
        # user already received a watchlist alert recently.
        if not is_new and is_on_cooldown(watchlist_cooldown_key, cooldown_minutes):
            logger.debug(
                f"Watchlist species {detection.common_name} on cooldown, skipping"
            )
        else:
            logger.info(
                f"Watchlist species detected: {detection.common_name}"
                + (f" - {new_reason}" if is_new else "")
            )

            if send_watchlist_alert(
                webhook_url,
                detection,
                image_url=image_url,
                birdnet_base_url=birdnet_base_url,
                is_new_species=is_new,
                new_reason=new_reason,
            ):
                set_cooldown(watchlist_cooldown_key)
                # Also set the new-species cooldown so check_new_species
                # won't re-flag this species as "new" on the next detection.
                # After this cooldown expires, subsequent watchlist hits show
                # as watchlist-only (without the new-species badge).
                if is_new:
                    set_cooldown(detection.scientific_name)
                return True
            elif is_new:
                # Watchlist alert failed but this is a new species —
                # fall back to the regular new-species alert path
                logger.warning(
                    "Watchlist alert failed for new species %s, "
                    "falling back to new-species alert",
                    detection.common_name,
                )
                new_species_config = config.get("new_species", {})
                fallback_url = get_webhook_url(
                    config, new_species_config.get("webhook_url")
                )
                if send_new_species_alert(
                    fallback_url, detection, new_reason, image_url, birdnet_base_url
                ):
                    set_cooldown(detection.scientific_name)
                    return True

    # Priority 3: New species (not watchlisted)
    elif is_new:
        new_species_config = config.get("new_species", {})
        webhook_url = get_webhook_url(config, new_species_config.get("webhook_url"))

        logger.info(f"New species detected: {detection.common_name} - {new_reason}")

        if send_new_species_alert(
            webhook_url, detection, new_reason, image_url, birdnet_base_url
        ):
            set_cooldown(detection.scientific_name)
            return True

    # Priority 4: Realtime notification
    elif should_notify_realtime(detection, config):
        webhook_url = get_webhook_url(config)

        logger.info(f"Detection alert: {detection.common_name}")

        if send_detection_alert(webhook_url, detection, image_url, birdnet_base_url):
            set_cooldown(detection.scientific_name)
            return True

    return False


def handle_detection_by_id(detection_id: int, config: dict[str, Any]) -> bool:
    """Handle a detection by ID.

    Args:
        detection_id: Detection ID from database.
        config: Configuration dictionary.

    Returns:
        True if notification was sent.
    """
    db_config = config["birdnet"]
    detection = get_detection_by_id(db_config, detection_id)

    if detection is None:
        logger.error(f"Detection not found: {detection_id}")
        return False

    return handle_detection(detection, config)


def handle_latest_detection(config: dict[str, Any]) -> bool:
    """Handle the most recent detection.

    Args:
        config: Configuration dictionary.

    Returns:
        True if notification was sent.
    """
    db_config = config["birdnet"]
    detection = get_latest_detection(db_config)

    if detection is None:
        logger.warning("No detections found in database")
        return False

    return handle_detection(detection, config)
