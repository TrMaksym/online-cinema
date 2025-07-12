import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from exceptions import EmailDeliveryError
from notifications.interfaces import EmailServiceProtocol

class AsyncEmailService(EmailServiceProtocol):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        use_tls: bool,
    ):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._sender_email = sender_email
        self._sender_password = sender_password
        self._use_tls = use_tls

    async def _send(self, recipient: str, subject: str, body_text: str):
        message = MIMEMultipart()
        message["From"] = self._sender_email
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(body_text, "plain"))

        try:
            smtp = aiosmtplib.SMTP(
                hostname=self._smtp_host,
                port=self._smtp_port,
                start_tls=self._use_tls
            )
            await smtp.connect()
            if self._use_tls:
                await smtp.starttls()
            await smtp.login(self._sender_email, self._sender_password)
            await smtp.sendmail(self._sender_email, [recipient], message.as_string())
            await smtp.quit()
        except Exception as e:
            logging.exception("Failed to send email")
            raise EmailDeliveryError(f"Failed to send email to {recipient}: {e}")

    async def send_account_activation(self, recipient_email: str, activation_url: str) -> None:
        subject = "Account Activation"
        body = (
            f"Hello,\n\n"
            f"To activate your account, please follow this link:\n{activation_url}\n\n"
            f"If you did not request this, just ignore this message."
        )
        await self._send(recipient_email, subject, body)

    async def notify_activation_success(self, recipient_email: str, dashboard_url: str) -> None:
        subject = "Your Account Has Been Activated"
        body = (
            f"Hello,\n\n"
            f"Your account has been successfully activated.\n"
            f"You can now log in here:\n{dashboard_url}\n\n"
            f"Thank you!"
        )
        await self._send(recipient_email, subject, body)

    async def send_password_reset_request(self, recipient_email: str, reset_url: str) -> None:
        subject = "Password Reset Request"
        body = (
            f"Hello,\n\n"
            f"We received a request to reset your password.\n"
            f"You can do that using this link:\n{reset_url}\n\n"
            f"If you didn’t request this, you can safely ignore it."
        )
        await self._send(recipient_email, subject, body)

    async def confirm_password_reset(self, recipient_email: str, login_url: str) -> None:
        subject = "Password Changed Successfully"
        body = (
            f"Hello,\n\n"
            f"Your password has been successfully changed.\n"
            f"If this wasn’t you, please reset your password immediately.\n"
            f"Login: {login_url}"
        )
        await self._send(recipient_email, subject, body)
