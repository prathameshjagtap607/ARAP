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
    subject = f"Your assessment invitation: {job_title}"
    return _send_email(to, subject, body_html)


_DECISION_SUBJECT = {
    "hire": "Update on your application: {job_title}",
    "hold": "Update on your application: {job_title}",
    "no_hire": "Update on your application: {job_title}",
}

_DECISION_BODY = {
    "hire": "<p>Hi,</p><p>Good news — you've progressed to the next round for <strong>{job_title}</strong>. Our team will be in touch shortly with next steps.</p>",
    "hold": "<p>Hi,</p><p>Thank you for completing the assessment for <strong>{job_title}</strong>. Your application is still under review — we'll follow up as soon as a decision is made.</p>",
    "no_hire": "<p>Hi,</p><p>Thank you for taking the time to complete the assessment for <strong>{job_title}</strong>. We won't be moving forward with your application at this stage, but we appreciate your interest and wish you the best in your search.</p>",
}


def send_decision_email(to: str, job_title: str, decision: str) -> bool:
    """Notify a candidate of the outcome of the AI assessment stage. Non-fatal by design."""
    body_html = _DECISION_BODY.get(decision, _DECISION_BODY["hold"]).format(job_title=job_title)
    subject = _DECISION_SUBJECT.get(decision, _DECISION_SUBJECT["hold"]).format(job_title=job_title)
    return _send_email(to, subject, body_html)


def _send_email(to: str, subject: str, body_html: str) -> bool:
    if settings.SENDGRID_API_KEY:
        if _send_via_sendgrid(to, subject, body_html):
            return True
        logger.warning("sendgrid send failed — falling back to SMTP for %s", to)

    if settings.SMTP_HOST:
        return _send_via_smtp(to, subject, body_html)

    logger.warning("no email provider configured — email not sent to %s", to)
    return False


def _send_via_smtp(to: str, subject: str, body_html: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
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


def _send_via_sendgrid(to: str, subject: str, body_html: str) -> bool:
    import json as _json
    import urllib.error
    import urllib.request
    payload = _json.dumps({
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.SMTP_FROM},
        "subject": subject,
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
