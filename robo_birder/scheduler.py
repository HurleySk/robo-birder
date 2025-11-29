"""Cron-based scheduler for summary reports and detection watcher."""

import logging
import signal
import time
from datetime import datetime
from typing import Any

from croniter import croniter

from .config import load_config
from .database import get_detection_by_id, get_max_detection_id, get_new_detection_ids
from .notify import handle_detection
from .summary import generate_and_send_summary

logger = logging.getLogger(__name__)


class DetectionWatcher:
    """Watches database for new detections and triggers notifications."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the watcher.

        Args:
            config: Configuration dictionary.
        """
        self.config = config
        self.db_config = config["birdnet"]
        self.last_id = self._get_max_id()
        logger.info(f"DetectionWatcher initialized, starting from ID {self.last_id}")

    def _get_max_id(self) -> int:
        """Get the current maximum detection ID from database."""
        try:
            return get_max_detection_id(self.db_config)
        except Exception as e:
            logger.error(f"Failed to get max ID: {e}")
            return 0

    def check_new_detections(self) -> int:
        """Check for new detections and process them.

        Returns:
            Number of new detections processed.
        """
        try:
            new_ids = get_new_detection_ids(self.db_config, self.last_id)
        except Exception as e:
            logger.error(f"Failed to check for new detections: {e}")
            return 0

        processed = 0
        for detection_id in new_ids:
            detection = get_detection_by_id(self.db_config, detection_id)
            if detection:
                logger.info(f"New detection: {detection.common_name} (ID {detection_id})")
                try:
                    handle_detection(detection, self.config)
                    processed += 1
                except Exception as e:
                    logger.exception(f"Error handling detection {detection_id}: {e}")
            self.last_id = detection_id

        return processed


class SummaryScheduler:
    """Scheduler that runs summary reports based on cron expressions."""

    def __init__(self, config_path: str | None = None):
        """Initialize the scheduler.

        Args:
            config_path: Path to configuration file.
        """
        self.config_path = config_path
        self.config = load_config(config_path)
        self.running = False
        self._reload_requested = False

        # Track next run times for each summary
        self.next_runs: dict[str, datetime] = {}
        self._initialize_schedules()

        # Detection watcher for real-time notifications
        self.watcher = DetectionWatcher(self.config)

    def _initialize_schedules(self) -> None:
        """Initialize next run times for all enabled summaries."""
        self.next_runs = {}
        summaries = self.config.get("summaries", [])
        now = datetime.now()

        for summary in summaries:
            if not summary.get("enabled", False):
                continue

            name = summary.get("name", "unnamed")
            cron_expr = summary.get("cron", "0 8 * * *")

            try:
                cron = croniter(cron_expr, now)
                next_run = cron.get_next(datetime)
                self.next_runs[name] = next_run
                logger.info(
                    f"Scheduled '{name}' (cron: {cron_expr}) - next run: {next_run}"
                )
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid cron expression for '{name}': {cron_expr} - {e}")

    def reload_config(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading configuration...")
        try:
            self.config = load_config(self.config_path)
            self._initialize_schedules()
            self.watcher.config = self.config
            self.watcher.db_config = self.config["birdnet"]
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")

    def _handle_sighup(self, signum: int, frame: Any) -> None:
        """Handle SIGHUP signal for config reload."""
        self._reload_requested = True

    def _get_summary_config(self, name: str) -> dict[str, Any] | None:
        """Get summary configuration by name.

        Args:
            name: Summary name.

        Returns:
            Summary configuration or None.
        """
        summaries = self.config.get("summaries", [])
        for summary in summaries:
            if summary.get("name") == name:
                return summary
        return None

    def _run_summary(self, name: str) -> None:
        """Run a summary and update its next run time.

        Args:
            name: Summary name.
        """
        summary_config = self._get_summary_config(name)
        if summary_config is None:
            logger.error(f"Summary configuration not found: {name}")
            return

        try:
            generate_and_send_summary(summary_config, self.config)
        except Exception as e:
            logger.exception(f"Error running summary '{name}': {e}")

        # Schedule next run
        cron_expr = summary_config.get("cron", "0 8 * * *")
        try:
            cron = croniter(cron_expr, datetime.now())
            self.next_runs[name] = cron.get_next(datetime)
            logger.debug(f"Next run for '{name}': {self.next_runs[name]}")
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to schedule next run for '{name}': {e}")
            # Remove from schedule if cron is invalid
            del self.next_runs[name]

    def run(self) -> None:
        """Run the scheduler loop."""
        self.running = True

        # Set up signal handler for config reload
        signal.signal(signal.SIGHUP, self._handle_sighup)

        logger.info("Scheduler started")

        while self.running:
            # Check for config reload request
            if self._reload_requested:
                self.reload_config()
                self._reload_requested = False

            now = datetime.now()

            # Check each scheduled summary
            for name, next_run in list(self.next_runs.items()):
                if now >= next_run:
                    logger.info(f"Running scheduled summary: {name}")
                    self._run_summary(name)

            # Check for new detections
            self.watcher.check_new_detections()

            # Sleep for a short interval
            time.sleep(10)

        logger.info("Scheduler stopped")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False


def run_scheduler(config_path: str | None = None) -> None:
    """Run the scheduler daemon.

    Args:
        config_path: Path to configuration file.
    """
    scheduler = SummaryScheduler(config_path)

    # Set up signal handlers
    def handle_sigterm(signum: int, frame: Any) -> None:
        logger.info("Received SIGTERM, shutting down...")
        scheduler.stop()

    def handle_sigint(signum: int, frame: Any) -> None:
        logger.info("Received SIGINT, shutting down...")
        scheduler.stop()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)

    scheduler.run()
