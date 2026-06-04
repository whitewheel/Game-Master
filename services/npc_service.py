import json
from utils.db import execute, fetchone, fetchall
from cogs.world.timeline import log_event

ICONS = {
    "npc": "🧑‍🤝‍🧑",
    "hidden": "👁️",
    "lore": "📚",
    "remove": "🗑️",
}


def get_npc(guild_id: int, name: str):
    return fetchone(guild_id, "SELECT * FROM npc WHERE guild_id=%s AND name=%s", (guild_id, name))


async def add_npc(guild_id: int, user_id, name, role="", traits=None):
    exists = get_npc(guild_id, name)
    if exists:
        return f"⚠️ NPC **{name}** sudah ada."

    traits = traits or {}
    traits = {k: {"value": v, "visible": False} for k, v in traits.items()}

    execute(
        guild_id,
        "INSERT INTO npc (guild_id, name, role, traits, info, status, affiliation) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (guild_id, name, role, json.dumps(traits), json.dumps({"value": "", "visible": True}), "Alive", None)
    )
    log_event(
        guild_id, user_id,
        code=f"NPC_ADD_{name.upper()}",
        title=f"{ICONS['npc']} NPC baru: {name}",
        details=f"Role: {role}",
        etype="npc_add",
        actors=[name],
        tags=["npc", "add"]
    )
    return f"{ICONS['npc']} NPC **{name}** berhasil ditambahkan."


async def add_trait(guild_id: int, name: str, key: str, value: str, visible=False, user_id=None):
    npc = get_npc(guild_id, name)
    if not npc:
        return "❌ NPC tidak ditemukan."

    traits = json.loads(npc.get("traits") or "{}")
    traits[key] = {"value": value, "visible": visible}
    execute(guild_id, "UPDATE npc SET traits=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
            (json.dumps(traits), guild_id, npc["id"]))

    log_event(guild_id, user_id or 0, code=f"NPC_TRAIT_ADD_{name.upper()}",
              title=f"➕ Trait {key} ditambahkan ke {name}", details=f"Value: {value}, Visible: {visible}",
              etype="npc_trait_add", actors=[name], tags=["npc", "trait", "add"])
    return f"✅ Trait **{key}={value}** ditambahkan ke **{name}** (visible={visible})."


async def remove_trait(guild_id: int, name: str, key: str, user_id=None):
    npc = get_npc(guild_id, name)
    if not npc:
        return "❌ NPC tidak ditemukan."

    traits = json.loads(npc.get("traits") or "{}")
    if key not in traits:
        return "❌ Trait tidak ditemukan."

    traits.pop(key)
    execute(guild_id, "UPDATE npc SET traits=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
            (json.dumps(traits), guild_id, npc["id"]))
    return f"🗑️ Trait **{key}** dihapus dari **{name}**."


async def reveal_trait(guild_id: int, name: str, key: str, user_id=None):
    npc = get_npc(guild_id, name)
    if not npc:
        return "❌ NPC tidak ditemukan."

    traits = json.loads(npc.get("traits") or "{}")
    if key not in traits:
        return "❌ Trait tidak ada."

    traits[key]["visible"] = True
    execute(guild_id, "UPDATE npc SET traits=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
            (json.dumps(traits), guild_id, npc["id"]))

    val = traits[key]["value"]
    return f"{ICONS['hidden']} {name} ternyata: {val}"


async def all_reveal(guild_id: int, name: str, user_id=None):
    npc = get_npc(guild_id, name)
    if not npc:
        return "❌ NPC tidak ditemukan."

    traits = json.loads(npc.get("traits") or "{}")
    for k in traits:
        traits[k]["visible"] = True

    info = npc.get("info")
    if info:
        try:
            info_data = json.loads(info)
            if isinstance(info_data, dict):
                info_data["visible"] = True
                info = json.dumps(info_data)
        except Exception:
            pass

    execute(guild_id, "UPDATE npc SET traits=%s, info=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
            (json.dumps(traits), info, guild_id, npc["id"]))
    return f"👁️ Semua trait & info **{name}** sudah terbuka."


async def set_info(guild_id: int, name: str, text: str, hidden=False, user_id=None):
    npc = get_npc(guild_id, name)
    if not npc:
        return "❌ NPC tidak ditemukan."

    info = {"value": text, "visible": not hidden}
    execute(guild_id, "UPDATE npc SET info=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
            (json.dumps(info), guild_id, npc["id"]))
    return f"📖 Info untuk **{name}** diupdate. (hidden={hidden})"


async def list_npc(guild_id: int):
    rows = fetchall(guild_id, "SELECT * FROM npc WHERE guild_id=%s ORDER BY LOWER(name) ASC", (guild_id,))
    if not rows:
        return f"{ICONS['npc']} Tidak ada NPC."
    out = []
    for r in rows:
        out.append(f"{ICONS['npc']} **{r['name']}** ({r['role']})")
    return "\n".join(out)


async def sync_from_wiki(guild_id: int, user_id=None):
    rows = fetchall(guild_id, "SELECT * FROM wiki WHERE guild_id=%s AND category='npc'", (guild_id,))
    added = []
    for r in rows:
        npc = get_npc(guild_id, r["name"])
        if not npc:
            execute(
                guild_id,
                "INSERT INTO npc (guild_id, name, role, traits, info, status, affiliation) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (guild_id, r["name"], "Lore NPC", "{}", json.dumps({"value": "", "visible": True}), "Alive", None)
            )
            added.append(r["name"])

    if not added:
        return f"{ICONS['lore']} Tidak ada NPC baru dari lore."
    return f"{ICONS['lore']} NPC ditambahkan dari lore: {', '.join(added)}"


async def remove_npc(guild_id: int, user_id: int, name: str):
    npc = get_npc(guild_id, name)
    if not npc:
        return f"❌ NPC **{name}** tidak ditemukan."

    execute(guild_id, "DELETE FROM npc WHERE guild_id=%s AND name=%s", (guild_id, name))
    return f"{ICONS['remove']} NPC **{name}** dihapus."
