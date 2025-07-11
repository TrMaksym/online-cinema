from datetime import datetime, date, timedelta
from typing import Optional

from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship, Mapped, mapped_column


class UserGroupEnum(str, Enum):
    USER = "USER"
    MODERATOR = "MODERATOR"
    ADMIN = "ADMIN"

class GenderEnum(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

class UserGroup(Base):
    __tablename__ = "user_groups"
    id = Column(Integer, primary_key=True)
    name = Column(Enum(UserGroupEnum), unique=True, nullable=False)

    users = relationship("User", back_populates="group")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullbale=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, defauly=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=False)
    group = relationship("UserGroup", back_populates="users")
    profile = relationship("UserProfile", back_populates="user", uselist=False)

    activation_tokens = relationship("UserActivationToken", back_populates="user")
    reset_password_tokens = relationship("UserResetPasswordToken", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    info: Mapped[Optional[str]] = mapped_column(Text)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    user: Mapped[User] = relationship("User", back_populates="profile")


class ActivationToken(Base):
    __tablename__ = "activation_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.now() + timedelta(hours=24))

    user = relationship("User", back_populates="activation_tokens")


class UserResetPassword(Base):
    __tablename__ = "user_password_reset"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.now() + timedelta(hours=24))

    user = relationship("User", back_populates="refresh_tokens")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.now() + timedelta(hours=24))
