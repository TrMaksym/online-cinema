import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4
from datetime import datetime, timedelta

from src.config.dependencies import get_email_sender
from src.schemas.accounts import ResendActivationEmailRequest, ChangePasswordRequest
from src.schemas.accounts import RegisterRequest, RegisterResponse, LoginRequest, ForgotPasswordRequest, PasswordResetToken
from src.database.session_postgresql import get_async_session
from src.security.jwt import create_refresh_token, create_access_token
from src.security.password import get_password_hash, verify_password
from src.database.models.accounts import User, ActivationToken, RefreshToken, UserGroupEnum, UserGroup
from src.notifications.email import AsyncEmailService
from src.tasks.accounts import send_reset_email_async
from src.validation.accounts import validate_password_complexity

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

    if not validate_password_complexity(data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain at least one number and one letter."
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

@router.get("/activate/{token}")
async def activate_user(token: str, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(ActivationToken).where(ActivationToken.token == token))
    activation_token = result.scalars().first()

    if not activation_token or activation_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid activation token or expired")

    user = await db.get(User, activation_token.user_id)
    if user.is_active:
        return {"message": "Account already activated"}

    user.is_active = True
    await db.delete(activation_token)
    await db.commit()
    return {"message": "Account activated successfully"}

@router.put("/reset-password/{token}")
async def reset_password(token: str, new_password: str, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token))
    reset_token = result.scalars().first()

    if not reset_token or reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")

    user = await db.get(User, reset_token.user_id)

    if not validate_password_complexity(new_password):
        raise HTTPException(status_code=400,
            detail="Password must be at least 8 characters long and include an uppercase letter, number, and special character."
        )

    user.hashed_password = get_password_hash(new_password)

    await db.delete(reset_token)
    await db.commit()

    return {"message": "Password successfully reset"}

@router.put("/change-password/")
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if not validate_password_complexity(data.new_password):
        raise HTTPException(status_code=400,
            detail="Password must be at least 8 characters long and include an uppercase letter, number, and special character."
        )

    user.hashed_password = get_password_hash(data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}

@router.post("/refresh-token/")
async def refresh_access_token(
        refresh_token: str,
        db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == refresh_token))
    token_record = result.scalars().first()

    if not token_record or token_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = create_access_token(token_record.user_id)
    return {"access_token": access_token}


@router.put("/admin/activate-user/{user_id}")
async def activate_user_admin(
        user_id: int,
        db: AsyncSession = Depends(get_async_session)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User no found")

    if user.is_active:
        return {"message": "User already active"}

    user.is_active = True
    await db.commit()
    return {"message": "User activated successfully"}

