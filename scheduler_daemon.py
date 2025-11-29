#!/usr/bin/env python3
"""
Scheduler daemon entry point for Robo-Birder.

This script runs as a long-lived daemon that executes scheduled summaries
based on cron expressions in the configuration file.

Usage:
    scheduler_daemon.py                     # Run with default config
    scheduler_daemon.py --config /path/to/config.yaml  # Custom config

Signals:
    SIGHUP  - Reload configuration
    SIGTERM - Graceful shutdown
    SIGINT  - Graceful shutdown (Ctrl+C)
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the project directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from robo_birder.scheduler import run_scheduler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduler_daemon")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(description="Robo-Birder scheduler daemon")
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to configuration file",
    )

    args = parser.parse_args()

    logger.info("Starting Robo-Birder scheduler daemon...")
    logger.info(f"Configuration file: {args.config}")

    try:
        run_scheduler(args.config)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Scheduler error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
