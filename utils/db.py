import os
import json
import psycopg2
import psycopg2.extras
from typing import Any, Iterable, List, Optional, Dict
from contextlib import contextmanager

# ===== Connection =====
DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ===== Low-level helpers =====

def execute(guild_id: int, sql: str, params: Iterable[Any] = ()) -> int:
    sql = _inject_guild(sql, guild_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        return cur.lastrowid if cur.lastrowid else 0

def executemany(guild_id: int, sql: str, seq_of_params) -> None:
    sql = _inject_guild(sql, guild_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.executemany(sql, seq_of_params)

def fetchone(guild_id: int, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
    sql = _inject_guild(sql, guild_id)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        return dict(row) if row else None

def fetchall(guild_id: int, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
    sql = _inject_guild(sql, guild_id)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]

def _inject_guild(sql: str, guild_id: int) -> str:
    """
    SQLite lama tidak punya guild_id di semua query.
    Di PostgreSQL, semua tabel punya guild_id.
    Helper ini tidak mengubah SQL — filter guild_id
    sudah harus ada di query masing-masing.
    """
    return sql

# ===== Aliases untuk kompatibilitas kode lama =====
def query_one(guild_id: int, sql: str, params: Iterable[Any] = ()):
    return fetchone(guild_id, sql, params)

def query_all(guild_id: int, sql: str, params: Iterable[Any] = ()):
    return fetchall(guild_id, sql, params)

# ===== Memory helpers =====

def save_memory(guild_id: int, user_id, mtype, value, meta=None):
    meta_json = json.dumps(meta or {})
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO memories (guild_id, user_id, type, value, meta, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (guild_id, user_id, mtype, value, meta_json)
        )

def get_recent(guild_id: int, mtype=None, limit=10):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if mtype:
            cur.execute(
                "SELECT * FROM memories WHERE guild_id=%s AND type=%s ORDER BY id DESC LIMIT %s",
                (guild_id, mtype, limit)
            )
        else:
            cur.execute(
                "SELECT * FROM memories WHERE guild_id=%s ORDER BY id DESC LIMIT %s",
                (guild_id, limit)
            )
        return [dict(r) for r in cur.fetchall()]

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

# ===== Schema bootstrap =====

def init_db(guild_id: int) -> None:
    """
    PostgreSQL: schema sudah dibuat via schema.sql di Supabase.
    Fungsi ini tetap ada untuk kompatibilitas — tidak perlu buat tabel lagi.
    """
    pass

def check_schema(guild_id: int) -> dict:
    """Cek tabel yang ada di PostgreSQL."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tables = [r[0] for r in cur.fetchall()]
        result = {}
        for t in tables:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
            """, (t,))
            result[t] = [r[0] for r in cur.fetchall()]
        return result

# ===== Placeholder untuk fungsi lama yang tidak relevan =====
def _ensure_table(guild_id: int, create_sql: str) -> None:
    pass

def _ensure_columns(guild_id: int, table: str, columns: Dict[str, str]) -> None:
    pass

def _exec_script(guild_id: int, sql: str) -> None:
    pass
