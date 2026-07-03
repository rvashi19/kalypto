from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

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


def send_auth_otp_email(*, email: str, otp_code: str, purpose: AuthOtpPurpose) -> None:
    settings = get_settings()
    has_smtp = bool(settings.smtp_host and settings.smtp_from_email)

    if not has_smtp:
        if settings.environment.lower() == "production":
            raise EmailDeliveryError("Email delivery is not configured.")
        logger.warning(
            "Development auth OTP for %s (%s): %s",
            email,
            purpose.value,
            otp_code,
        )
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
    except OSError as error:
        raise EmailDeliveryError("Email delivery failed.") from error
