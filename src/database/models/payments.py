from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum as SaEnum, Numeric, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from enum import Enum as PyEnum

from database.models.base import Base

class PaymentStatusEnum(str, PyEnum):
    successful = "successful"
    cancelled = "cancelled"
    refunded = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SaEnum(PaymentStatusEnum, name="paymentstatusenum"),
        default=PaymentStatusEnum.successful,
        nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String(255), nullable=True)

    user = relationship("User", back_populates="payments")
    order = relationship("Order", back_populates="payments")
    payment_items = relationship("PaymentItem", back_populates="payment", cascade="all, delete-orphan")


class PaymentItem(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    price_at_payment: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    payment = relationship("Payment", back_populates="payment_items")
    order_item = relationship("OrderItem", back_populates="payment_items")