from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4
from datetime import datetime, timedelta

from config.dependencies import get_email_sender
from src.schemas.accounts import RegisterRequest, RegisterResponse
from src.database.session_postgresql import get_async_session
from src.security.password import get_password_hash
from src.database.models.accounts import User, ActivationToken
from src.notifications.email import AsyncEmailService

router = APIRouter()


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

    activation_link = f"https://example.com/activate/{token}"

    await email_service.send_account_activation(data.email, activation_link)

    return RegisterResponse(
        email=data.email,
        message="Registration successful. Please check your email to activate your account."
    )
