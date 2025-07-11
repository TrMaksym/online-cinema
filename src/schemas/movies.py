from typing import Optional, List

from pydantic.v1 import BaseModel, constr, condecimal
import uuid

from database.models.movies import Star, Genre, Director


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

    stars: Optional[List[Star]] = []
    genres: Optional[List[Genre]] = []
    directors: Optional[List[Director]] = []


class CertificationsSchema(BaseModel):
    id: int
    name: constr(max_length=50)


class MovieStarSchema(BaseModel):
    movie_id: int
    star_id: int


class MovieGenreSchema(BaseModel):
    movie_id: int
    genre_id: int


class MovieDirectorSchema(BaseModel):
    movie_id: int
    director_id: int


class Genre(BaseModel):
    id: int
    name: constr(max_length=100)


class Star(BaseModel):
    id: int
    name: constr(max_length=100)


class Director(BaseModel):
    id: int
    name: constr(max_length=100)
