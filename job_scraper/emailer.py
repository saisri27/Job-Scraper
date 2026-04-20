"""Send an email digest of newly discovered job postings."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .config import EmailConfig, is_configured
from .scrapers.base import Job

log = logging.getLogger(__name__)


def send_job_digest(jobs: list[Job], cfg: EmailConfig) -> None:
    if not jobs:
        log.info("No new jobs to email.")
        return

    if not is_configured(cfg):
        log.warning("Email not configured (missing secrets); skipping digest.")
        return

    subject = f"[Job Alert] {len(jobs)} new posting{'s' if len(jobs) != 1 else ''} — Cisco & IBM"

    # Plain-text body
    lines: list[str] = ["New job postings matching your search:\n"]
    for job in jobs:
        lines.append(f"  [{job.company}] {job.title}")
        if job.location:
            lines.append(f"    Location : {job.location}")
        lines.append(f"    Role     : {job.role}")
        lines.append(f"    Link     : {job.url}")
        lines.append("")
    lines.append("-- Job Scraper Bot")
    body = "\n".join(lines)

    # HTML body for nicer rendering
    html_rows = ""
    for job in jobs:
        html_rows += (
            f"<tr>"
            f"<td style='padding:6px 12px'>{job.company}</td>"
            f"<td style='padding:6px 12px'>{job.role}</td>"
            f"<td style='padding:6px 12px'><a href='{job.url}'>{job.title}</a></td>"
            f"<td style='padding:6px 12px'>{job.location or '—'}</td>"
            f"</tr>"
        )
    html = f"""
    <html><body>
    <h2 style='font-family:sans-serif'>New Job Postings — Cisco &amp; IBM</h2>
    <table border='1' cellspacing='0' style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>
      <thead style='background:#f0f0f0'>
        <tr>
          <th style='padding:6px 12px'>Company</th>
          <th style='padding:6px 12px'>Role</th>
          <th style='padding:6px 12px'>Title</th>
          <th style='padding:6px 12px'>Location</th>
        </tr>
      </thead>
      <tbody>{html_rows}</tbody>
    </table>
    </body></html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.user
    msg["To"] = cfg.to
    msg.set_content(body)
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(cfg.host, cfg.port) as smtp:
            smtp.starttls()
            smtp.login(cfg.user, cfg.password)
            smtp.send_message(msg)
        log.info("Email sent to %s with %d new jobs.", cfg.to, len(jobs))
    except smtplib.SMTPException as exc:
        log.error("Failed to send email: %s", exc)
        raise
