import logging
from http.client import HTTPException
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from src.config.dependencies import get_async_session, get_current_user, get_current_admin_or_moderator
from src.database.models.orders import Order
from src.database.models.payments import Payment
from src.notifications.email import AsyncEmailService
from src.schemas.payments import PaymentResponse, PaymentStatusEnum

router = APIRouter()

@router.post("/payments/initiate", response_model=PaymentResponse)
async def initiate_payment(
        order_id: int,
        db: AsyncSession = Depends(get_async_session),
        current_user = Depends(get_current_user)
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Cannot initiate payment for paid/canceled order")

    existing_payment = await db.execute(
        select(Payment).where(Payment.order_id == order_id, Payment.status == PaymentStatusEnum.pending)
    )
    if existing_payment.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Payment already initiated")

    payment = Payment(
        order_id=order_id,
        user_id=current_user.id,
        amount=order.total_price,
        status=PaymentStatusEnum.pending
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return payment

@router.post("/payments/webhook")
async def mock_payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    email_service: AsyncEmailService = Depends()
):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    payment_id = payload.get("payment_id")
    new_status = payload.get("status")

    if not payment_id or new_status not in {"successful", "canceled", "refunded"}:
        raise HTTPException(status_code=400, detail="Missing or invalid payment_id or status")

    payment_result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = payment_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment.status = new_status
    await db.commit()

    try:
        subject = f"Payment status update for order {payment.order_id}"
        body=(
            f"Hello, \n\nYour payment with ID {payment_id}"
            f"has been updated to status {new_status}. \n\nThank you."
        )
        await email_service.send_email(payment.user.email, subject, body)
    except Exception as e:
        logging.error(f"Error sending email: {e}")

    return {"message": "Payment status updated"}

@router.get("/payments/history", response_model=list[PaymentResponse])
async def get_payment_history(
        db: AsyncSession = Depends(get_async_session),
        current_user = Depends(get_current_user)
):
    result = await db.execute(select(Payment).where(Payment.user_id == current_user.id))
    return result.scalars().all()

@router.get("/payments/admin", response_model=list[PaymentResponse])
async def get_all_payments_for_admin(
        user_id: Optional[int] = None,
        status: Optional[PaymentStatusEnum] = None,
        db: AsyncSession = Depends(get_async_session),
        admin_user = Depends(get_current_admin_or_moderator)
):
    filters = []
    if user_id:
        filters.append(Payment.user_id == user_id)
    if status:
        filters.append(Payment.status == status)

    stmt = select(Payment)
    if filters:
        stmt = stmt.where(*filters)

    result = await db.execute(stmt)
    return result.scalars().all()