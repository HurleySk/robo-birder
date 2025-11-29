"""Summary report generator for Robo-Birder."""

import logging
from typing import Any

from .config import get_webhook_url
from .database import (
    get_daily_breakdown,
    get_hourly_breakdown,
    get_summary_for_period,
)
from .discord import send_summary

logger = logging.getLogger(__name__)


def generate_and_send_summary(
    summary_config: dict[str, Any], config: dict[str, Any]
) -> bool:
    """Generate and send a summary report.

    Args:
        summary_config: Configuration for this specific summary.
        config: Full configuration dictionary.

    Returns:
        True if summary was sent successfully.
    """
    summary_name = summary_config.get("name", "Summary")
    lookback_minutes = summary_config.get("lookback_minutes", 1440)
    top_n = summary_config.get("include_top_species", 10)
    include_hourly = summary_config.get("include_hourly_breakdown", False)
    include_daily = summary_config.get("include_daily_breakdown", False)

    db_config = config["birdnet"]

    logger.info(f"Generating {summary_name} summary (lookback: {lookback_minutes} min)")

    # Get summary data
    total_detections, species_summaries = get_summary_for_period(
        db_config, lookback_minutes
    )

    # Get breakdowns if requested
    hourly_breakdown = None
    daily_breakdown = None

    if include_hourly:
        hourly_breakdown = get_hourly_breakdown(db_config, lookback_minutes)

    if include_daily:
        daily_breakdown = get_daily_breakdown(db_config, lookback_minutes)

    # Get webhook URL (allow per-summary override)
    webhook_url = get_webhook_url(config, summary_config.get("webhook_url"))

    # Send summary
    success = send_summary(
        webhook_url=webhook_url,
        summary_name=summary_name,
        total_detections=total_detections,
        species_summaries=species_summaries,
        top_n=top_n,
        hourly_breakdown=hourly_breakdown,
        daily_breakdown=daily_breakdown,
        lookback_minutes=lookback_minutes,
    )

    if success:
        logger.info(
            f"Summary '{summary_name}' sent: {total_detections} detections, "
            f"{len(species_summaries)} species"
        )
    else:
        logger.error(f"Failed to send summary '{summary_name}'")

    return success


def run_all_enabled_summaries(config: dict[str, Any]) -> dict[str, bool]:
    """Run all enabled summaries.

    Args:
        config: Full configuration dictionary.

    Returns:
        Dictionary mapping summary name to success status.
    """
    results = {}
    summaries = config.get("summaries", [])

    for summary_config in summaries:
        if summary_config.get("enabled", False):
            name = summary_config.get("name", "unnamed")
            results[name] = generate_and_send_summary(summary_config, config)

    return results


def run_summary_by_name(name: str, config: dict[str, Any]) -> bool:
    """Run a specific summary by name.

    Args:
        name: Summary name.
        config: Full configuration dictionary.

    Returns:
        True if summary was sent successfully.

    Raises:
        ValueError: If summary name not found.
    """
    summaries = config.get("summaries", [])

    for summary_config in summaries:
        if summary_config.get("name") == name:
            return generate_and_send_summary(summary_config, config)

    raise ValueError(f"Summary not found: {name}")
