"""Database queries for BirdNet Go SQLite database."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Generator


@dataclass
class Detection:
    """Represents a bird detection record."""

    id: int
    date: str
    time: str
    begin_time: datetime
    scientific_name: str
    common_name: str
    confidence: float
    clip_name: str | None = None
    species_code: str | None = None


@dataclass
class SpeciesSummary:
    """Summary statistics for a species."""

    scientific_name: str
    common_name: str
    count: int
    avg_confidence: float
    max_confidence: float
    image_url: str | None = None


@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection as a context manager.

    Args:
        db_path: Path to SQLite database.

    Yields:
        Database connection.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_detection_by_id(db_path: str, detection_id: int) -> Detection | None:
    """Get a detection record by ID.

    Args:
        db_path: Path to SQLite database.
        detection_id: Detection ID.

    Returns:
        Detection object or None if not found.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, date, time, begin_time, scientific_name, common_name,
                   confidence, clip_name, species_code
            FROM notes
            WHERE id = ?
            """,
            (detection_id,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return Detection(
            id=row["id"],
            date=row["date"],
            time=row["time"],
            begin_time=_parse_datetime(row["begin_time"]),
            scientific_name=row["scientific_name"],
            common_name=row["common_name"],
            confidence=row["confidence"],
            clip_name=row["clip_name"],
            species_code=row["species_code"],
        )


def get_latest_detection(db_path: str) -> Detection | None:
    """Get the most recent detection.

    Args:
        db_path: Path to SQLite database.

    Returns:
        Detection object or None if no detections.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, date, time, begin_time, scientific_name, common_name,
                   confidence, clip_name, species_code
            FROM notes
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return Detection(
            id=row["id"],
            date=row["date"],
            time=row["time"],
            begin_time=_parse_datetime(row["begin_time"]),
            scientific_name=row["scientific_name"],
            common_name=row["common_name"],
            confidence=row["confidence"],
            clip_name=row["clip_name"],
            species_code=row["species_code"],
        )


def get_bird_image_url(db_path: str, scientific_name: str) -> str | None:
    """Get cached bird image URL from image_caches table.

    Args:
        db_path: Path to SQLite database.
        scientific_name: Scientific name of the species.

    Returns:
        Image URL or None if not cached.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT url
            FROM image_caches
            WHERE scientific_name = ?
            ORDER BY cached_at DESC
            LIMIT 1
            """,
            (scientific_name,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return row["url"]


def species_exists_in_db(db_path: str, scientific_name: str) -> bool:
    """Check if a species has ever been detected.

    Args:
        db_path: Path to SQLite database.
        scientific_name: Scientific name to check.

    Returns:
        True if species exists in database.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM notes
            WHERE scientific_name = ?
            LIMIT 1
            """,
            (scientific_name,),
        )
        return cursor.fetchone() is not None


def species_seen_this_year(db_path: str, scientific_name: str) -> bool:
    """Check if a species has been seen this calendar year.

    Args:
        db_path: Path to SQLite database.
        scientific_name: Scientific name to check.

    Returns:
        True if species was seen this year.
    """
    year_start = datetime(datetime.now().year, 1, 1).isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM notes
            WHERE scientific_name = ?
            AND begin_time >= ?
            LIMIT 1
            """,
            (scientific_name, year_start),
        )
        return cursor.fetchone() is not None


def species_seen_since(db_path: str, scientific_name: str, since: datetime) -> bool:
    """Check if a species has been seen since a given date.

    Args:
        db_path: Path to SQLite database.
        scientific_name: Scientific name to check.
        since: Datetime to check from.

    Returns:
        True if species was seen since the given date.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM notes
            WHERE scientific_name = ?
            AND begin_time >= ?
            LIMIT 1
            """,
            (scientific_name, since.isoformat()),
        )
        return cursor.fetchone() is not None


def get_detections_since(
    db_path: str, since: datetime, until: datetime | None = None
) -> list[Detection]:
    """Get all detections within a time range.

    Args:
        db_path: Path to SQLite database.
        since: Start datetime.
        until: End datetime (defaults to now).

    Returns:
        List of Detection objects.
    """
    if until is None:
        until = datetime.now()

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, date, time, begin_time, scientific_name, common_name,
                   confidence, clip_name, species_code
            FROM notes
            WHERE begin_time >= ? AND begin_time < ?
            ORDER BY begin_time
            """,
            (since.isoformat(), until.isoformat()),
        )

        detections = []
        for row in cursor.fetchall():
            detections.append(
                Detection(
                    id=row["id"],
                    date=row["date"],
                    time=row["time"],
                    begin_time=_parse_datetime(row["begin_time"]),
                    scientific_name=row["scientific_name"],
                    common_name=row["common_name"],
                    confidence=row["confidence"],
                    clip_name=row["clip_name"],
                    species_code=row["species_code"],
                )
            )

        return detections


