from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum as SaEnum, Numeric
from sqlalchemy.orm import Mapped, relationship, mapped_column
from .base import Base


class OrderStatusEnum(str, PyEnum):
    pending = "pending"
    paid = "paid"
    canceled = "canceled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    status: Mapped[OrderStatusEnum] = mapped_column(
        SaEnum(OrderStatusEnum, name="orderstatusenum"),
        nullable=False,
        default=OrderStatusEnum.pending
    )
    total_amount = Column(Numeric(10, 2), nullable=True)

    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")



class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    price_at_order = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="order_items")
    movie = relationship("Movie")
    payment_items = relationship("PaymentItem", back_populates="order_item")
