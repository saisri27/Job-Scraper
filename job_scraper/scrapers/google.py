"""Playwright scraper for Google careers (google.com/about/careers).

Google job-detail URLs follow the pattern:
  /about/careers/applications/jobs/results/{numeric-id}-{slug}

We match on that URL segment.

Search URL format:
  https://www.google.com/about/careers/applications/jobs/results/?q="Data+Scientist"
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
BASE_URL = "https://www.google.com"
_JOB_URL_RE = re.compile(r"/jobs/results/\d+")


class GoogleScraper(BaseScraper):
    company = "Google"

    async def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            for role in ROLES:
                found = await self._fetch_role(page, role)
                log.info("Google | %-20s → %d jobs", role, len(found))
                jobs.extend(found)
            await browser.close()
        return jobs

    async def _fetch_role(self, page, role: str) -> list[Job]:
        query = quote_plus(f'"{role}"')
        search_url = (
            f"{BASE_URL}/about/careers/applications/jobs/results/"
            f"?q={query}&hl=en_US"
        )
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                await page.wait_for_selector("a[href*='/jobs/results/']", timeout=25_000)
            except Exception:  # noqa: BLE001
                log.debug("Google: no '/jobs/results/' links appeared within 25s for '%s'", role)
            await page.wait_for_timeout(1_500)
        except Exception as exc:  # noqa: BLE001
            log.warning("Google: page load failed for '%s': %s", role, exc)
            return []

        jobs: list[Job] = []
        seen_urls: set[str] = set()
        anchors = await page.query_selector_all("a[href*='/jobs/results/']")
        for anchor in anchors:
            href = await anchor.get_attribute("href") or ""
            if not _JOB_URL_RE.search(href):
                continue
            title = (await anchor.inner_text()).strip()
            if not title:
                # Google sometimes puts the title in an h3 inside the anchor
                h3 = await anchor.query_selector("h3")
                if h3:
                    title = (await h3.inner_text()).strip()
            if not title:
                continue

            role_tokens = role.lower().split()
            if not all(t in title.lower() for t in role_tokens):
                continue

            full_url = urljoin(BASE_URL, href.split("?")[0])
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            jobs.append(Job(company="Google", title=title, url=full_url, role=role))

        if not jobs and os.environ.get("DEBUG_SCREENSHOTS", "").lower() in ("1", "true"):
            out = Path("debug_screenshots")
            out.mkdir(exist_ok=True)
            slug = role.lower().replace(" ", "_")
            await page.screenshot(path=str(out / f"google_{slug}.png"), full_page=True)
            log.warning("Google: saved debug screenshot for '%s'", role)

        return jobs
