"""SQLAlchemy models."""
import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String(512), nullable=False)
    author = Column(String(512), default="")
    filename = Column(String(512), nullable=False)  # stored file name
    num_pages = Column(Integer, default=0)
    status = Column(String(32), default="uploaded")  # uploaded|processing|ready|error
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan",
                            order_by="Chapter.start_page")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    number = Column(Integer, nullable=True)  # chapter number if detected
    title = Column(String(512), nullable=False)
    start_page = Column(Integer, nullable=False)  # 0-indexed
    end_page = Column(Integer, nullable=False)  # inclusive
    source = Column(String(32), default="toc")  # toc|regex|llm|manual
    summary = Column(Text, default="")  # detailed summary
    tldr = Column(Text, default="")  # 2-sentence TL;DR
    summarized = Column(Integer, default=0)

    book = relationship("Book", back_populates="chapters")


class ReadingProgress(Base):
    __tablename__ = "reading_progress"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), unique=True, nullable=False)
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
