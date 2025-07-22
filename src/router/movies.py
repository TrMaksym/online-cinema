from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.operators import or_

from src.config.dependencies import get_async_session
from src.database.models.movies import Movie, Genre, Star, Director, Favorite, Purchase, Comment
from src.database.models.nofitications import Notification
from src.schemas.movies import MovieSchema, MovieCreateSchema, RatingCreateSchema, FavoriteResponseSchema, \
    FavoriteCreateSchema, CommentSchema, CommentCreateSchema

router = APIRouter()
comment_router = APIRouter()

user_favorites = {}

fake_likes_storage = {}

fake_ratings_storage = {}

fake_favorites_storage = {}



async def get_genres_by_ids(genre_ids: list[int], db: AsyncSession):
    result = await db.execute(select(Genre).where(Genre.id.in_(genre_ids)))
    return result.scalars().all()

async def get_directors_by_ids(director_ids: list[int], db: AsyncSession):
    result = await db.execute(select(Director).where(Director.id.in_(director_ids)))
    return result.scalars().all()

async def get_stars_by_ids(star_ids: list[int], db: AsyncSession):
    result = await db.execute(select(Star).where(Star.id.in_(star_ids)))
    return result.scalars().all()


@router.post("/", response_model=MovieSchema)
async def create_movie(data: MovieCreateSchema, db: AsyncSession = Depends(get_async_session)):
    movie = Movie(
        name=data.name,
        year=data.year,
        time=data.time,
        imdb=data.imdb,
        votes=data.votes,
        meta_score=data.meta_score,
        gross=data.gross,
        description=data.description,
        price=data.price,
        certification_id=data.certification_id
    )

    if data.genres:
        movie.genres = await get_genres_by_ids(data.genres, db)
    if data.directors:
        movie.directors = await get_directors_by_ids(data.directors, db)
    if data.stars:
        movie.stars = await get_stars_by_ids(data.stars, db)

    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    return movie


@router.get("/", response_model=List[MovieSchema])
async def get_movies(
    search: str,
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    year: Optional[int] = None,
    imdb_min: Optional[float] = None,
    genre_id: Optional[int] = None,
    sort_by: Optional[str] = Query(None, regex="^(price|year|imdb|votes)$"),
    order: Optional[str] = Query("asc", regex="^(asc|desc)$")
):
    query = select(Movie).options(joinedload(Movie.genres)).options(joinedload(Movie.directors)).options(joinedload(Movie.stars))

    if search:
        query = query.where(or_(
            Movie.name.ilike(f"%{search}%"),
            Movie.description.ilike(f"%{search}%"),
            Director.name.ilike(f"%{search}%"),
            Star.name.ilike(f"%{search}%"),
        ))
    if year:
        query = query.where(Movie.year == year)
    if imdb_min:
        query = query.where(Movie.imdb >= imdb_min)
    if genre_id:
        query = query.where(Movie.genres.any(Genre.id == genre_id))

    if sort_by:
        sort_by_column = getattr(Movie, sort_by)
        if order == "desc":
            sort_by_column = sort_by_column.desc()
        query = query.order_by(sort_by_column)

    query = query.offset(skip).limit(limit)
    movies = (await db.execute(query))
    return movies.scalars().all()

@router.get("/{movie_id}", response_model=MovieSchema)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(
        select(Movie).options(joinedload(Movie.genres), joinedload(Movie.directors), joinedload(Movie.stars))
        .where(Movie.id == movie_id)
    )
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie

