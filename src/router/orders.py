from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import List

from src.database.models.orders import Order, OrderItem
from src.database.models.movies import Movie
from src.database.models.shopping_cart import Cart
from src.schemas.orders import OrderCreateRequest, OrderResponse
from src.config.dependencies import get_async_session, get_current_user

router = APIRouter()

@router.post("/from-cart", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_from_cart(
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user)
):
    cart_result = await db.execute(
        select(Cart).where(Cart.user_id == current_user.id)
    )
    cart = cart_result.scalar_one_or_none()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    movie_ids = [item.movie_id for item in cart.items]

    purchased_result = await db.execute(
        select(OrderItem.movie_id).join(Order).where(
            Order.user_id == current_user.id,
            OrderItem.movie_id.in_(movie_ids)
        )
    )
    already_purchased = {row[0] for row in purchased_result.all()}
    available_ids = [mid for mid in movie_ids if mid not in already_purchased]

    if not available_ids:
        raise HTTPException(status_code=400, detail="All movies already purchased")

    movies_result = await db.execute(select(Movie).where(Movie.id.in_(available_ids)))
    movies = movies_result.scalars().all()

    total_price = sum(movie.price for movie in movies)
    new_order = Order(
        user_id=current_user.id,
        created_at=datetime.utcnow(),
        total_price=total_price,
        status="paid"
    )
    db.add(new_order)
    await db.flush()

    for movie in movies:
        db.add(OrderItem(order_id=new_order.id, movie_id=movie.id))

    for item in cart.items:
        db.delete(item)

    await db.commit()

    return OrderResponse(
        id=new_order.id,
        created_at=new_order.created_at,
        total_price=new_order.total_price,
        status=new_order.status,
        movies=[{"id": m.id, "name": m.name, "price": m.price} for m in movies]
    )
