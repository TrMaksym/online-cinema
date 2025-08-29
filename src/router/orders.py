from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import List, Optional

from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.database.models.movies import Movie
from src.database.models.shopping_cart import Cart
from src.schemas.orders import OrderResponse, MovieInOrder
from src.config.dependencies import (
    get_async_session,
    get_current_user,
    get_current_admin_or_moderator,
)

router = APIRouter()


@router.post(
    "/from-cart", response_model=OrderResponse, status_code=status.HTTP_201_CREATED
)
async def create_order_from_cart(
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    cart_result = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cart_result.scalar_one_or_none()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    movie_ids = [item.movie_id for item in cart.items]

    purchased_result = await db.execute(
        select(OrderItem.movie_id)
        .join(Order)
        .where(Order.user_id == current_user.id, OrderItem.movie_id.in_(movie_ids))
    )
    already_purchased = {row[0] for row in purchased_result.all()}
    available_ids = [mid for mid in movie_ids if mid not in already_purchased]

    if not available_ids:
        raise HTTPException(status_code=400, detail="All movies already purchased")

    movies_result = await db.execute(select(Movie).where(Movie.id.in_(available_ids)))
    movies = movies_result.scalars().all()

    total_amount = sum(movie.price for movie in movies)
    new_order = Order(
        user_id=current_user.id,
        created_at=datetime.utcnow(),
        total_amount=total_amount,
        status=OrderStatusEnum.paid,
    )
    db.add(new_order)
    await db.flush()

    for movie in movies:
        db.add(OrderItem(order_id=new_order.id, movie_id=movie.id, price_at_order=movie.price))

    for item in cart.items:
        db.delete(item)

    await db.commit()

    return OrderResponse(
        id=new_order.id,
        created_at=new_order.created_at,
        status=new_order.status,
        total_price=new_order.total_amount,
        movies=[MovieInOrder(id=m.id, name=m.name, price=m.price) for m in movies],
    )


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    movie_ids: List[int] = Body(..., embed=True),
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    if not movie_ids:
        raise HTTPException(status_code=400, detail="No movies selected.")

    purchased_result = await db.execute(
        select(OrderItem.movie_id).join(Order).where(Order.user_id == current_user.id)
    )
    already_purchased = set(purchased_result.scalars().all())

    filtered_ids = [mid for mid in movie_ids if mid not in already_purchased]
    if not filtered_ids:
        raise HTTPException(status_code=400, detail="All movies already purchased.")

    movies_result = await db.execute(select(Movie).where(Movie.id.in_(filtered_ids)))
    movies = movies_result.scalars().all()
    if not movies:
        raise HTTPException(status_code=404, detail="No available movies found.")

    total_amount = sum(m.price for m in movies)
    new_order = Order(
        user_id=current_user.id,
        created_at=datetime.utcnow(),
        total_amount=total_amount,
        status=OrderStatusEnum.pending,
    )
    db.add(new_order)
    await db.flush()
    await db.refresh(new_order)

    for movie in movies:
        db.add(
            OrderItem(
                order_id=new_order.id,
                movie_id=movie.id,
                price_at_order=movie.price,
            )
        )

    await db.commit()

    return OrderResponse(
        id=new_order.id,
        created_at=new_order.created_at,
        status=new_order.status,
        total_price=new_order.total_amount,
        movies=[MovieInOrder(id=m.id, name=m.name, price=m.price) for m in movies],
    )


@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.user_id == current_user.id))
    orders = result.scalars().all()

    response = []
    for order in orders:
        items_result = await db.execute(
            select(OrderItem, Movie)
            .join(Movie, OrderItem.movie_id == Movie.id)
            .where(OrderItem.order_id == order.id)
        )
        movies = [
            {"id": m.id, "name": m.name, "price": m.price} for _, m in items_result
        ]
        response.append(
            OrderResponse(
                id=order.id,
                created_at=order.created_at,
                status=order.status,
                total_price=order.total_price,
                movies=movies,
            )
        )
    return response


@router.delete("/{order_id}", status_code=204)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Cannot cancel paid/canceled order")

    order.status = "canceled"
    await db.commit()


@router.get("/admin", response_model=List[OrderResponse])
async def get_all_orders_admin(
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    _: dict = Depends(get_current_admin_or_moderator),
):
    query = select(Order)
    if user_id:
        query = query.where(Order.user_id == user_id)
    if status_filter:
        query = query.where(Order.status == status_filter)

    result = await db.execute(query)
    orders = result.scalars().all()

    response = []
    for order in orders:
        items_result = await db.execute(
            select(OrderItem, Movie)
            .join(Movie, OrderItem.movie_id == Movie.id)
            .where(OrderItem.order_id == order.id)
        )
        movies = [
            {"id": m.id, "name": m.name, "price": m.price} for _, m in items_result
        ]
        response.append(
            OrderResponse(
                id=order.id,
                created_at=order.created_at,
                status=order.status,
                total_price=order.total_price,
                movies=movies,
            )
        )
    return response
