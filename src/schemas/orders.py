from datetime import datetime
from typing import List
from pydantic import BaseModel

class MovieInOrder(BaseModel):
    id: int
    name: str
    price: float

class OrderResponse(BaseModel):
    id: int
    created_at: datetime
    total_price: float
    status: str
    movies: List[MovieInOrder]

class OrderCreateRequest(BaseModel):
    movie_ids: List[int]
