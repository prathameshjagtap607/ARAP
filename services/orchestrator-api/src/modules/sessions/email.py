import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import settings

logger = logging.getLogger(__name__)

_BODY_TEMPLATE = """\
<p>Hi,</p>
<p>You have been invited to complete an assessment for <strong>{job_title}</strong>.</p>
<p>Duration: {duration_minutes} minutes.</p>
<p><a href="{link}">Click here to start your assessment</a></p>
<p>This link is valid for 15 minutes from the time of clicking.</p>
"""


def send_invite_email(
    to: str,
    link: str,
    job_title: str,
    duration_minutes: int,
) -> bool:
    """Send magic-link invite email. Returns True if sent, False if no provider configured."""
    body_html = _BODY_TEMPLATE.format(
        job_title=job_title, duration_minutes=duration_minutes, link=link
    )

    if settings.SENDGRID_API_KEY:
        if _send_via_sendgrid(to, body_html, job_title):
            return True
        logger.warning("sendgrid send failed — falling back to SMTP for %s", to)

    if settings.SMTP_HOST:
        return _send_via_smtp(to, body_html, job_title)

    logger.warning("no email provider configured — link not sent: %s", link)
    return False


def _send_via_smtp(to: str, body_html: str, job_title: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your assessment invitation: {job_title}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())
        return True
    except Exception as e:
        logger.error("smtp send failed: %s", e)
        return False


def _send_via_sendgrid(to: str, body_html: str, job_title: str) -> bool:
    import json as _json
    import urllib.error
    import urllib.request
    payload = _json.dumps({
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.SMTP_FROM},
        "subject": f"Your assessment invitation: {job_title}",
        "content": [{"type": "text/html", "value": body_html}],
    }).encode()
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 202)
    except urllib.error.HTTPError as e:
        logger.error("sendgrid error %s: %s", e.code, e.read())
        return False
