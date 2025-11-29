#!/usr/bin/env python3
"""
Notification handler entry point for BirdNet Go script provider.

This script is called by BirdNet Go when a detection occurs.
It receives detection data via stdin (JSON format) or as the latest detection.

Usage:
    notify_handler.py                    # Process latest detection
    notify_handler.py --id <detection_id>  # Process specific detection
    notify_handler.py --test             # Send test notification
    echo '{"id": 123}' | notify_handler.py  # Receive via stdin
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add the project directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from robo_birder.config import load_config
from robo_birder.notify import handle_detection_by_id, handle_latest_detection
from robo_birder.discord import send_webhook

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("notify_handler")


def send_test_notification(config: dict) -> bool:
    """Send a test notification to verify webhook setup.

    Args:
        config: Configuration dictionary.

    Returns:
        True if successful.
    """
    webhook_url = config["discord"]["webhook_url"]

    payload = {
        "embeds": [
            {
                "title": "Robo-Birder Test",
                "description": "If you see this message, your Discord webhook is configured correctly!",
                "color": 0x2ECC71,  # Green
                "footer": {"text": "Robo-Birder"},
            }
        ]
    }

    return send_webhook(webhook_url, payload)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(description="Robo-Birder notification handler")
    parser.add_argument(
        "--id",
        type=int,
        help="Detection ID to process",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test notification",
    )
    parser.add_argument(
        "--summary",
        type=str,
        help="Run a specific summary by name",
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Handle test mode
    if args.test:
        logger.info("Sending test notification...")
        if send_test_notification(config):
            logger.info("Test notification sent successfully!")
            return 0
        else:
            logger.error("Failed to send test notification")
            return 1

    # Handle summary mode
    if args.summary:
        from robo_birder.summary import run_summary_by_name

        logger.info(f"Running summary: {args.summary}")
        try:
            if run_summary_by_name(args.summary, config):
                return 0
            else:
                return 1
        except ValueError as e:
            logger.error(str(e))
            return 1

    # Check for detection ID from stdin (JSON format)
    detection_id = args.id

    if detection_id is None and not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                data = json.loads(stdin_data)
                detection_id = data.get("id") or data.get("detection_id")
        except json.JSONDecodeError:
            logger.warning("Failed to parse stdin as JSON, trying latest detection")
        except Exception as e:
            logger.warning(f"Error reading stdin: {e}")

    # Process detection
    if detection_id is not None:
        logger.info(f"Processing detection ID: {detection_id}")
        success = handle_detection_by_id(detection_id, config)
    else:
        logger.info("Processing latest detection")
        success = handle_latest_detection(config)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
