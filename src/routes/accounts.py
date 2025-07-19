import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4
from datetime import datetime, timedelta

from src.config.dependencies import get_email_sender
from src.schemas.accounts import ResendActivationEmailRequest
from src.schemas.accounts import RegisterRequest, RegisterResponse, LoginRequest, ForgotPasswordRequest, PasswordResetToken
from src.database.session_postgresql import get_async_session
from src.security.jwt import create_refresh_token, create_access_token
from src.security.password import get_password_hash, verify_password
from src.database.models.accounts import User, ActivationToken, RefreshToken, UserGroupEnum, UserGroup
from src.notifications.email import AsyncEmailService
from src.tasks.accounts import send_reset_email_async

router = APIRouter()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

@router.post("/register/", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_async_session),
    email_service: AsyncEmailService = Depends(get_email_sender)
):
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    hashed_password = get_password_hash(data.password)
    new_user = User(
        email=data.email,
        hashed_password=hashed_password,
        is_active=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        group_id=1
    )
    db.add(new_user)
    await db.flush()

    token = str(uuid4())
    activation_token = ActivationToken(
        user_id=new_user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(activation_token)
    await db.commit()

    activation_link = f"{BASE_URL}/activate/{token}"

    await email_service.send_account_activation(data.email, activation_link)

    return RegisterResponse(
        email=data.email,
        message="Registration successful. Please check your email to activate your account."
    )


@router.post("/reset-activation/")
async def resend_activation(
        data: ResendActivationEmailRequest,
        db: AsyncSession = Depends(get_async_session),
        email: AsyncEmailService = Depends(get_email_sender)
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email does not exist."
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active."
        )

    activation_token = ActivationToken(
        user_id=user.id,
        token=str(uuid4()),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(activation_token)
    await db.commit()

    activation_link = f"{BASE_URL}/activate/{activation_token.token}"
    await email.send_account_activation(recipient_email=data.email, activation_url=activation_link)

    return RegisterResponse(
        email=data.email,
        message="Registration successful. Please check your email to activate your account."
    )


@router.post("/login/")
async def login(
        data: LoginRequest,
        db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accounts not activated."
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    refresh_expires_at = datetime.utcnow() + timedelta(days=7)

    db.add(
        RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=refresh_expires_at
        )
    )

    await db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token}

@router.post("/logout/")
async def logout(refresh_token: str, db: AsyncSession = Depends(get_async_session)):
    await db.execute(delete(RefreshToken).where(RefreshToken.token == refresh_token))
    await db.commit()
    return {"message": "Successfully logged out."}

@router.post("/forgot-password/")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email does not exist or is not active."
        )

    token = str(uuid4())
    expires = datetime.utcnow() + timedelta(hours=2)
    db.add(PasswordResetToken(user_id=user.id, token=token, expires_at=expires))
    await db.commit()

    reset_link = f"{BASE_URL}/reset-password/{token}"
    await send_reset_email_async(user.email, reset_link)
    return {"message": "Password reset email sent."}

@router.put("/admin/change-group/{user_id}")
async def change_user_group(
    user_id: int,
    new_group: UserGroupEnum,
    db: AsyncSession = Depends(get_async_session)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(select(UserGroup).where(UserGroup.name == new_group.value))
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    user.group_id = group.id
    await db.commit()
    return {"message": "Group updated"}