"""Worker-local SQLite journal for resilient orchestration.

When the primary PostgreSQL database is unreachable (e.g., the control
plane VM is down during parent hypervisor patching), the orchestrator
buffers status updates here.  Once the DB comes back online, the
journal is replayed and flushed.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SyncSession
from app.models.job import Job

logger = logging.getLogger(__name__)

JOURNAL_DIR = os.environ.get("JOURNAL_DIR", "/tmp/updatr-journal")
JOURNAL_PATH = os.path.join(JOURNAL_DIR, "orchestration_journal.db")


def _ensure_journal_db() -> sqlite3.Connection:
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    conn = sqlite3.connect(JOURNAL_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            wave_index INTEGER,
            status TEXT NOT NULL,
            payload TEXT,
            created_at TEXT NOT NULL,
            replayed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def buffer_update(job_id: str, wave_index: int | None, status: str, payload: dict | None = None):
    """Write a status update to the local SQLite journal."""
    try:
        conn = _ensure_journal_db()
        conn.execute(
            "INSERT INTO journal_entries (job_id, wave_index, status, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, wave_index, status, json.dumps(payload) if payload else None, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()
        logger.info("journal: buffered update job=%s wave=%s status=%s", job_id, wave_index, status)
    except Exception:
        logger.exception("journal: failed to buffer update")


def replay_journal():
    """Replay un-replayed journal entries to the primary database."""
    try:
        conn = _ensure_journal_db()
        rows = conn.execute(
            "SELECT id, job_id, wave_index, status, payload, created_at FROM journal_entries WHERE replayed = 0 ORDER BY id"
        ).fetchall()

        if not rows:
            return 0

        replayed = 0
        with SyncSession() as db:
            for row_id, job_id, wave_index, status, payload_str, created_at in rows:
                try:
                    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
                    if job:
                        job.status = status
                        if wave_index is not None:
                            job.current_wave = wave_index
                        if status == "completed":
                            job.completed_at = datetime.fromisoformat(created_at)
                        if status == "failed":
                            job.completed_at = datetime.fromisoformat(created_at)
                        db.commit()

                    conn.execute("UPDATE journal_entries SET replayed = 1 WHERE id = ?", (row_id,))
                    conn.commit()
                    replayed += 1
                except Exception:
                    logger.exception("journal: failed to replay entry %d", row_id)
                    break

        conn.close()
        logger.info("journal: replayed %d/%d entries", replayed, len(rows))
        return replayed

    except Exception:
        logger.exception("journal: replay failed")
        return 0


def try_update_db(job_id: str, wave_index: int | None, status: str, payload: dict | None = None) -> bool:
    """Attempt to write to primary DB; fall back to journal on failure."""
    try:
        with SyncSession() as db:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
            if job:
                job.status = status
                if wave_index is not None:
                    job.current_wave = wave_index
                if status == "running" and not job.started_at:
                    job.started_at = datetime.now(timezone.utc)
                if status in ("completed", "failed"):
                    job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return True
    except Exception:
        logger.warning("journal: primary DB write failed for job=%s, buffering", job_id)
        buffer_update(job_id, wave_index, status, payload)
        return False


def wait_for_db_recovery(max_wait: int = 600, initial_interval: int = 5) -> bool:
    """Poll the primary DB with exponential backoff until it responds.

    Returns True if the DB is reachable, False if max_wait is exceeded.
    """
    interval = initial_interval
    elapsed = 0

    while elapsed < max_wait:
        try:
            with SyncSession() as db:
                db.execute(select(Job).limit(1))
            logger.info("journal: primary DB is back online after %ds", elapsed)
            replay_journal()
            return True
        except Exception:
            logger.info("journal: DB still unreachable, retrying in %ds (elapsed: %ds)", interval, elapsed)
            time.sleep(interval)
            elapsed += interval
            interval = min(interval * 2, 60)

    logger.error("journal: DB did not recover within %ds", max_wait)
    return False
