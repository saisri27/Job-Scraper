"""Playwright scraper for Apple careers (jobs.apple.com).

Apple job-detail URLs always contain `/details/{numeric-id}/{slug}` so we
anchor on that pattern — far more reliable than CSS class names that change.

Search URL format:
  https://jobs.apple.com/en-us/search?search=<role>&sort=relevance
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from playwright.async_api import async_playwright

from .base import BaseScraper, Job

log = logging.getLogger(__name__)

ROLES = ["Data Scientist", "AI Engineer"]
BASE_URL = "https://jobs.apple.com"
_JOB_URL_RE = re.compile(r"/details/\d+")


class AppleScraper(BaseScraper):
    company = "Apple"

    async def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            for role in ROLES:
                found = await self._fetch_role(page, role)
                log.info("Apple  | %-20s → %d jobs", role, len(found))
                jobs.extend(found)
            await browser.close()
        return jobs

    async def _fetch_role(self, page, role: str) -> list[Job]:
        search_url = f"{BASE_URL}/en-us/search?search={quote_plus(role)}&sort=relevance"
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
            # Apple renders results client-side; wait for at least one job-detail link.
            try:
                await page.wait_for_selector("a[href*='/details/']", timeout=25_000)
            except Exception:  # noqa: BLE001
                log.debug("Apple: no '/details/' links appeared within 25s for '%s'", role)
            await page.wait_for_timeout(1_500)
        except Exception as exc:  # noqa: BLE001
            log.warning("Apple: page load failed for '%s': %s", role, exc)
            return []

        jobs: list[Job] = []
        seen_urls: set[str] = set()
        anchors = await page.query_selector_all("a[href*='/details/']")
        for anchor in anchors:
            href = await anchor.get_attribute("href") or ""
            if not _JOB_URL_RE.search(href):
                continue
            title = (await anchor.inner_text()).strip()
            if not title:
                continue
            full_url = urljoin(BASE_URL, href.split("?")[0])
            if full_url in seen_urls:
                continue

            role_tokens = role.lower().split()
            if not all(t in title.lower() for t in role_tokens):
                continue

            seen_urls.add(full_url)
            # Apple sometimes has the posting location as a sibling element.
            location = ""
            try:
                parent = await anchor.evaluate_handle("el => el.closest('tr, li, article') || el.parentElement")
                loc_el = await parent.as_element().query_selector(".table-col-2, .job-location, [class*='location']") if parent else None
                if loc_el:
                    location = (await loc_el.inner_text()).strip()
            except Exception:  # noqa: BLE001
                pass

            jobs.append(Job(company="Apple", title=title, url=full_url, role=role, location=location))

        if not jobs and os.environ.get("DEBUG_SCREENSHOTS", "").lower() in ("1", "true"):
            out = Path("debug_screenshots")
            out.mkdir(exist_ok=True)
            slug = role.lower().replace(" ", "_")
            await page.screenshot(path=str(out / f"apple_{slug}.png"), full_page=True)
            log.warning("Apple: saved debug screenshot for '%s'", role)

        return jobs
