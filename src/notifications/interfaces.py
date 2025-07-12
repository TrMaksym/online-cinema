from abc import ABC, abstractmethod

class EmailServiceProtocol(ABC):

    @abstractmethod
    async def send_account_activation(self, recipient_email: str, activation_url: str) -> None:
        pass

    @abstractmethod
    async def notify_activation_success(self, recipient_email: str, dashboard_url: str) -> None:
        pass

    @abstractmethod
    async def send_password_reset_request(self, recipient_email: str, reset_url: str) -> None:
        pass

    @abstractmethod
    async def confirm_password_reset(self, recipient_email: str, login_url: str) -> None:
        pass