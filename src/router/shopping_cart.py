from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.dependencies import get_async_session, get_current_user
from src.database.models.movies import Movie
from src.database.models.orders import OrderItem, Order
from src.database.models.shopping_cart import Cart, CartItem
from src.schemas.movies import MovieSchema

router = APIRouter()


@router.post("/add/{movie_id}")
async def add_to_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    purchased_result = await db.execute(
        select(OrderItem.movie_id)
        .join(Order)
        .where(Order.user_id == current_user.id, OrderItem.movie_id == movie_id)
    )
    if purchased_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Movie already purchased")

    result = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = result.scalar_one_or_none()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.flush()

    for item in cart.items:
        if item.movie_id == movie_id:
            raise HTTPException(status_code=400, detail="Movie already in cart")

    new_item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(new_item)
    await db.commit()
    return {"message": "Movie added to cart"}


@router.delete("/remove/{movie_id}")
async def remove_from_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(CartItem)
        .join(Cart)
        .where(Cart.user_id == current_user.id, CartItem.movie_id == movie_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=400, detail="Movie not in cart")

    await db.delete(item)
    await db.commit()
    return {"message": "Movie removed from cart"}


@router.get("/", response_model=list[MovieSchema])
async def get_cart(
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(CartItem).join(Cart).where(Cart.user_id == current_user.id)
    )
    items = result.scalars().all()
    movie_ids = [item.movie_id for item in items]

    movie_result = await db.execute(select(Movie).where(Movie.id.in_(movie_ids)))
    return movie_result.scalars().all()


@router.delete("/clear")
async def clear_cart(
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(CartItem).join(Cart).where(Cart.user_id == current_user.id)
    )
    items = result.scalars().all()

    for item in items:
        await db.delete(item)
    await db.commit()
    return {"message": "Cart cleared"}
