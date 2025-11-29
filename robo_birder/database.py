"""Database queries for BirdNet Go with SQLite and MySQL support."""

import sqlite3
from abc import ABC, abstractmethod
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


class DatabaseBackend(ABC):
    """Abstract database backend interface."""

    @abstractmethod
    def execute(self, query: str, params: tuple | None = None) -> Any:
        """Execute a query and return a cursor-like object."""
        pass

    @abstractmethod
    def fetchone(self, cursor: Any) -> dict | None:
        """Fetch one row as a dictionary."""
        pass

    @abstractmethod
    def fetchall(self, cursor: Any) -> list[dict]:
        """Fetch all rows as dictionaries."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the connection."""
        pass

    @property
    @abstractmethod
    def placeholder(self) -> str:
        """Return the parameter placeholder (? for SQLite, %s for MySQL)."""
        pass

    @abstractmethod
    def hour_extract(self, column: str) -> str:
        """Return SQL for extracting hour from a datetime column."""
        pass

    @abstractmethod
    def date_extract(self, column: str) -> str:
        """Return SQL for extracting date from a datetime column."""
        pass


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend."""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, query: str, params: tuple | None = None) -> Any:
        if params:
            return self.conn.execute(query, params)
        return self.conn.execute(query)

    def fetchone(self, cursor: Any) -> dict | None:
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self, cursor: Any) -> list[dict]:
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()

    @property
    def placeholder(self) -> str:
        return "?"

    def hour_extract(self, column: str) -> str:
        return f"CAST(strftime('%H', {column}) AS INTEGER)"

    def date_extract(self, column: str) -> str:
        return f"strftime('%Y-%m-%d', {column})"


class MySQLBackend(DatabaseBackend):
    """MySQL database backend."""

    def __init__(self, config: dict[str, Any]):
        import pymysql
        import pymysql.cursors

        self.conn = pymysql.connect(
            host=config.get("host", "localhost"),
            port=config.get("port", 3306),
            database=config.get("database", "birdnet"),
            user=config.get("username", "birdnet"),
            password=config.get("password", ""),
            cursorclass=pymysql.cursors.DictCursor,
        )

    def execute(self, query: str, params: tuple | None = None) -> Any:
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def fetchone(self, cursor: Any) -> dict | None:
        return cursor.fetchone()

    def fetchall(self, cursor: Any) -> list[dict]:
        return cursor.fetchall()

    def close(self) -> None:
        self.conn.close()

    @property
    def placeholder(self) -> str:
        return "%s"

    def hour_extract(self, column: str) -> str:
        return f"HOUR({column})"

    def date_extract(self, column: str) -> str:
        return f"DATE({column})"


@contextmanager
def get_backend(db_config: dict[str, Any]) -> Generator[DatabaseBackend, None, None]:
    """Get a database backend as a context manager.

    Args:
        db_config: Database configuration dict (the 'birdnet' section from config).

    Yields:
        Database backend.
    """
    db_type = db_config.get("db_type", "sqlite")

    if db_type == "mysql":
        mysql_config = db_config.get("mysql", {})
        backend = MySQLBackend(mysql_config)
    else:
        db_path = db_config.get("db_path", "/root/birdnet-go-app/data/birdnet.db")
        backend = SQLiteBackend(db_path)

    try:
        yield backend
    finally:
        backend.close()


# Legacy function for backward compatibility
@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Get a SQLite database connection as a context manager.

    DEPRECATED: Use get_backend() with db_config instead.

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


def get_detection_by_id(db_config: dict[str, Any], detection_id: int) -> Detection | None:
    """Get a detection record by ID.

    Args:
        db_config: Database configuration dict.
        detection_id: Detection ID.

    Returns:
        Detection object or None if not found.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT id, date, time, begin_time, scientific_name, common_name,
                   confidence, clip_name, species_code
            FROM notes
            WHERE id = {p}
            """,
            (detection_id,),
        )
        row = db.fetchone(cursor)

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
            species_code=row.get("species_code"),
        )


def get_latest_detection(db_config: dict[str, Any]) -> Detection | None:
    """Get the most recent detection.

    Args:
        db_config: Database configuration dict.

    Returns:
        Detection object or None if no detections.
    """
    with get_backend(db_config) as db:
        cursor = db.execute(
            """
            SELECT id, date, time, begin_time, scientific_name, common_name,
                   confidence, clip_name, species_code
            FROM notes
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = db.fetchone(cursor)

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
            species_code=row.get("species_code"),
        )


