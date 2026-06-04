import json
import re
from utils.db import execute, fetchone, fetchall

ICONS = {
    "weapon": "🗡️",
    "armor": "🛡️",
    "accessory": "💍",
    "consumable": "🧪",
    "gadget": "🔧",
    "misc": "📦",
}

RARITY_ORDER = {
    "Common": 1, "Uncommon": 2, "Rare": 3,
    "Epic": 4, "Legendary": 5, "Mythic": 6, "Ascendant": 7
}

RARITY_ICON = {
    "Common": "🟢", "Uncommon": "🔵", "Rare": "🟣",
    "Epic": "🟡", "Legendary": "🔴", "Mythic": "🟠", "Ascendant": "🌠"
}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).title()


def add_item(guild_id: int, data: dict):
    data["name"] = normalize_name(data.get("name", ""))
    req = data.get("requirement", "").strip()
    if req == "-":
        req = ""
    data["requirement"] = req

    weight = data.get("weight", 0.1)
    try:
        weight = float(weight)
    except Exception:
        weight = 0.1
    if weight <= 0:
        weight = 0.1

    execute(guild_id, """
        INSERT INTO items (guild_id, name, item_type, effect, rarity, item_value, weight, slot, notes, rules, requirement)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (guild_id, name) DO UPDATE SET
            item_type=EXCLUDED.item_type,
            effect=EXCLUDED.effect,
            rarity=EXCLUDED.rarity,
            item_value=EXCLUDED.item_value,
            weight=EXCLUDED.weight,
            slot=EXCLUDED.slot,
            notes=EXCLUDED.notes,
            rules=EXCLUDED.rules,
            requirement=EXCLUDED.requirement,
            updated_at=NOW()
    """, (
        guild_id,
        data.get("name"),
        data.get("type") or data.get("item_type"),
        data.get("effect"),
        data.get("rarity", "Common"),
        data.get("value") or data.get("item_value", 0),
        weight,
        data.get("slot"),
        data.get("notes", ""),
        data.get("rules", ""),
        data.get("requirement", "")
    ))
    return True


def update_item(guild_id: int, name: str, updates: dict):
    row = get_item(guild_id, name)
    if not row:
        return False
    row.update(updates)
    return add_item(guild_id, row)


def get_item(guild_id: int, name: str):
    norm = normalize_name(name)
    row = fetchone(guild_id, "SELECT * FROM items WHERE guild_id=%s AND name=%s", (guild_id, norm))
    if not row:
        return None
    item = dict(row)
    item["icon"] = ICONS.get((item.get("item_type") or "").lower(), ICONS["misc"])
    # alias untuk kompatibilitas kode lama
    item["type"] = item.get("item_type")
    item["value"] = item.get("item_value")
    return item


def list_items(guild_id: int, limit: int = 50):
    rows = fetchall(guild_id, "SELECT * FROM items WHERE guild_id=%s", (guild_id,))
    if not rows:
        return []

    categories = {}
    for r in rows:
        type_key = (r.get("item_type") or "Misc").capitalize()
        rarity = r.get("rarity", "Common")
        base_icon = ICONS.get((r.get("item_type") or "").lower(), ICONS["misc"])
        rarity_icon = RARITY_ICON.get(rarity, "⬜")
        effect = r.get("effect", "-")
        requirement = r.get("requirement", "")
        req_text = f" | Req: {requirement}" if requirement else ""
        entry = {
            "name": r["name"],
            "rarity": rarity,
            "text": f"{rarity_icon} {base_icon} **{r['name']}** ({rarity}{req_text})\n*{effect}*"
        }
        categories.setdefault(type_key, []).append(entry)

    out = []
    for cat in sorted(categories.keys()):
        out.append(f"__**{cat}**__")
        sorted_entries = sorted(
            categories[cat],
            key=lambda e: (RARITY_ORDER.get(e["rarity"], 99), e["name"].lower())
        )
        for e in sorted_entries:
            out.append(e["text"])

    return out[:limit] if limit else out


def remove_item(guild_id: int, name: str):
    norm = normalize_name(name)
    execute(guild_id, "DELETE FROM items WHERE guild_id=%s AND name=%s", (guild_id, norm))
    return True


def clear_items(guild_id: int) -> int:
    rows = fetchone(guild_id, "SELECT COUNT(*) as c FROM items WHERE guild_id=%s", (guild_id,))
    count = rows["c"] if rows else 0
    execute(guild_id, "DELETE FROM items WHERE guild_id=%s", (guild_id,))
    return count


def search_items(guild_id: int, keyword: str, limit: int = 20):
    rows = fetchall(
        guild_id,
        "SELECT * FROM items WHERE guild_id=%s AND (name ILIKE %s OR item_type ILIKE %s OR effect ILIKE %s) LIMIT %s",
        (guild_id, f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)
    )
    out = []
    for r in rows:
        icon = ICONS.get((r.get("item_type") or "").lower(), ICONS["misc"])
        requirement = r.get("requirement", "")
        req_text = f" | Req: {requirement}" if requirement else ""
        out.append(f"{icon} **{r['name']}** — {r.get('effect','')}{req_text}")
    return out
