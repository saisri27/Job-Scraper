import hashlib
import json
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import quote_plus, urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


STATE_FILE = Path(".cache/seen_jobs.json")


@dataclass
class JobPosting:
    job_id: str
    company: str
    role: str
    title: str
    url: str


def build_targets() -> List[Dict[str, str]]:
    roles = ["Data Scientist", "AI Engineer"]
    targets: List[Dict[str, str]] = []
    for role in roles:
        encoded = quote_plus(role)
        targets.append(
            {
                "company": "Cisco",
                "role": role,
                "search_url": f"https://jobs.cisco.com/jobs/SearchJobs/?keyword={encoded}",
            }
        )
        targets.append(
            {
                "company": "IBM",
                "role": role,
                "search_url": f"https://careers.ibm.com/job/search/?q={encoded}",
            }
        )
    return targets


def stable_job_id(company: str, role: str, title: str, url: str) -> str:
    raw = f"{company}|{role}|{title.strip().lower()}|{url.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_seen_ids() -> Set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen_job_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen_ids(ids: Set[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"seen_job_ids": sorted(ids)}, indent=2), encoding="utf-8")


def looks_like_job_link(text: str, href: str, role: str) -> bool:
    haystack = f"{text} {href}".lower()
    role_ok = all(part.lower() in haystack for part in role.split())
    has_job_word = any(t in haystack for t in ["job", "career", "position", "opening", "requisition"])
    return role_ok and has_job_word


def scrape_target(page, company: str, role: str, search_url: str) -> List[JobPosting]:
    page.goto(search_url, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(2500)
    anchors = page.locator("a")
    count = anchors.count()

    found: List[JobPosting] = []
    seen_urls: Set[str] = set()
    for i in range(count):
        anchor = anchors.nth(i)
        href = anchor.get_attribute("href")
        title = (anchor.inner_text() or "").strip()
        if not href or not title:
            continue
        full_url = urljoin(page.url, href)
        if full_url in seen_urls:
            continue
        if not looks_like_job_link(title, full_url, role):
            continue
        seen_urls.add(full_url)
        found.append(
            JobPosting(
                job_id=stable_job_id(company, role, title, full_url),
                company=company,
                role=role,
                title=title,
                url=full_url,
            )
        )
    return found


def send_email_alert(new_jobs: List[JobPosting]) -> None:
    smtp_host = os.getenv("EMAIL_HOST")
    smtp_port = int(os.getenv("EMAIL_PORT", "587"))
    smtp_user = os.getenv("EMAIL_USER")
    smtp_pass = os.getenv("EMAIL_PASS")
    email_to = os.getenv("EMAIL_TO", smtp_user or "")
    if not (smtp_host and smtp_user and smtp_pass and email_to):
        print("Email settings incomplete; skipping alert.")
        return

    lines: List[str] = []
    for job in new_jobs:
        lines.append(f"- {job.company} | {job.role} | {job.title}")
        lines.append(f"  {job.url}")
    body = "New matching jobs were found:\n\n" + "\n".join(lines)

    message = EmailMessage()
    message["Subject"] = f"New job postings found: {len(new_jobs)}"
    message["From"] = smtp_user
    message["To"] = email_to
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(message)
    print(f"Email sent to {email_to}.")


def main() -> None:
    targets = build_targets()
    seen_ids = load_seen_ids()
    collected: List[JobPosting] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for target in targets:
            company = target["company"]
            role = target["role"]
            search_url = target["search_url"]
            print(f"Scraping {company} for {role}")
            try:
                jobs = scrape_target(page, company, role, search_url)
                print(f"Found {len(jobs)} potential matches")
                collected.extend(jobs)
            except (PlaywrightError, PlaywrightTimeoutError) as exc:
                print(f"Failed scraping {company} ({role}): {exc}")
        browser.close()

    deduped: Dict[str, JobPosting] = {job.job_id: job for job in collected}
    current_ids = set(deduped.keys())
    new_ids = current_ids - seen_ids
    new_jobs = [deduped[job_id] for job_id in sorted(new_ids)]

    print(f"Total unique matches this run: {len(current_ids)}")
    print(f"New jobs this run: {len(new_jobs)}")

    if new_jobs:
        send_email_alert(new_jobs)

    save_seen_ids(seen_ids.union(current_ids))


if __name__ == "__main__":
    main()
