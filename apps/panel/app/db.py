from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.config import settings


@lru_cache
def _conninfo() -> str:
    return settings.database_url


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(_conninfo(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(query: str, params: tuple | dict | None = None) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def fetch_all(query: str, params: tuple | dict | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())


def execute(query: str, params: tuple | dict | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)


def execute_returning(query: str, params: tuple | dict | None = None) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()
