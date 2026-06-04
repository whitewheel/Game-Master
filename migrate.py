"""
migrate.py — Migrasi data dari SQLite (Narator bot lama) ke Supabase PostgreSQL
Jalankan sekali: python migrate.py --guild_id YOUR_GUILD_ID --sqlite_path /path/to/narator_GUILD.db
"""

import os
import sys
import json
import sqlite3
import psycopg2
import psycopg2.extras
import argparse
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

TABLES = [
    "characters", "enemies", "allies", "companions",
    "quests", "npc", "npc_shop", "factions", "favors",
    "items", "inventory", "skill_library", "skills",
    "effects", "blueprints", "crafting", "known_blueprints",
    "hollow_nodes", "hollow_log", "hollow_visitors", "hollow_events",
    "history", "timeline", "initiative", "memories"
]

# Kolom yang perlu di-parse dari JSON string ke JSONB
JSON_COLUMNS = {
    "characters": ["buffs", "debuffs", "effects", "equipment", "companions", "inventory"],
    "enemies": ["effects", "loot"],
    "allies": ["effects"],
    "companions": ["effects", "modules"],
    "quests": ["assigned_to", "rewards", "favor", "tags"],
    "npc": ["traits", "info"],
    "npc_shop": ["favor_req", "quest_req"],
    "items": [],
    "inventory": ["metadata"],
    "effects": [],
    "hollow_nodes": ["traits", "types", "npcs", "visitors", "events", "vendors_today", "event_today", "visitors_today"],
    "hollow_log": ["vendors", "visitors"],
    "history": ["data"],
    "memories": ["meta"],
    "initiative": ["order_json"],
    "blueprints": ["req"],
}

def parse_json_safe(val, fallback="{}"):
    if val is None:
        return fallback
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    try:
        parsed = json.loads(val)
        return json.dumps(parsed)
    except Exception:
        return fallback

def migrate(guild_id: int, sqlite_path: str):
    print(f"🚀 Mulai migrasi guild {guild_id} dari {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(DATABASE_URL)
    pg_cur = pg_conn.cursor()

    for table in TABLES:
        try:
            cur = sqlite_conn.execute(f"SELECT * FROM {table}")
            rows = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            print(f"⚠️  Tabel {table} tidak ada di SQLite, skip. ({e})")
            continue

        if not rows:
            print(f"📭 {table}: kosong, skip.")
            continue

        json_cols = JSON_COLUMNS.get(table, [])
        migrated = 0

        for row in rows:
            row["guild_id"] = guild_id

            # Parse JSON columns
            for col in json_cols:
                if col in row:
                    fallback = "[]" if col in ["buffs", "debuffs", "effects", "companions", "inventory", "loot", "assigned_to", "traits", "types", "npcs", "visitors", "events", "vendors_today", "visitors_today", "order_json"] else "{}"
                    row[col] = parse_json_safe(row.get(col), fallback)

            # Hapus kolom id agar auto-increment PostgreSQL yang handle
            row.pop("id", None)

            cols = list(row.keys())
            placeholders = ["%s"] * len(cols)
            values = [row[c] for c in cols]

            sql = f"""
                INSERT INTO {table} ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT DO NOTHING
            """
            try:
                pg_cur.execute(sql, values)
                migrated += 1
            except Exception as e:
                print(f"  ❌ Row gagal di {table}: {e}")
                pg_conn.rollback()
                continue

        pg_conn.commit()
        print(f"  ✅ {table}: {migrated}/{len(rows)} rows berhasil dimigrasi")

    pg_cur.close()
    pg_conn.close()
    sqlite_conn.close()
    print("\n🎉 Migrasi selesai!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrasi Narator SQLite → Supabase")
    parser.add_argument("--guild_id", type=int, required=True, help="Discord Guild ID")
    parser.add_argument("--sqlite_path", type=str, required=True, help="Path ke file SQLite lama")
    args = parser.parse_args()
    migrate(args.guild_id, args.sqlite_path)
