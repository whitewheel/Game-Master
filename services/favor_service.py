import json
from utils.db import execute, fetchone, fetchall
from cogs.world.timeline import log_event
from services import faction_service

ICONS = {
    "favor": "💠",
    "add": "➕",
    "set": "⚖️",
    "remove": "🗑️",
}


def favor_status(value: int) -> str:
    if value <= -10:
        return "Hostile 😡"
    elif value < 0:
        return "Unfriendly 😒"
    elif value < 5:
        return "Neutral 😐"
    elif value < 10:
        return "Friendly 🙂"
    else:
        return "Allied 🤝"


async def add_or_set_favor(guild_id: int, char_name: str, faction: str, value: int, notes: str = ""):
    if not faction_service.exists_faction(guild_id, faction):
        faction_service.add_faction(guild_id, faction, desc="(auto-generated)", ftype="general")

    execute(
        guild_id,
        """
        INSERT INTO favors (guild_id, char_name, faction, favor, notes, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (guild_id, char_name, faction)
        DO UPDATE SET favor=EXCLUDED.favor,
                      notes=EXCLUDED.notes,
                      updated_at=NOW()
        """,
        (guild_id, char_name, faction, value, notes)
    )
    log_event(
        guild_id, char_name,
        code=f"FAVOR_SET_{faction.upper()}",
        title=f"{ICONS['favor']} Favor {char_name}:{faction} → {value}",
        details=notes,
        etype="favor_set",
        actors=[char_name, faction],
        tags=["favor", "set"]
    )
    return f"{ICONS['favor']} Favor {faction} untuk **{char_name}** di-set ke `{value}`."


async def mod_favor(guild_id: int, char_name: str, faction: str, delta: int, notes: str = ""):
    if not faction_service.exists_faction(guild_id, faction):
        faction_service.add_faction(guild_id, faction, desc="(auto-generated)", ftype="general")

    row = fetchone(guild_id,
                   "SELECT favor FROM favors WHERE guild_id=%s AND char_name=%s AND faction=%s",
                   (guild_id, char_name, faction))
    current = row["favor"] if row else 0
    new_value = current + delta

    execute(
        guild_id,
        """
        INSERT INTO favors (guild_id, char_name, faction, favor, notes, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (guild_id, char_name, faction)
        DO UPDATE SET favor=%s,
                      notes=EXCLUDED.notes,
                      updated_at=NOW()
        """,
        (guild_id, char_name, faction, new_value, notes, new_value)
    )
    return f"{ICONS['favor']} Favor {faction} untuk **{char_name}** berubah {delta:+d} → `{new_value}`."


async def remove_favor(guild_id: int, char_name: str, faction: str):
    execute(guild_id, "DELETE FROM favors WHERE guild_id=%s AND char_name=%s AND faction=%s",
            (guild_id, char_name, faction))
    return f"{ICONS['remove']} Favor {faction} untuk **{char_name}** dihapus."


async def list_favors(guild_id: int, char_name: str = None):
    if char_name:
        return fetchall(guild_id, "SELECT * FROM favors WHERE guild_id=%s AND char_name=%s",
                        (guild_id, char_name))
    return fetchall(guild_id, "SELECT * FROM favors WHERE guild_id=%s", (guild_id,))


async def get_detail(guild_id: int, faction: str, char_name: str = None):
    if char_name:
        return fetchone(guild_id, "SELECT * FROM favors WHERE guild_id=%s AND char_name=%s AND faction=%s",
                        (guild_id, char_name, faction))
    return fetchall(guild_id, "SELECT * FROM favors WHERE guild_id=%s AND faction=%s", (guild_id, faction))


async def list_all_favors(guild_id: int):
    return fetchall(guild_id, "SELECT * FROM favors WHERE guild_id=%s", (guild_id,))


async def list_factions_status(guild_id: int, char_name: str, factions: list):
    out = []
    for fac in factions:
        row = fetchone(guild_id, "SELECT favor FROM favors WHERE guild_id=%s AND char_name=%s AND faction=%s",
                       (guild_id, char_name, fac))
        val = row["favor"] if row else 0
        status = favor_status(val)
        out.append((fac, val, status))
    return out


async def add_favor(guild_id: int, targets: list, faction: str, value: int):
    if not faction_service.exists_faction(guild_id, faction):
        faction_service.add_faction(guild_id, faction, desc="(auto-generated)", ftype="general")

    result = []
    for ch in targets:
        row = fetchone(guild_id, "SELECT favor FROM favors WHERE guild_id=%s AND char_name=%s AND faction=%s",
                       (guild_id, ch, faction))
        current = row["favor"] if row else 0
        new_value = current + value

        execute(
            guild_id,
            """
            INSERT INTO favors (guild_id, char_name, faction, favor, notes, updated_at)
            VALUES (%s, %s, %s, %s, 'Quest reward', NOW())
            ON CONFLICT (guild_id, char_name, faction)
            DO UPDATE SET favor=%s, updated_at=NOW()
            """,
            (guild_id, ch, faction, new_value, new_value)
        )
        result.append(f"{ch}: {new_value}")

    return f"{ICONS['favor']} Favor {faction} ditambahkan → " + ", ".join(result)
