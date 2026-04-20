"""Persistent 'jobs already seen' store, shared across scrapers.

State is a small JSON file mapping `dedup_key` -> ISO timestamp of first
sighting.  Entries older than `TTL_DAYS` are pruned on each load so the
file never grows unbounded.

In GitHub Actions the state file is restored/saved via `actions/cache`;
locally it lives at `.state/seen_jobs.json` (gitignored) so back-to-back
runs deduplicate correctly too.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .scrapers.base import Job

log = logging.getLogger(__name__)

TTL_DAYS = 30
DEFAULT_PATH = Path(os.environ.get("SEEN_STORE_PATH", ".state/seen_jobs.json"))


class SeenStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_PATH
        self._seen: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.info("SeenStore: no existing state at %s", self.path)
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("SeenStore: failed to read %s (%s); starting fresh", self.path, exc)
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)
        kept = 0
        for key, iso in raw.items():
            try:
                if datetime.fromisoformat(iso) >= cutoff:
                    self._seen[key] = iso
                    kept += 1
            except ValueError:
                continue
        log.info("SeenStore: loaded %d entries (TTL=%dd, pruned %d expired)", kept, TTL_DAYS, len(raw) - kept)

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """Return jobs not yet recorded; newly-seen jobs are stamped and added."""
        now_iso = datetime.now(timezone.utc).isoformat()
        new: list[Job] = []
        for job in jobs:
            if job.dedup_key in self._seen:
                continue
            self._seen[job.dedup_key] = now_iso
            new.append(job)
        return new

    def reset(self) -> None:
        """Clear all seen state (used with --reset-store)."""
        self._seen.clear()
        log.warning("SeenStore: cleared — every scraped job will appear as new")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._seen, indent=2, sort_keys=True), encoding="utf-8"
        )
        log.info("SeenStore: wrote %d entries to %s", len(self._seen), self.path)
