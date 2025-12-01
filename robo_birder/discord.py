"""Discord webhook integration for Robo-Birder."""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .database import Detection, SpeciesSummary

logger = logging.getLogger(__name__)

# Discord embed colors
COLOR_NEW_SPECIES = 0xFFD700  # Gold
COLOR_DETECTION = 0x3498DB  # Blue
COLOR_SUMMARY = 0x2ECC71  # Green
COLOR_ERROR = 0xE74C3C  # Red


def send_webhook(webhook_url: str, payload: dict[str, Any]) -> bool:
    """Send a payload to a Discord webhook.

    Args:
        webhook_url: Discord webhook URL.
        payload: Webhook payload (embeds, content, etc.).

    Returns:
        True if successful, False otherwise.
    """
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Discord webhook: {e}")
        return False


def send_new_species_alert(
    webhook_url: str,
    detection: Detection,
    reason: str,
    image_url: str | None = None,
    birdnet_base_url: str = "http://localhost:8080",
) -> bool:
    """Send a new species alert to Discord.

    Args:
        webhook_url: Discord webhook URL.
        detection: Detection record.
        reason: Why this is a new species (e.g., "First ever sighting!").
        image_url: Optional bird image URL.
        birdnet_base_url: Base URL for BirdNet Go web UI.

    Returns:
        True if successful.
    """
    # Format time nicely
    try:
        time_str = detection.begin_time.strftime("%-I:%M %p")
    except ValueError:
        # Windows doesn't support %-I
        time_str = detection.begin_time.strftime("%I:%M %p").lstrip("0")

    embed = {
        "title": f"NEW SPECIES: {detection.common_name}",
        "color": COLOR_NEW_SPECIES,
        "fields": [
            {
                "name": detection.common_name,
                "value": f"*{detection.scientific_name}*",
                "inline": False,
            },
            {
                "name": "Details",
                "value": f"**{reason}**\nConfidence: {detection.confidence:.0%}\nTime: {time_str}",
                "inline": False,
            },
        ],
        "footer": {"text": "Robo-Birder"},
        "timestamp": detection.begin_time.isoformat(),
    }

    # Add bird image if available
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    # Add link to BirdNet Go (specific detection)
    embed["url"] = f"{birdnet_base_url}/ui/detections/{detection.id}"

    payload = {"embeds": [embed]}

    return send_webhook(webhook_url, payload)


def send_detection_alert(
    webhook_url: str,
    detection: Detection,
    image_url: str | None = None,
    birdnet_base_url: str = "http://localhost:8080",
) -> bool:
    """Send a regular detection alert to Discord.

    Args:
        webhook_url: Discord webhook URL.
        detection: Detection record.
        image_url: Optional bird image URL.
        birdnet_base_url: Base URL for BirdNet Go web UI.

    Returns:
        True if successful.
    """
    try:
        time_str = detection.begin_time.strftime("%-I:%M %p")
    except ValueError:
        time_str = detection.begin_time.strftime("%I:%M %p").lstrip("0")

    embed = {
        "title": detection.common_name,
        "description": f"*{detection.scientific_name}*",
        "color": COLOR_DETECTION,
        "fields": [
            {
                "name": "Confidence",
                "value": f"{detection.confidence:.0%}",
                "inline": True,
            },
            {
                "name": "Time",
                "value": time_str,
                "inline": True,
            },
        ],
        "footer": {"text": "Robo-Birder"},
        "timestamp": detection.begin_time.isoformat(),
        "url": f"{birdnet_base_url}/ui/detections/{detection.id}",
    }

    if image_url:
        embed["thumbnail"] = {"url": image_url}

    payload = {"embeds": [embed]}

    return send_webhook(webhook_url, payload)


