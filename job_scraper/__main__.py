"""Entry point: scrape Cisco + IBM, dedup against seen-store, email digest."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import load
from .emailer import send_job_digest
from .scrapers.apple import AppleScraper
from .scrapers.base import Job
from .scrapers.google import GoogleScraper
from .seen_store import SeenStore

log = logging.getLogger("job_scraper")

SCRAPERS = [AppleScraper(), GoogleScraper()]


async def _scrape_one(scraper) -> list[Job]:
    try:
        return await scraper.fetch()
    except Exception as exc:  # noqa: BLE001
        log.exception("%s scraper raised an unexpected error: %s", scraper.company, exc)
        return []


async def run(*, dry_run: bool = False, reset_store: bool = False) -> int:
    results = await asyncio.gather(*(_scrape_one(s) for s in SCRAPERS))
    all_jobs: list[Job] = [j for sub in results for j in sub]
    log.info("Scraped %d total job postings across all companies", len(all_jobs))

    store = SeenStore()
    if reset_store:
        store.reset()

    new_jobs = store.filter_new(all_jobs)
    log.info("New (unseen) jobs this run: %d", len(new_jobs))
    for job in new_jobs:
        log.info("  [%s] %s — %s", job.company, job.title, job.location or "location unknown")

    if dry_run:
        log.info("Dry-run mode: skipping email send and not persisting seen-store.")
        return len(new_jobs)

    cfg = load()
    send_job_digest(new_jobs, cfg)
    store.save()
    return len(new_jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Job scraper — Cisco + IBM (Data Scientist & AI Engineer)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scrape and log results without sending email or saving state.",
    )
    parser.add_argument(
        "--reset-store", action="store_true",
        help="Treat every found job as new (forces email; use for first real run or testing).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug-level logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    count = asyncio.run(run(dry_run=args.dry_run, reset_store=args.reset_store))
    sys.exit(0 if count >= 0 else 1)


if __name__ == "__main__":
    main()
