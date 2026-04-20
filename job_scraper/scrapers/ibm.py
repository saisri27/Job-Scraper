"""Playwright scraper for IBM careers (careers.ibm.com).

IBM's SPA renders individual job cards; each card's anchor href follows:
  /job/{numeric-id}/{slug}/

We match on  a[href*="/job/"]  and confirm the segment after /job/ is numeric
so we don't accidentally pick up navigation links that also contain '/job/'.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urljoin

from playwright.async_api import async_playwright

from .base import BaseScraper, Job

log = logging.getLogger(__name__)

ROLES = ["Data Scientist", "AI Engineer"]
BASE_URL = "https://careers.ibm.com"
_JOB_URL_RE = re.compile(r"/job/\d+/")


class IBMScraper(BaseScraper):
    company = "IBM"

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
                log.info("IBM   | %-20s → %d jobs", role, len(found))
                jobs.extend(found)
            await browser.close()
        return jobs

    async def _fetch_role(self, page, role: str) -> list[Job]:
        search_url = f"{BASE_URL}/job/search/?q={quote_plus(role)}&country=us"
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60_000)
            await page.wait_for_timeout(4_000)
        except Exception as exc:  # noqa: BLE001
            log.warning("IBM: page load failed for '%s': %s", role, exc)
            return []

        jobs: list[Job] = []
        seen: set[str] = set()

        # Primary: anchors whose href matches /job/{id}/ pattern
        anchors = await page.query_selector_all("a[href*='/job/']")
        for anchor in anchors:
            href = await anchor.get_attribute("href") or ""
            if not _JOB_URL_RE.search(href):
                continue
            title = (await anchor.inner_text()).strip()
            if not title:
                # title might be in a child element; try the parent list item
                parent = await anchor.query_selector("xpath=..")
                if parent:
                    title = (await parent.inner_text()).strip().splitlines()[0].strip()
            if not title:
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            jobs.append(Job(company="IBM", title=title, url=full_url, role=role))

        # Fallback: role-keyword filter across all links
        if not jobs:
            log.debug("IBM: primary selector found nothing for '%s'; using fallback", role)
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
                jobs.append(Job(company="IBM", title=title, url=full_url, role=role))

        return jobs