def get_bird_image_url(db_config: dict[str, Any], scientific_name: str) -> str | None:
    """Get cached bird image URL from image_caches table.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name of the species.

    Returns:
        Image URL or None if not cached.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT url
            FROM image_caches
            WHERE scientific_name = {p}
            ORDER BY cached_at DESC
            LIMIT 1
            """,
            (scientific_name,),
        )
        row = db.fetchone(cursor)

        if row is None:
            return None

        return row["url"]


def species_exists_in_db(db_config: dict[str, Any], scientific_name: str) -> bool:
    """Check if a species has ever been detected.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name to check.

    Returns:
        True if species exists in database.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT 1 FROM notes
            WHERE scientific_name = {p}
            LIMIT 1
            """,
            (scientific_name,),
        )
        return db.fetchone(cursor) is not None


def species_seen_this_year(db_config: dict[str, Any], scientific_name: str) -> bool:
    """Check if a species has been seen this calendar year.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name to check.

    Returns:
        True if species was seen this year.
    """
    year_start = datetime(datetime.now().year, 1, 1).isoformat()

    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT 1 FROM notes
            WHERE scientific_name = {p}
            AND begin_time >= {p}
            LIMIT 1
            """,
            (scientific_name, year_start),
        )
        return db.fetchone(cursor) is not None


def species_seen_since(db_config: dict[str, Any], scientific_name: str, since: datetime) -> bool:
    """Check if a species has been seen since a given date.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name to check.
        since: Datetime to check from.

    Returns:
        True if species was seen since the given date.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT 1 FROM notes
            WHERE scientific_name = {p}
            AND begin_time >= {p}
            LIMIT 1
            """,
            (scientific_name, since.isoformat()),
        )
        return db.fetchone(cursor) is not None


def get_detections_since(
    db_config: dict[str, Any], since: datetime, until: datetime | None = None
) -> list[Detection]:
    """Get all detections within a time range.

    Args:
        db_config: Database configuration dict.
        since: Start datetime.
        until: End datetime (defaults to now).

    Returns:
        List of Detection objects.
    """
    if until is None:
        until = datetime.now()

    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT id, date, time, begin_time, scientific_name, common_name,
                   confidence, clip_name, species_code
            FROM notes
            WHERE begin_time >= {p} AND begin_time < {p}
            ORDER BY begin_time
            """,
            (since.isoformat(), until.isoformat()),
        )

        detections = []
        for row in db.fetchall(cursor):
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
                    species_code=row.get("species_code"),
                )
            )

        return detections


def get_summary_for_period(
    db_config: dict[str, Any], lookback_minutes: int
) -> tuple[int, list[SpeciesSummary]]:
    """Get detection summary for a time period.

    Args:
        db_config: Database configuration dict.
        lookback_minutes: Number of minutes to look back.

    Returns:
        Tuple of (total_detections, list of SpeciesSummary).
    """
    since = datetime.now() - timedelta(minutes=lookback_minutes)

    with get_backend(db_config) as db:
        p = db.placeholder

        # Get total count
        cursor = db.execute(
            f"""
            SELECT COUNT(*) as total
            FROM notes
            WHERE begin_time >= {p}
            """,
            (since.isoformat(),),
        )
        row = db.fetchone(cursor)
        total = row["total"] if row else 0

        # Get per-species summary
        cursor = db.execute(
            f"""
            SELECT scientific_name, common_name,
                   COUNT(*) as count,
                   AVG(confidence) as avg_confidence,
                   MAX(confidence) as max_confidence
            FROM notes
            WHERE begin_time >= {p}
            GROUP BY scientific_name
            ORDER BY count DESC
            """,
            (since.isoformat(),),
        )

        summaries = []
        for row in db.fetchall(cursor):
            # Get image URL for species
            image_url = get_bird_image_url(db_config, row["scientific_name"])

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
    db_config: dict[str, Any], lookback_minutes: int
) -> dict[int, int]:
    """Get detection counts by hour.

    Args:
        db_config: Database configuration dict.
        lookback_minutes: Number of minutes to look back.

    Returns:
        Dictionary mapping hour (0-23) to detection count.
    """
    since = datetime.now() - timedelta(minutes=lookback_minutes)

    with get_backend(db_config) as db:
        p = db.placeholder
        hour_expr = db.hour_extract("begin_time")
        cursor = db.execute(
            f"""
            SELECT {hour_expr} as hour,
                   COUNT(*) as count
            FROM notes
            WHERE begin_time >= {p}
            GROUP BY hour
            ORDER BY hour
            """,
            (since.isoformat(),),
        )

        return {row["hour"]: row["count"] for row in db.fetchall(cursor)}


