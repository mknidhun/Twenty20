"""Database engine + session (PostgreSQL via SQLModel / SQLAlchemy async).

Set DATABASE_URL in backend/.env, e.g.:
  postgresql+asyncpg://twenty20:twenty20@localhost:5432/twenty20_wariyad
For quick local dev you may instead use SQLite:
  sqlite+aiosqlite:///./twenty20.db
The application code is identical for both.
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://twenty20:twenty20@localhost:5432/twenty20_wariyad",
)

# echo can be toggled with SQL_ECHO=true for debugging
engine = create_async_engine(DATABASE_URL, echo=os.environ.get("SQL_ECHO") == "true", future=True)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async DB session per request."""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Create all tables if they don't exist (dev convenience; use Alembic in prod)."""
    import models  # noqa: F401  (ensures models are registered on SQLModel.metadata)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