@router.put("/{movie_id}", response_model=MovieSchema)
async def update_movie(movie_id: int, data: MovieCreateSchema, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(movie, key, value)

@router.delete("/{movie_id}")
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    purchase = await db.execute(select(Purchase).where(Purchase.movie_id == movie_id))
    if purchase.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cannot delete: movie purchased")

    await db.delete(movie)
    await db.commit()
    return {"message": "Movie deleted"}


@router.post("/favorites", response_model=FavoriteResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_to_favorites(favorite_data: FavoriteCreateSchema, db: AsyncSession = Depends(get_async_session)):
    existing = await db.execute(
        select(Favorite).where(
            Favorite.user_id == favorite_data.user_id,
            Favorite.movie_id == favorite_data.movie_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already in favorites")

    favorite = Favorite(user_id=favorite_data.user_id, movie_id=favorite_data.movie_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite


@router.delete("/{movie_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_favorites(
    movie_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.movie_id == movie_id)
    )
    favorite = result.scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    await db.delete(favorite)
    await db.commit()


@router.get("/favorites", response_model=List[MovieSchema])
async def list_favorites(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    fav_query = select(Favorite.movie_id).where(Favorite.user_id == user_id)
    result = await db.execute(fav_query)
    fav_ids = [id for (id,) in result.all()]
    if not fav_ids:
        return []

    query = (
        select(Movie)
        .where(Movie.id.in_(fav_ids))
        .options(joinedload(Movie.genres), joinedload(Movie.directors), joinedload(Movie.stars))
        .offset(skip)
        .limit(limit)
    )
    movies_result = await db.execute(query)
    return movies_result.scalars().all()

@router.get("/genres", response_model=List[dict])
async def list_genres_with_count(db: AsyncSession = Depends(get_async_session)):
    query = (
        select(Genre.id, Genre.name, func.count(Movie.id).label("movie_count"))
        .join(Genre.movies)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    result = await db.execute(query)
    genres = [{"id": gid, "name": gname, "movie_count": count} for gid, gname, count in result.all()]
    return genres


@router.get("/genres/{genre_id}/movies", response_model=List[MovieSchema])
async def movies_by_genre(genre_id: int, db: AsyncSession = Depends(get_async_session)):
    query = (
        select(Movie)
        .join(Movie.genres)
        .where(Genre.id == genre_id)
        .options(joinedload(Movie.genres), joinedload(Movie.directors), joinedload(Movie.stars))
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/{movie_id}/like", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def like_movie(movie_id: int, user_id: int):
    key = f"{user_id}:{movie_id}"
    fake_likes_storage[key] = True
    return {"message": f"User {user_id} liked movie {movie_id}"}

@router.post("/{movie_id}/dislike", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def dislike_movie(movie_id: int, user_id: int):
    key = f"{user_id}:{movie_id}"
    fake_likes_storage[key] = False
    return {"message": f"User {user_id} disliked movie {movie_id}"}

@router.post("/{movie_id}/rate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def rate_movie(movie_id: int, rating: RatingCreateSchema):
    key = f"{rating.user_id}:{movie_id}"
    fake_ratings_storage[key] = rating.rating
    return {"message": f"User {rating.user_id} rated movie {movie_id} with rating {rating.rating}"}

@router.post("/{movie_id}/favorite")
async def favorite_movie(movie_id: int, user_id: int = 1):
    if user_id not in user_favorites:
        fake_favorites_storage[user_id] = set()
    fake_favorites_storage[user_id].add(movie_id)
    return {"message": f"User {user_id} added movie {movie_id} to favorites"}

@router.delete("/{movie_id}/favorite")
async def unfavorite_movie(movie_id: int, user_id: int = 1):
    if user_id in fake_favorites_storage:
        fake_favorites_storage[user_id].discard(movie_id)
    return {"message": f"User {user_id} removed movie {movie_id} from favorites"}

@router.get("/genres/", response_model=list[dict])
async def get_genres_with_movie_count(db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Genre.id, Genre.name, func.count(Movie.id).join(Movie.genres).group_by(Genre.id)))
    data = [{"id": g[0], "name": g[1], "movie_count": g[2]} for g in result.all()]
    return data

@comment_router.post("/", response_model=CommentSchema, status_code=status.HTTP_201_CREATED)
async def create_comment(
        data: CommentCreateSchema,
        db: AsyncSession = Depends(get_async_session)
):
    comment = Comment(**data.dict())
    db.add(comment)
    if data.parent_id:
        parent_result = await db.execute(select(Comment).where(Comment.id == data.parent_id))
        parent_comment = parent_result.scalar_one_or_none()
        if parent_comment:
            notification = Notification(
                user_id=parent_comment.user_id,
                comment_id=comment.id,
                text=f"Your comment was replied to by {comment.user_id}"
            )
            db.add(notification)

    await db.commit()
    await db.refresh(comment)
    return comment

@comment_router.get("/{comment_id}", response_model=CommentSchema)
async def get_comments(movie_id: int, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Comment).where(Comment.movie_id == movie_id).order_by(Comment.created_at.desc()))
    return result.scalars().all()

@comment_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: int, db: AsyncSession = Depends(get_async_session)):
    result =  await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.delete(comment)
    await db.commit()
    return {"message": "Comment deleted"}
