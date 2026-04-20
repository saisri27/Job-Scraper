# Job Scraper (Playwright)

Scrapes **Apple** and **Google** careers pages for `Data Scientist` and `AI Engineer` roles, runs 4×/day on GitHub Actions, and emails you when new postings appear.

## Package layout

```
job_scraper/
├── __main__.py        # Entry point
├── config.py          # Email config loaded from env / GitHub Secrets
├── emailer.py         # SMTP email digest (HTML + plain text)
├── seen_store.py      # Dedup persistence (.state/seen_jobs.json, 30-day TTL)
└── scrapers/
    ├── base.py        # Job dataclass + BaseScraper ABC
    ├── apple.py       # Matches /details/{id} URL pattern
    └── google.py      # Matches /jobs/results/{id} URL pattern
```

## GitHub Secrets to add

In your GitHub repo → **Settings → Secrets and variables → Actions**:

- `EMAIL_HOST` (e.g. `smtp.gmail.com`)
- `EMAIL_PORT` (e.g. `587`)
- `EMAIL_USER` (your sender email)
- `EMAIL_PASS` (email **app password**, not your regular password)
- `EMAIL_TO` (recipient email; can be same as `EMAIL_USER`)

## Running

- **Scheduled**: every 6 hours via cron (`0 */6 * * *`)
- **Manual**: Actions tab → *Job Scraper* → *Run workflow*
  - Set **reset_store** to `true` on the first real run to force an email with everything found.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m job_scraper --verbose --reset-store --dry-run
```

- `--dry-run` — log results, don't send email or persist state
- `--reset-store` — treat every job as new (useful for first run / testing)
- `--verbose` — debug logging
