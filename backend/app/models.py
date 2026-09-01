"""Multi-user data models: users, shelves, books per user, reading progress."""
import datetime

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint, create_engine)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), default="")  # empty for google-only users
    name = Column(String(200), default="")
    google_sub = Column(String(64), unique=True, nullable=True)  # google account id
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    author = Column(String(512), default="")
    filename = Column(String(512), nullable=False)  # storage key
    num_pages = Column(Integer, default=0)
    status = Column(String(32), default="uploaded")  # uploaded|processing|ready|error
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan",
                            order_by="Chapter.start_page")


class Shelf(Base):
    __tablename__ = "shelves"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    items = relationship("ShelfBook", back_populates="shelf", cascade="all, delete-orphan")


class ShelfBook(Base):
    __tablename__ = "shelf_books"
    __table_args__ = (UniqueConstraint("shelf_id", "book_id", name="uq_shelf_book"),)

    id = Column(Integer, primary_key=True)
    shelf_id = Column(Integer, ForeignKey("shelves.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)

    shelf = relationship("Shelf", back_populates="items")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    number = Column(Integer, nullable=True)
    title = Column(String(512), nullable=False)
    start_page = Column(Integer, nullable=False)
    end_page = Column(Integer, nullable=False)
    source = Column(String(32), default="toc")  # toc|regex|llm|manual
    summary = Column(Text, default="")
    tldr = Column(Text, default="")
    summarized = Column(Integer, default=0)

    book = relationship("Book", back_populates="chapters")


class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book_progress"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    last_page = Column(Integer, default=0)
    percent = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
