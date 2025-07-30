from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional

class PaymentStatusEnum(str, Enum):
    pending = "pending"
    successful = "successful"
    canceled = "canceled"
    refunded = "refunded"

class PaymentResponse(BaseModel):
    id: int
    user_id: int
    order_id: int
    created_at: datetime
    status: PaymentStatusEnum
    amount: float
    external_payment_id: Optional[str]

    class Config:
        orm_mode = True
