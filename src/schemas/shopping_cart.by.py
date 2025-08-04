from datetime import datetime
from pydantic import BaseModel


class UsersSchema(BaseModel):
    id: int

    class Config:
        orm_mode = True


class CartsSchema(BaseModel):
    id: int
    user_id: int

    class Config:
        orm_mode = True


class CartsItemsSchema(BaseModel):
    id: int
    cart_id: int
    movie_id: int
    added_at: datetime

    class Config:
        orm_mode = True


class MoviesSchema(BaseModel):
    id: int

    class Config:
        orm_mode = True
