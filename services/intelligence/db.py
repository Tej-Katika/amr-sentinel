"""TimescaleDB connection helpers."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

DEFAULT_URL = "postgresql://amrsentinel:amrsentinel_dev@localhost:5432/amrsentinel"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_URL)


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(database_url())
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(commit: bool = False) -> Iterator[RealDictCursor]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
