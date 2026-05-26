"""Pytest configuration for backend test database setup."""

from __future__ import annotations

import asyncio

import pytest

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


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database() -> None:
    """Initialize the database schema used by integration tests."""

    asyncio.run(_create_test_schema())
    yield
    asyncio.run(_drop_test_schema())
