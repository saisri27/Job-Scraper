# Job Scraper (Playwright)

This project runs a GitHub Actions workflow that:

- Scrapes Cisco and IBM career pages
- Looks for `Data Scientist` and `AI Engineer` postings
- Runs 4 times per day
- Sends an email when newly discovered jobs appear

## GitHub Secrets to add

In your GitHub repo, go to **Settings -> Secrets and variables -> Actions** and add:

- `EMAIL_HOST` (example: `smtp.gmail.com`)
- `EMAIL_PORT` (example: `587`)
- `EMAIL_USER` (your sender email)
- `EMAIL_PASS` (email app password / passcode)
- `EMAIL_TO` (your destination email; can be same as `EMAIL_USER`)

## Workflow details

- Workflow file: `.github/workflows/job-scraper.yml`
- Schedule: every 6 hours via cron (`0 */6 * * *`)
- Manual trigger: supported via `workflow_dispatch`

## Local run (optional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python scripts/scrape_jobs.py
```
