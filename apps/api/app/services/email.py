from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.settings import get_settings
from app.models import AuthOtpPurpose

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when a required auth email cannot be sent safely."""


def _purpose_subject(purpose: AuthOtpPurpose) -> str:
    if purpose == AuthOtpPurpose.PASSWORD_RESET:
        return "Your KALYPTO password reset code"
    return "Your KALYPTO verification code"


def _purpose_body(*, otp_code: str, purpose: AuthOtpPurpose) -> str:
    if purpose == AuthOtpPurpose.PASSWORD_RESET:
        intro = "Use this code to reset your KALYPTO password."
    else:
        intro = "Use this code to verify your KALYPTO account."
    return (
        f"{intro}\n\n"
        f"Code: {otp_code}\n\n"
        "This code expires in 10 minutes. If you did not request it, you can ignore this email."
    )


def _resend_api_key() -> str | None:
    settings = get_settings()
    if settings.resend_api_key:
        return settings.resend_api_key
    if (
        settings.smtp_host
        and settings.smtp_host.lower() == "smtp.resend.com"
        and settings.smtp_username == "resend"
        and settings.smtp_password
    ):
        return settings.smtp_password
    return None


def _send_with_resend_http(*, email: str, otp_code: str, purpose: AuthOtpPurpose) -> bool:
    settings = get_settings()
    api_key = _resend_api_key()
    if not api_key or not settings.smtp_from_email:
        return False

    recipient_domain = email.rsplit("@", 1)[-1] if "@" in email else "unknown"
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": f"{settings.smtp_from_name} <{settings.smtp_from_email}>",
                "to": [email],
                "subject": _purpose_subject(purpose),
                "text": _purpose_body(otp_code=otp_code, purpose=purpose),
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(
            "Sent auth email with Resend HTTP: from=%s recipient_domain=%s purpose=%s",
            settings.smtp_from_email,
            recipient_domain,
            purpose.value,
        )
        return True
    except httpx.HTTPStatusError as error:
        logger.exception(
            "Resend auth email delivery failed: status=%s from=%s recipient_domain=%s purpose=%s response=%s",
            error.response.status_code,
            settings.smtp_from_email,
            recipient_domain,
            purpose.value,
            error.response.text[:500],
        )
        raise EmailDeliveryError("Email delivery failed.") from error
    except httpx.HTTPError as error:
        logger.exception(
            "Resend auth email request failed: from=%s recipient_domain=%s purpose=%s error_type=%s error=%s",
            settings.smtp_from_email,
            recipient_domain,
            purpose.value,
            type(error).__name__,
            error,
        )
        raise EmailDeliveryError("Email delivery failed.") from error


def send_auth_otp_email(*, email: str, otp_code: str, purpose: AuthOtpPurpose) -> None:
    settings = get_settings()
    has_smtp = bool(settings.smtp_host and settings.smtp_from_email)
    has_resend = bool(_resend_api_key() and settings.smtp_from_email)
    recipient_domain = email.rsplit("@", 1)[-1] if "@" in email else "unknown"

    if not has_smtp and not has_resend:
        if settings.environment.lower() == "production":
            raise EmailDeliveryError("Email delivery is not configured.")
        logger.warning(
            "Development auth OTP for %s (%s): %s",
            email,
            purpose.value,
            otp_code,
        )
        return

    if _send_with_resend_http(email=email, otp_code=otp_code, purpose=purpose):
        return

    message = EmailMessage()
    message["Subject"] = _purpose_subject(purpose)
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = email
    message.set_content(_purpose_body(otp_code=otp_code, purpose=purpose))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        logger.exception(
            "SMTP auth email delivery failed: host=%s port=%s from=%s recipient_domain=%s purpose=%s error_type=%s error=%s",
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_from_email,
            recipient_domain,
            purpose.value,
            type(error).__name__,
            error,
        )
        raise EmailDeliveryError("Email delivery failed.") from error
