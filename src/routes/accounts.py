from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, session

from sqlalchemy.future import select
from uuid import uuid4
from datetime import datetime, timedelta

from src.schemas.accounts import (
    RegisterRequest, RegisterResponse,
    ActivationResponse, ResendActivationRequest, ResendActivationResponse
)
from src.database.session_postgresql import get_async_session
from src.security.passwords import get_password_hash
from src.database.models.accounts import User, ActivationToken
from src.notifications.emails import send_activation_email_async

router = APIRouter()

@router.post("/register/", response_model=RegisterResponse)
async def register_user(data: RegisterResponse, db: AsyncSession = Depends(get_async_session)):
    result = await session.execute()