def get_summary_for_period(
    db_path: str, lookback_minutes: int
) -> tuple[int, list[SpeciesSummary]]:
    """Get detection summary for a time period.

    Args:
        db_path: Path to SQLite database.
        lookback_minutes: Number of minutes to look back.

    Returns:
        Tuple of (total_detections, list of SpeciesSummary).
    """
    since = datetime.now() - timedelta(minutes=lookback_minutes)

    with get_connection(db_path) as conn:
        # Get total count
        cursor = conn.execute(
            """
            SELECT COUNT(*) as total
            FROM notes
            WHERE begin_time >= ?
            """,
            (since.isoformat(),),
        )
        total = cursor.fetchone()["total"]

        # Get per-species summary
        cursor = conn.execute(
            """
            SELECT scientific_name, common_name,
                   COUNT(*) as count,
                   AVG(confidence) as avg_confidence,
                   MAX(confidence) as max_confidence
            FROM notes
            WHERE begin_time >= ?
            GROUP BY scientific_name
            ORDER BY count DESC
            """,
            (since.isoformat(),),
        )

        summaries = []
        for row in cursor.fetchall():
            # Get image URL for species
            image_url = get_bird_image_url(db_path, row["scientific_name"])

            summaries.append(
                SpeciesSummary(
                    scientific_name=row["scientific_name"],
                    common_name=row["common_name"],
                    count=row["count"],
                    avg_confidence=row["avg_confidence"],
                    max_confidence=row["max_confidence"],
                    image_url=image_url,
                )
            )

        return total, summaries


def get_hourly_breakdown(
    db_path: str, lookback_minutes: int
) -> dict[int, int]:
    """Get detection counts by hour.

    Args:
        db_path: Path to SQLite database.
        lookback_minutes: Number of minutes to look back.

    Returns:
        Dictionary mapping hour (0-23) to detection count.
    """
    since = datetime.now() - timedelta(minutes=lookback_minutes)

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT CAST(strftime('%H', begin_time) AS INTEGER) as hour,
                   COUNT(*) as count
            FROM notes
            WHERE begin_time >= ?
            GROUP BY hour
            ORDER BY hour
            """,
            (since.isoformat(),),
        )

        return {row["hour"]: row["count"] for row in cursor.fetchall()}


def get_daily_breakdown(
    db_path: str, lookback_minutes: int
) -> dict[str, int]:
    """Get detection counts by date.

    Args:
        db_path: Path to SQLite database.
        lookback_minutes: Number of minutes to look back.

    Returns:
        Dictionary mapping date string to detection count.
    """
    since = datetime.now() - timedelta(minutes=lookback_minutes)

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT date, COUNT(*) as count
            FROM notes
            WHERE begin_time >= ?
            GROUP BY date
            ORDER BY date
            """,
            (since.isoformat(),),
        )

        return {row["date"]: row["count"] for row in cursor.fetchall()}


def get_first_detection_date(db_path: str, scientific_name: str) -> datetime | None:
    """Get the first time a species was detected.

    Args:
        db_path: Path to SQLite database.
        scientific_name: Scientific name of species.

    Returns:
        Datetime of first detection or None.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT begin_time
            FROM notes
            WHERE scientific_name = ?
            ORDER BY begin_time ASC
            LIMIT 1
            """,
            (scientific_name,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return _parse_datetime(row["begin_time"])


def _parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string from BirdNet Go database.

    Handles various formats including timezone offsets.

    Args:
        dt_str: Datetime string from database.

    Returns:
        Parsed datetime object (timezone-naive).
    """
    # BirdNet Go stores datetimes like: 2025-11-29 15:19:54.4447381-05:00
    # We need to handle various formats

    if dt_str is None:
        return datetime.now()

    # Try to parse with fromisoformat (handles most cases)
    try:
        # Remove nanosecond precision if present (Python only handles microseconds)
        if "." in dt_str:
            parts = dt_str.split(".")
            base = parts[0]
            remainder = parts[1]

            # Find where timezone starts (+ or -)
            tz_start = -1
            for i, c in enumerate(remainder):
                if c in "+-":
                    tz_start = i
                    break

            if tz_start > 0:
                # Truncate to 6 decimal places
                frac = remainder[:tz_start][:6]
                tz = remainder[tz_start:]
                dt_str = f"{base}.{frac}{tz}"
            elif tz_start == -1:
                # No timezone
                frac = remainder[:6]
                dt_str = f"{base}.{frac}"

        dt = datetime.fromisoformat(dt_str)
        # Convert to naive datetime (remove timezone)
        return dt.replace(tzinfo=None)
    except ValueError:
        pass

    # Fallback: try basic format
    try:
        return datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.now()
