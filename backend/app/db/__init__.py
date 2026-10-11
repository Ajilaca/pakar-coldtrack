"""Akses TimescaleDB dengan psycopg v3 (tanpa ORM). DSN dari env DATABASE_URL."""

import os
from contextlib import contextmanager

DEFAULT_DSN = "postgresql://coldtrack:coldtrack@localhost:5432/coldtrack"   # nilai dev (docker-compose)
_pool = None


def dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


def pool():
    """Pool koneksi bersama (dibuat malas, hanya bila DB dipakai)."""
    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(dsn(), min_size=1, max_size=int(os.environ.get("DB_POOL_MAX", "8")), open=True)
    return _pool


@contextmanager
def conn():
    with pool().connection() as c:
        yield c
