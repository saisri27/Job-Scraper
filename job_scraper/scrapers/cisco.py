"""Playwright scraper for Cisco careers (jobs.cisco.com).

Cisco uses Oracle Taleo; individual job detail URLs always contain
'ProjectDetail' in the path, e.g.:
  https://jobs.cisco.com/jobs/ProjectDetail/Senior-Data-Scientist/1415369

We anchor on that URL fragment so we never depend on fragile CSS class names.
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus, urljoin

from playwright.async_api import async_playwright

from .base import BaseScraper, Job

log = logging.getLogger(__name__)

ROLES = ["Data Scientist", "AI Engineer"]
BASE_URL = "https://jobs.cisco.com"


class CiscoScraper(BaseScraper):
    company = "Cisco"

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
                log.info("Cisco | %-20s → %d jobs", role, len(found))
                jobs.extend(found)
            await browser.close()
        return jobs

    async def _fetch_role(self, page, role: str) -> list[Job]:
        search_url = f"{BASE_URL}/jobs/SearchJobs/{quote_plus(role)}"
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60_000)
            await page.wait_for_timeout(3_000)
        except Exception as exc:  # noqa: BLE001
            log.warning("Cisco: page load failed for '%s': %s", role, exc)
            return []

        jobs: list[Job] = []
        seen: set[str] = set()

        # Primary: Taleo job-detail URL fragment
        for fragment in ("ProjectDetail", "/jobs/detail/", "/jobs/view/"):
            anchors = await page.query_selector_all(f"a[href*='{fragment}']")
            for anchor in anchors:
                title = (await anchor.inner_text()).strip()
                href = await anchor.get_attribute("href") or ""
                if not title or not href:
                    continue
                full_url = urljoin(BASE_URL, href)
                if full_url in seen:
                    continue
                seen.add(full_url)
                jobs.append(Job(company="Cisco", title=title, url=full_url, role=role))

        # Fallback: scan all links and filter by role keywords in the title
        if not jobs:
            log.debug("Cisco: primary selector found nothing for '%s'; using fallback", role)
            tokens = role.lower().split()
            for anchor in await page.query_selector_all("a"):
                title = (await anchor.inner_text()).strip()
                href = await anchor.get_attribute("href") or ""
                if not title or not href:
                    continue
                if not all(t in title.lower() for t in tokens):
                    continue
                full_url = urljoin(BASE_URL, href)
                if full_url in seen or full_url == search_url:
                    continue
                seen.add(full_url)
                jobs.append(Job(company="Cisco", title=title, url=full_url, role=role))

        return jobs
