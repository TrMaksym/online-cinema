import pytest
from unittest.mock import AsyncMock, patch
from src.notifications.email import AsyncEmailService, EmailDeliveryError

@pytest.mark.asyncio
async def test_send_email_success():
    service = AsyncEmailService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        sender_email="sender@test.com",
        sender_password="password",
        use_tls=True
    )

    with patch.object(service, "_send", new_callable=AsyncMock) as mock_send:
        result = await service.send_email(
            recipient="email@example.com",
            subject="Test Email",
            body_text="This is a test email."
        )

        mock_send.assert_awaited_once()
        args, kwargs = mock_send.await_args
        assert args == ("email@example.com", "Test Email", "This is a test email.")
        assert kwargs == {}
        assert result is None

@pytest.mark.asyncio
async def test_send_email_failure():
    service = AsyncEmailService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        sender_email="sender@test.com",
        sender_password="password",
        use_tls=True
    )

    with patch.object(service, "_send", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = EmailDeliveryError("SMTP error")

        with pytest.raises(EmailDeliveryError):
            await service.send_email(
                recipient="user@example.com",
                subject="Hello",
                body_text="Test body"
            )

@pytest.mark.asyncio
async def test_send_account_activation():
    service = AsyncEmailService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        sender_email="sender@test.com",
        sender_password="password",
        use_tls=True
    )

    with patch.object(service, "_send", new_callable=AsyncMock) as mock_send:
        activation_link ="http://test.com/activate"
        await service.send_account_activation("user@example.com", activation_link)

        mock_send.assert_awaited_once()
        args, kwargs = mock_send.await_args
        assert args[0] == "user@example.com"
        assert args[1] == "Account Activation"
        assert activation_link in args[2]
        assert kwargs.get("html") is True

@pytest.mark.asyncio
async def test_notify_activation_success():
    service = AsyncEmailService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        sender_email="email@example.com",
        sender_password="password",
        use_tls=True
    )

    with patch.object(service, "_send", new_callable=AsyncMock) as mock_send:
        dashboard_url = "http://test.com/dashboard"
        await service.notify_activation_success("email@example.com", dashboard_url)

        mock_send.assert_awaited_once()
        args, kwargs = mock_send.await_args
        assert args[0] == "email@example.com"
        assert args[1] == "Your Account Has Been Activated"
        assert dashboard_url in args[2]
        assert kwargs.get("html") is None or kwargs.get("html") is False

@pytest.mark.asyncio
async def test_send_password_reset_request():
    service = AsyncEmailService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        sender_email="sender@test.com",
        sender_password="password",
        use_tls=True
    )
    with patch.object(service, "_send", new_callable=AsyncMock) as mock_send:
        reset_url = "http://test.com/reset"
        await service.send_password_reset_request("user@example.com", reset_url)

        mock_send.assert_awaited_once()
        args, kwargs = mock_send.await_args
        assert args[0] == "user@example.com"
        assert args[1] == "Password Reset Request"
        assert reset_url in args[2]
        assert kwargs.get("html") is None or kwargs.get("html") is False

@pytest.mark.asyncio
async def test_confirm_password_reset():
    service = AsyncEmailService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        sender_email="email@example.com",
        sender_password="password",
        use_tls=True
    )

    with patch.object(service, "_send", new_callable=AsyncMock) as mock_send:
        login_url = "http://test.com/login"
        await service.confirm_password_reset("email@example.com", login_url)

        mock_send.assert_awaited_once()
        args, kwargs = mock_send.await_args
        assert args[0] == "email@example.com"
        assert args[1] == "Password Changed Successfully"
        assert login_url in args[2]
        assert kwargs.get("html") is None or kwargs.get("html") is False