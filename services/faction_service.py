from utils.db import execute, fetchone, fetchall


def exists_faction(guild_id: int, name: str) -> bool:
    row = fetchone(
        guild_id,
        "SELECT 1 FROM factions WHERE guild_id=%s AND name=%s",
        (guild_id, name)
    )
    return row is not None


def add_faction(guild_id: int, name: str, desc: str = "", ftype: str = "general", hidden: int = 0):
    execute(
        guild_id,
        """
        INSERT INTO factions (guild_id, name, description, faction_type, hidden, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (guild_id, name) DO NOTHING
        """,
        (guild_id, name, desc, ftype, hidden)
    )
    return f"🏷️ Faction **{name}** ditambahkan (type: {ftype})."


def list_factions(guild_id: int, include_hidden=False):
    if include_hidden:
        return fetchall(guild_id, "SELECT * FROM factions WHERE guild_id=%s", (guild_id,))
    return fetchall(guild_id, "SELECT * FROM factions WHERE guild_id=%s AND hidden=0", (guild_id,))


def get_faction(guild_id: int, name: str):
    return fetchone(
        guild_id,
        "SELECT * FROM factions WHERE guild_id=%s AND name=%s",
        (guild_id, name)
    )


def remove_faction(guild_id: int, name: str):
    execute(guild_id, "DELETE FROM factions WHERE guild_id=%s AND name=%s", (guild_id, name))
    return f"🗑️ Faction **{name}** dihapus."


def hide_faction(guild_id: int, name: str, hidden: int = 1):
    execute(guild_id, "UPDATE factions SET hidden=%s WHERE guild_id=%s AND name=%s", (hidden, guild_id, name))
    return f"{'🙈' if hidden else '👁️'} Faction **{name}** {'disembunyikan' if hidden else 'ditampilkan'}."


def set_faction_type(guild_id: int, name: str, ftype: str):
    execute(guild_id, "UPDATE factions SET faction_type=%s WHERE guild_id=%s AND name=%s", (ftype, guild_id, name))
    return f"🏷️ Faction **{name}** type diubah ke `{ftype}`."