def get_daily_breakdown(
    db_config: dict[str, Any], lookback_minutes: int
) -> dict[str, int]:
    """Get detection counts by date.

    Args:
        db_config: Database configuration dict.
        lookback_minutes: Number of minutes to look back.

    Returns:
        Dictionary mapping date string to detection count.
    """
    since = datetime.now() - timedelta(minutes=lookback_minutes)

    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT date, COUNT(*) as count
            FROM notes
            WHERE begin_time >= {p}
            GROUP BY date
            ORDER BY date
            """,
            (since.isoformat(),),
        )

        return {row["date"]: row["count"] for row in db.fetchall(cursor)}


def get_first_detection_date(db_config: dict[str, Any], scientific_name: str) -> datetime | None:
    """Get the first time a species was detected.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name of species.

    Returns:
        Datetime of first detection or None.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"""
            SELECT begin_time
            FROM notes
            WHERE scientific_name = {p}
            ORDER BY begin_time ASC
            LIMIT 1
            """,
            (scientific_name,),
        )
        row = db.fetchone(cursor)

        if row is None:
            return None

        return _parse_datetime(row["begin_time"])


def get_species_count(db_config: dict[str, Any], scientific_name: str) -> int:
    """Get count of detections for a species.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name of species.

    Returns:
        Number of detections.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"SELECT COUNT(*) as count FROM notes WHERE scientific_name = {p}",
            (scientific_name,),
        )
        row = db.fetchone(cursor)
        return row["count"] if row else 0


def get_species_count_since(
    db_config: dict[str, Any], scientific_name: str, since: datetime, before_id: int | None = None
) -> int:
    """Get count of detections for a species since a datetime.

    Args:
        db_config: Database configuration dict.
        scientific_name: Scientific name of species.
        since: Start datetime.
        before_id: Only count detections with ID less than this (for checking new species).

    Returns:
        Number of detections.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        if before_id is not None:
            cursor = db.execute(
                f"""
                SELECT COUNT(*) as count FROM notes
                WHERE scientific_name = {p}
                AND begin_time >= {p}
                AND id < {p}
                """,
                (scientific_name, since.isoformat(), before_id),
            )
        else:
            cursor = db.execute(
                f"""
                SELECT COUNT(*) as count FROM notes
                WHERE scientific_name = {p}
                AND begin_time >= {p}
                """,
                (scientific_name, since.isoformat()),
            )
        row = db.fetchone(cursor)
        return row["count"] if row else 0


def get_max_detection_id(db_config: dict[str, Any]) -> int:
    """Get the maximum detection ID from database.

    Args:
        db_config: Database configuration dict.

    Returns:
        Maximum ID or 0 if no detections.
    """
    with get_backend(db_config) as db:
        cursor = db.execute("SELECT MAX(id) as max_id FROM notes")
        row = db.fetchone(cursor)
        return row["max_id"] if row and row["max_id"] is not None else 0


def get_new_detection_ids(db_config: dict[str, Any], after_id: int) -> list[int]:
    """Get IDs of detections after a given ID.

    Args:
        db_config: Database configuration dict.
        after_id: Return detections with ID greater than this.

    Returns:
        List of detection IDs.
    """
    with get_backend(db_config) as db:
        p = db.placeholder
        cursor = db.execute(
            f"SELECT id FROM notes WHERE id > {p} ORDER BY id",
            (after_id,),
        )
        return [row["id"] for row in db.fetchall(cursor)]


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

    # Handle datetime objects (from MySQL)
    if isinstance(dt_str, datetime):
        return dt_str.replace(tzinfo=None) if dt_str.tzinfo else dt_str

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
