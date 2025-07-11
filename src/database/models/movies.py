from typing import Optional

from sqlalchemy import Column, Integer, String, UUID, Float, DECIMAL, ForeignKey, Table
from sqlalchemy.orm import relationship, Mapped
import uuid

from sqlalchemy.testing.schema import mapped_column

from database.models.base import Base


movie_genres = Table(
        "movie_genres",
        Base.metadata,
        Column("movie_id", ForeignKey("movies.id"), primary_key=True),
        Column("genre_id", ForeignKey("genres.id"), primary_key=True)
    )

    movie_directors = Table(
        "movie_directors",
        Base.metadata,
        Column("movie_id", ForeignKey("movies.id"), primary_key=True),
        Column("director_id", ForeignKey("directors.id"), primary_key=True)
    )

    movie_stars = Table(
        "movie_stars",
        Base.metadata,
        Column("movie_id", ForeignKey("movies.id"), primary_key=True),
        Column("star_id", ForeignKey("stars.id"), primary_key=True)
    )


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_genres = relationship("Movie", black_populates="genre")


class Star(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_start = relationship("Movie", black_populates="star")


class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_directors = relationship("Movie", black_populates="director")


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    movie_certifications = relationship("Movie", black_populates="certification")


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description = Column(String(255), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False )
    certification_id = Column(Integer, ForeignKey("certifications.id"), nullable=False)


    certification = relationship("Certification", backref="movies")
    genres = relationship("Genre", secondary=movie_genres, backref="movies")
    directors = relationship("Director", secondary=movie_directors, backref="movies")
    stars = relationship("Star", secondary=movie_stars, backref="movies")
