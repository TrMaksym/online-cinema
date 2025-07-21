from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from src.config.dependencies import get_async_session
from src.database.models.movies import Movie, Genre, Star, Director
from src.schemas.movies import MovieSchema, MovieCreateSchema, RatingCreateSchema

router = APIRouter()

user_favorites = {}

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

@router.delete("/{movie_id}")
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    await db.delete(movie)
    await db.commit()
    return {"message": "Movie deleted"}


@router.post("/{movie_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def add_to_favorites(movie_id: int, user_id: int = 1):
    if user_id not in user_favorites:
        user_favorites[user_id] = set()
    user_favorites[user_id].add(movie_id)
    return

@router.delete("/{movie_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_favorites(movie_id: int, user_id: int = 1):
    if user_id in user_favorites:
        user_favorites[user_id].discard(movie_id)
    return

@router.get("/favorites", response_model=List[MovieSchema])
async def list_favorites(
    user_id: int = 1,
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None
):
    if user_id not in user_favorites or not user_favorites[user_id]:
        return []

    fav_ids = list(user_favorites[user_id])
    query = select(Movie).where(Movie.id.in_(fav_ids)).options(joinedload(Movie.genres), joinedload(Movie.directors), joinedload(Movie.stars))

    if search:
        search_str = f"%{search.lower()}%"
        query = query.where(
            (Movie.name.ilike(search_str)) |
            (Movie.description.ilike(search_str)) |
            (Movie.stars.any(Star.name.ilike(search_str))) |
            (Movie.directors.any(Director.name.ilike(search_str)))
        )
    if sort_by:
        sort_col = getattr(Movie, sort_by)
        if order == "desc":
            sort_col = sort_col.desc()
        query = query.order_by(sort_col)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

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

from fastapi import status

@router.post("/{movie_id}/like", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def like_movie(movie_id: int):
    return {"detail": "Not implemented: liking movies"}

@router.post("/{movie_id}/dislike", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def dislike_movie(movie_id: int):
    return {"detail": "Not implemented: disliking movies"}

@router.post("/{movie_id}/rate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def rate_movie(movie_id: int, rating: int):
    return {"detail": "Not implemented: rating movies"}

@router.post("/{movie_id}/comments", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def write_comment(movie_id: int, comment: str):
    return {"detail": "Not implemented: writing comments"}

@router.get("/{movie_id}/comments", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_comments(movie_id: int):
    return {"detail": "Not implemented: getting comments"}
