import json
from utils.db import fetchone, execute
from services import inventory_service, item_service
from cogs.world.timeline import log_event

SLOTS = [
    "main_hand", "off_hand",
    "armor_inner", "armor_outer",
    "accessory1", "accessory2", "accessory3",
    "augment1", "augment2", "augment3",
]

SLOT_ICONS = {
    "main_hand": "🗡️", "off_hand": "🔪",
    "armor_inner": "👕", "armor_outer": "🛡️",
    "accessory1": "💍", "accessory2": "💍", "accessory3": "💍",
    "augment1": "🧬", "augment2": "🧬", "augment3": "🧬",
    "mod": "🧩",
}


def _norm_name(x: str) -> str:
    try:
        return item_service.normalize_name(x)
    except Exception:
        return (x or "").strip()


def _get_char(guild_id: int, char: str):
    return fetchone(guild_id, "SELECT * FROM characters WHERE guild_id=%s AND name=%s", (guild_id, char))


def _update_equipment(guild_id: int, char: str, eq: dict):
    execute(
        guild_id,
        "UPDATE characters SET equipment=%s, updated_at=NOW() WHERE guild_id=%s AND name=%s",
        (json.dumps(eq), guild_id, char)
    )


def equip_item(guild_id: int, char: str, slot: str, item_name: str, user_id="0"):
    slot = (slot or "").lower()
    c = _get_char(guild_id, char)
    if not c:
        return False, f"❌ Karakter {char} tidak ditemukan."

    eq = json.loads(c.get("equipment") or "{}")
    if not eq:
        eq = {s: "" for s in SLOTS}
        eq["mods"] = []

    if slot == "mod":
        inv = inventory_service.get_inventory(guild_id, char)
        target = _norm_name(item_name)
        found = next((it for it in inv if _norm_name(it["item"]) == target and (it["qty"] or 0) > 0), None)
        if not found:
            return False, f"❌ {char} tidak punya \"{item_name}\" di inventory."

        eq.setdefault("mods", [])
        eq["mods"].append(found["item"])
        _update_equipment(guild_id, char, eq)
        inventory_service.remove_item(guild_id, char, found["item"], 1, user_id=user_id)
        inventory_service.calc_carry(guild_id, char)
        return True, f"🧩 {char} sekarang memiliki mod {found['item']}."

    if slot not in SLOTS:
        return False, f"❌ Slot tidak valid. Pilih: {', '.join(SLOTS)} atau `mod`"

    inv = inventory_service.get_inventory(guild_id, char)
    target = _norm_name(item_name)
    found = next((it for it in inv if _norm_name(it["item"]) == target and (it["qty"] or 0) > 0), None)
    if not found:
        return False, f"❌ {char} tidak punya \"{item_name}\" di inventory."

    item_data = item_service.get_item(guild_id, target)
    weight = float(item_data.get("weight", 0)) if item_data else 0.0
    carry_capacity = c.get("carry_capacity", 0) or 0
    carry_used = c.get("carry_used", 0.0) or 0.0
    if carry_capacity > 0 and carry_used + weight > carry_capacity:
        return False, f"❌ {char} tidak sanggup equip {item_name} (melebihi kapasitas)."

    if eq.get(slot):
        inventory_service.add_item(guild_id, char, eq[slot], 1, user_id=user_id)

    eq[slot] = found["item"]
    _update_equipment(guild_id, char, eq)
    inventory_service.remove_item(guild_id, char, found["item"], 1, user_id=user_id)
    inventory_service.calc_carry(guild_id, char)
    return True, f"⚔️ {char} sekarang memakai {found['item']} di slot {slot}."


def unequip_item(guild_id: int, char: str, slot: str, user_id="0"):
    slot = (slot or "").lower()
    if slot not in SLOTS:
        return False, f"❌ Slot tidak valid. Pilih: {', '.join(SLOTS)}"

    c = _get_char(guild_id, char)
    if not c:
        return False, f"❌ Karakter {char} tidak ditemukan."

    eq = json.loads(c.get("equipment") or "{}")
    if not eq:
        eq = {s: "" for s in SLOTS}
        eq["mods"] = []

    if not eq.get(slot):
        return False, f"❌ Slot {slot} kosong."

    item_name = eq[slot]
    inventory_service.add_item(guild_id, char, item_name, 1, user_id=user_id)
    eq[slot] = ""
    _update_equipment(guild_id, char, eq)
    inventory_service.calc_carry(guild_id, char)
    return True, f"🛑 {char} melepas {item_name} dari slot {slot}."


def remove_mod(guild_id: int, char: str, item_name: str, user_id="0"):
    c = _get_char(guild_id, char)
    if not c:
        return False, f"❌ Karakter {char} tidak ditemukan."

    eq = json.loads(c.get("equipment") or "{}")
    if "mods" not in eq:
        eq["mods"] = []

    mods = eq["mods"]
    match = next((m for m in mods if m.lower() == item_name.lower()), None)
    if not match:
        return False, f"❌ {char} tidak punya mod {item_name}."

    mods.remove(match)
    eq["mods"] = mods
    _update_equipment(guild_id, char, eq)
    inventory_service.add_item(guild_id, char, match, 1, user_id=user_id)
    inventory_service.calc_carry(guild_id, char)
    return True, f"🧩 {char} melepas mod {match}."


def _default_eq_dict() -> dict:
    base = {s: "" for s in SLOTS}
    base["mods"] = []
    return base


def get_equipment_dict(guild_id: int, char: str):
    c = _get_char(guild_id, char)
    if not c:
        return None

    raw = c.get("equipment")
    try:
        eq = json.loads(raw) if raw else {}
    except Exception:
        eq = {}

    if not isinstance(eq, dict):
        eq = {}

    out = _default_eq_dict()
    for s in SLOTS:
        out[s] = eq.get(s, "") or ""
    out["mods"] = list(eq.get("mods", []) or [])
    return out


def get_mod_list(guild_id: int, char: str) -> list:
    eq = get_equipment_dict(guild_id, char)
    if not eq:
        return []
    mods = eq.get("mods", [])
    return list(mods) if isinstance(mods, list) else []


def show_equipment(guild_id: int, char: str):
    c = _get_char(guild_id, char)
    if not c:
        return None

    eq = json.loads(c.get("equipment") or "{}")
    if not eq:
        eq = {s: "" for s in SLOTS}
        eq["mods"] = []

    out = []
    for s in SLOTS:
        item = eq.get(s, "")
        icon = SLOT_ICONS.get(s, "▫️")
        if item:
            it = item_service.get_item(guild_id, item)
            item_icon = it["icon"] if it else "📦"
            out.append(f"{icon} **{s}**: {item_icon} {item}")
        else:
            out.append(f"{icon} **{s}**: (kosong)")

    mods = eq.get("mods", [])
    if mods:
        out.append("🧩 **Mods:**")
        for m in mods:
            it = item_service.get_item(guild_id, m)
            icon = it["icon"] if it else "📦"
            out.append(f"   • {icon} {m}")
    else:
        out.append("🧩 **Mods:** (tidak ada)")

    return out
