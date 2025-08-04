from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    UUID,
    Float,
    DECIMAL,
    ForeignKey,
    Table,
    Text,
    DateTime,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped
import uuid

from sqlalchemy.testing.schema import mapped_column

from .base import Base

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id"), primary_key=True),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("director_id", ForeignKey("directors.id"), primary_key=True),
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("star_id", ForeignKey("stars.id"), primary_key=True),
)


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_genres = relationship("Movie", back_populates="genre")


class Star(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_start = relationship("Movie", back_populates="star")


class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_directors = relationship("Movie", back_populates="director")


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_certifications = relationship("Movie", back_populates="certification")


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description = Column(String(255), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    certification_id = Column(Integer, ForeignKey("certifications.id"), nullable=False)

    certification = relationship("Certification", backref="movies")
    genres = relationship("Genre", secondary=movie_genres, backref="movies")
    directors = relationship("Director", secondary=movie_directors, backref="movies")
    stars = relationship("Star", secondary=movie_stars, backref="movies")
    favorited_by = relationship(
        "Favorite", back_populates="movie", cascade="all, delete"
    )
    purchases = relationship("Purchase", back_populates="movie", cascade="all, delete")


class MovieRating(Base):
    __tablename__ = "movie_ratings"
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("movie_id", "user_id", name="_user_movie_rating_uc"),
    )


class MovieLikeDislike(Base):
    __tablename__ = "movie_likes_dislikes"
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, nullable=False)
    is_like = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("movie_id", "user_id", name="_user_movie_like_uc"),
    )


class MovieComment(Base):
    __tablename__ = "movie_comments"
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, nullable=False)
    parent_id = Column(
        Integer, ForeignKey("movie_comments.id", ondelete="CASCADE"), nullable=True
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    replies = relationship("MovieComment", backref="parent", remote_side=[id])


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"))

    user = relationship("User", back_populates="favorites")
    movie = relationship("Movie", back_populates="favorited_by")

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="unique_favorite"),)


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())

    movie = relationship("Movie", back_populates="purchases")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)

    replies = relationship("Comment", backref="parent", remote_side=[id])
