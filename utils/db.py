import os
import json
from typing import Any, Iterable, List, Optional, Dict
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_conn():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute(guild_id: int, sql: str, params: Iterable[Any] = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.rownumber or 0

def executemany(guild_id: int, sql: str, seq_of_params) -> None:
    with get_conn() as conn:
        conn.executemany(sql, seq_of_params)

def fetchone(guild_id: int, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()

def fetchall(guild_id: int, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()

def query_one(guild_id: int, sql: str, params: Iterable[Any] = ()):
    return fetchone(guild_id, sql, params)

def query_all(guild_id: int, sql: str, params: Iterable[Any] = ()):
    return fetchall(guild_id, sql, params)

def save_memory(guild_id: int, user_id, mtype, value, meta=None):
    meta_json = json.dumps(meta or {})
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memories (guild_id, user_id, type, value, meta, created_at) VALUES (%s,%s,%s,%s,%s,NOW())",
            (guild_id, user_id, mtype, value, meta_json)
        )

def get_recent(guild_id: int, mtype=None, limit=10):
    if mtype:
        return fetchall(guild_id,
            "SELECT * FROM memories WHERE guild_id=%s AND type=%s ORDER BY id DESC LIMIT %s",
            (guild_id, mtype, limit))
    return fetchall(guild_id,
        "SELECT * FROM memories WHERE guild_id=%s ORDER BY id DESC LIMIT %s",
        (guild_id, limit))

def template_for(mtype: str) -> dict:
    templates = {
        "character": {"name": "", "level": 1, "hp": 0},
        "quest": {"name": "", "status": "active"},
        "item": {"name": "", "desc": ""},
        "favor": {"faction": "", "points": 0},
        "enemy": {"name": "", "hp": 0, "xp_reward": 0},
        "ally": {"name": "", "hp": 0}
    }
    return templates.get(mtype, {})

def init_db(guild_id: int) -> None:
    pass

def check_schema(guild_id: int) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
        tables = [r["table_name"] for r in cur.fetchall()]
        result = {}
        for t in tables:
            cur2 = conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s AND table_schema='public'",
                (t,)
            )
            result[t] = [r["column_name"] for r in cur2.fetchall()]
        return result

def _ensure_table(guild_id: int, create_sql: str) -> None:
    pass

def _ensure_columns(guild_id: int, table: str, columns: Dict[str, str]) -> None:
    pass

def _exec_script(guild_id: int, sql: str) -> None:
    pass
