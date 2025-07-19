from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import List

from src.database.models import Order, OrderItem, Movie
from schemas import OrderCreateRequest, OrderResponse
from config.dependencies import get_async_session, get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user)
):

    movies_ids = order_data.movie_ids
    query = select(OrderItem).join(Order).where(
        Order.user_id == current_user.id,
        OrderItem.movie_id.in_(movies_ids)
    )
    existing_items = (await db.execute(query)).scalars().all()
    if existing_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some movies are already purchased."
        )

    query_movies = select(Movie).where(Movie.id.in_(movies_ids))
    movies = (await db.execute(query_movies)).scalars().all()
    if len(movies) != len(movies_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more movies not found."
        )

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
        order_item = OrderItem(
            order_id=new_order.id,
            movie_id=movie.id
        )
        db.add(order_item)

    await db.commit()

    return OrderResponse(
        id=new_order.id,
        created_at=new_order.created_at,
        total_price=new_order.total_price,
        status=new_order.status,
        movies=[{"id": m.id, "name": m.name, "price": m.price} for m in movies]
    )


@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user)
):
    query = select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    orders = (await db.execute(query)).scalars().all()

    orders_responses = []
    for order in orders:
        query_items = select(OrderItem).where(OrderItem.order_id == order.id)
        items = (await db.execute(query_items)).scalars().all()
        movie_ids = [item.movie_id for item in items]

        query_movies = select(Movie).where(Movie.id.in_(movie_ids))
        movies = (await db.execute(query_movies)).scalars().all()

        orders_responses.append(OrderResponse(
            id=order.id,
            created_at=order.created_at,
            total_price=order.total_price,
            status=order.status,
            movies=[{"id": m.id, "name": m.name, "price": m.price} for m in movies]
        ))

    return orders_responses
