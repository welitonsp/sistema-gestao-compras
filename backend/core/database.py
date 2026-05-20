"""Database infrastructure for the backend API.

This module configures the asynchronous SQLAlchemy engine, session factory,
and request-scoped dependency used by FastAPI handlers and services.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from backend.core.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=settings.database_pool_pre_ping,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    future=True,
)
"""Shared asynchronous SQLAlchemy engine for the application."""


SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)
"""Factory for creating short-lived async database sessions."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async database session.

    This dependency is intended for FastAPI path operations. The session is
    always closed after use, and an explicit rollback is issued if request
    processing raises an exception before commit.
    """

    session: AsyncSession = SessionLocal()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
