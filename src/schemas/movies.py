from typing import Optional, List

from pydantic import BaseModel, constr, condecimal, conint
import uuid


class MovieSchema(BaseModel):
    id: int
    uuid: uuid.UUID
    name: constr(max_length=250)
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float
    gross: float
    description: constr(max_length=255)
    price: condecimal(max_digits=10, decimal_places=2)
    certification_id: int

    class Config:
        orm_mode = True


class MovieCreateSchema(BaseModel):
    name: constr(max_length=250)
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: constr(max_length=255)
    price: condecimal(max_digits=10, decimal_places=2)
    certification_id: int
    genres: Optional[List[int]] = []
    directors: Optional[List[int]] = []
    stars: Optional[List[int]] = []

    class Config:
        orm_mode = True


class CertificationsSchema(BaseModel):
    id: int
    name: constr(max_length=50)

    class Config:
        orm_mode = True


class MovieStarSchema(BaseModel):
    movie_id: int
    star_id: int

    class Config:
        orm_mode = True


class MovieGenreSchema(BaseModel):
    movie_id: int
    genre_id: int

    class Config:
        orm_mode = True


class MovieDirectorSchema(BaseModel):
    movie_id: int
    director_id: int

    class Config:
        orm_mode = True


class Genre(BaseModel):
    id: int
    name: constr(max_length=100)

    class Config:
        orm_mode = True


class Star(BaseModel):
    id: int
    name: constr(max_length=100)

    class Config:
        orm_mode = True


class Director(BaseModel):
    id: int
    name: constr(max_length=100)

    class Config:
        orm_mode = True


class RatingCreateSchema(BaseModel):
    rating: conint(ge=1, le=10)
    user_id: int
    movie_id: int


class LikeDislikeCreateSchema(BaseModel):
    user_id: int
    movie_id: int
    like: bool


class LikeDislikeResponseSchema(BaseModel):
    movie_id: int
    user_id: int
    like: bool

    class Config:
        orm_mode = True


class CommentCreateSchema(BaseModel):
    user_id: int
    movie_id: int
    parent_comment_id: Optional[int] = None
    text: constr(min_length=1)


class CommentSchema(BaseModel):
    id: int
    user_id: int
    movie_id: int
    parent_comment_id: Optional[int]
    text: str
    replies: Optional[List["CommentSchema"]] = []

    class Config:
        orm_mode = True


class FavoriteCreateSchema(BaseModel):
    user_id: int
    movie_id: int


class FavoriteResponseSchema(BaseModel):
    id: int
    user_id: int
    movie_id: int

    class Config:
        orm_mode = True
