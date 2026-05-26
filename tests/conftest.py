"""Pytest configuration for backend test database setup."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

os.environ.update(
    {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "SECRET_KEY": "test_secret_key_institutional_standard",
        "DEBUG": "false",
        "AI_PROVIDER": "groq",
        "ENABLE_GEMINI": "false",
        "GROQ_API_KEY": "fake_key",
        "GEMINI_API_KEY": "",
        "REDIS_URL": "redis://localhost:6379/0",
    }
)

from backend.core.database import engine
from backend.models.base import Base

# Import ORM models so Base.metadata includes every mapped table before create_all.
import backend.models.compras  # noqa: F401,E402


async def _create_test_schema() -> None:
    """Create all ORM tables for the SQLite in-memory test database."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _drop_test_schema() -> None:
    """Drop all ORM tables after the test session finishes."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Force AnyIO tests to use asyncio only."""

    return "asyncio"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_test_database() -> None:
    """Initialize the database schema used by integration tests."""

    await _create_test_schema()
    yield
    await _drop_test_schema()
    await engine.dispose()
