from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped
from src.database.models.accounts import User

from .base import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    user = relationship("User", back_populates="cart")

    items = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User", back_populates="cart")



class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    cart = relationship("Cart", back_populates="items")
    movie = relationship("Movie")