def send_summary(
    webhook_url: str,
    summary_name: str,
    total_detections: int,
    species_summaries: list[SpeciesSummary],
    top_n: int = 10,
    hourly_breakdown: dict[int, int] | None = None,
    daily_breakdown: dict[str, int] | None = None,
    lookback_minutes: int = 1440,
    tz: ZoneInfo | None = None,
) -> bool:
    """Send a summary report to Discord.

    Args:
        webhook_url: Discord webhook URL.
        summary_name: Name of the summary (e.g., "Daily", "Hourly").
        total_detections: Total number of detections.
        species_summaries: List of species summaries.
        top_n: Number of top species to show.
        hourly_breakdown: Optional hourly detection counts.
        daily_breakdown: Optional daily detection counts.
        lookback_minutes: Lookback period in minutes.
        tz: Optional timezone for display formatting.

    Returns:
        True if successful.
    """
    unique_species = len(species_summaries)
    now = datetime.now(tz) if tz else datetime.now()

    # Format title based on lookback period
    if lookback_minutes <= 60:
        title = f"Hourly Bird Report"
        time_desc = now.strftime("%-I:00 %p")
    elif lookback_minutes <= 1440:
        title = f"Daily Bird Report"
        time_desc = now.strftime("%b %d, %Y")
    else:
        days = lookback_minutes // 1440
        title = f"{days}-Day Bird Report"
        time_desc = now.strftime("%b %d, %Y")

    # Build species list
    top_species = species_summaries[:top_n]

    if lookback_minutes <= 60 and len(top_species) <= 5:
        # Compact format for hourly
        species_lines = []
        main_species = []
        other_species = []

        for i, s in enumerate(top_species):
            if i < 3:
                main_species.append(f"**{s.common_name}** ({s.count})")
            else:
                other_species.append(f"{s.common_name} ({s.count})")

        species_text = "\n".join(main_species)
        if other_species:
            species_text += "\n" + " | ".join(other_species)
    else:
        # Numbered list for longer summaries
        species_lines = []
        for i, s in enumerate(top_species, 1):
            species_lines.append(f"{i}. **{s.common_name}** ({s.count})")

        species_text = "\n".join(species_lines)

        if len(species_summaries) > top_n:
            remaining = len(species_summaries) - top_n
            species_text += f"\n*...and {remaining} more species*"

    # Build embed
    embed = {
        "title": title,
        "description": f"**{time_desc}**",
        "color": COLOR_SUMMARY,
        "fields": [
            {
                "name": "Summary",
                "value": f"**{total_detections}** detections | **{unique_species}** species",
                "inline": False,
            },
        ],
        "footer": {"text": "Robo-Birder"},
        "timestamp": now.isoformat(),
    }

    if species_text:
        embed["fields"].append(
            {
                "name": "Top Species" if top_n > 5 else "Species",
                "value": species_text,
                "inline": False,
            }
        )

    # Add hourly breakdown if present
    if hourly_breakdown:
        peak_hours = _find_peak_hours(hourly_breakdown)
        if peak_hours:
            embed["fields"].append(
                {
                    "name": "Peak Activity",
                    "value": peak_hours,
                    "inline": False,
                }
            )

    # Add thumbnail from most detected species
    if top_species and top_species[0].image_url:
        embed["thumbnail"] = {"url": top_species[0].image_url}

    # Handle case of no detections
    if total_detections == 0:
        embed["fields"] = [
            {
                "name": "No Detections",
                "value": "No birds were detected during this period.",
                "inline": False,
            }
        ]

    payload = {"embeds": [embed]}

    return send_webhook(webhook_url, payload)


def _find_peak_hours(hourly_breakdown: dict[int, int]) -> str:
    """Find and format peak activity hours.

    Args:
        hourly_breakdown: Dict mapping hour to count.

    Returns:
        Formatted string of peak hours.
    """
    if not hourly_breakdown:
        return ""

    # Find max count
    max_count = max(hourly_breakdown.values())

    # Find all hours with count >= 75% of max
    threshold = max_count * 0.75
    peak_hours = [h for h, c in hourly_breakdown.items() if c >= threshold]

    if not peak_hours:
        return ""

    # Format hours
    def format_hour(h: int) -> str:
        if h == 0:
            return "12 AM"
        elif h < 12:
            return f"{h} AM"
        elif h == 12:
            return "12 PM"
        else:
            return f"{h - 12} PM"

    # Group consecutive hours
    peak_hours.sort()
    ranges = []
    start = peak_hours[0]
    end = start

    for h in peak_hours[1:]:
        if h == end + 1:
            end = h
        else:
            ranges.append((start, end))
            start = h
            end = h
    ranges.append((start, end))

    # Format ranges
    formatted = []
    for start, end in ranges:
        if start == end:
            formatted.append(format_hour(start))
        else:
            formatted.append(f"{format_hour(start)}-{format_hour(end + 1)}")

    return ", ".join(formatted)
