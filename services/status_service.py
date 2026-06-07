import json
from utils.db import execute, fetchone, fetchall
from services import effect_service  # Integrasi penuh dengan sistem efek baru

# ===============================
# STATUS SERVICE (per-server)
# ===============================
# target_type: "char", "enemy", atau "ally"

def _table(target_type: str) -> str:
    if target_type == "enemy":
        return "enemies"
    elif target_type == "ally":
        return "allies"
    return "characters"

ICONS = {
    "buff": "✨",
    "debuff": "☠️",
    "expired": "⌛"
}

# -------------------------------
# Helpers
# -------------------------------
def _baseline_row(table: str, name: str) -> dict:
    """Nilai baseline aman untuk INSERT awal."""
    base = {
        "name": name,
        "hp": 0, "hp_max": 0,
        "energy": 0, "energy_max": 0,
        "stamina": 0, "stamina_max": 0,
        "ac": 10, "init_mod": 0,
        "str_stat": 0, "dex": 0, "con": 0, "int_stat": 0, "wis": 0, "cha": 0,
        "level": 1, "xp": 0, "gold": 0, "speed": 30,
        "equipment": "{}", "companions": "[]", "inventory": "[]",
        "effects": "[]"
    }
    if table == "enemies":
        base.update({
            "xp_reward": 0, "gold_reward": 0, "loot": "[]"
        })
    elif table == "allies":
        base.update({
            "effects": "[]"
        })
    return base

def _ensure_exists(guild_id: int, table: str, name: str) -> dict:
    """Pastikan row ada. Kalau belum, INSERT baseline."""
    row = fetchone(guild_id, f"SELECT * FROM {table} WHERE name=%s", (name,))
    if row:
        return row

    base = _baseline_row(table, name)
    cols = ", ".join(base.keys())
    placeholders = ", ".join(["%s"] * len(base))
    execute(guild_id, f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", tuple(base.values()))
    return fetchone(guild_id, f"SELECT * FROM {table} WHERE name=%s", (name,))

# ===============================
# XP SCALING HELPER
# ===============================
def xp_required(level: int) -> int:
    """XP untuk naik DARI `level` ke level berikutnya.
    HARUS identik dgn web (lib/xp.ts xpRequired): pakai round, bukan int/truncate."""
    L = max(1, int(level or 1))
    return round(100 * (1.5 ** (L - 1)))


def level_from_total_xp(total_xp: int):
    """Turunkan (level, into, need) dari TOTAL xp kumulatif.
    Padanan web: lib/xp.ts levelFromTotalXp."""
    total = max(0, int(total_xp or 0))
    level, spent = 1, 0
    need = xp_required(level)
    while total - spent >= need and level < 999:
        spent += need
        level += 1
        need = xp_required(level)
    return level, total - spent, need


def total_xp_for_level(level: int) -> int:
    """XP kumulatif minimum agar tepat berada di awal `level`."""
    target = max(1, int(level or 1))
    return sum(xp_required(L) for L in range(1, target))

# ===============================
# HP / VITALS
# ===============================
async def damage(guild_id: int, target_type, name, amount: int):
    table = _table(target_type)
    row = _ensure_exists(guild_id, table, name)

    hp_max = int(row.get("hp_max") or 0)
    cur_hp = int(row.get("hp") or 0)
    new_hp = max(0, cur_hp - int(amount))

    execute(guild_id, f"UPDATE {table} SET hp=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (new_hp, row["id"]))

    execute(guild_id, "INSERT INTO history (guild_id, action, data) VALUES (%s,%s,%s)",
            (guild_id, "dmg", json.dumps({"target": name, "type": target_type,
                                "old": cur_hp, "new": new_hp, "amount": int(amount)})))
    execute(guild_id, "INSERT INTO timeline (guild_id, event) VALUES (%s,%s)",
            (guild_id, f"{name} menerima {int(amount)} damage → {new_hp}/{hp_max} HP",))
    return new_hp

async def heal(guild_id: int, target_type, name, amount: int):
    table = _table(target_type)
    row = _ensure_exists(guild_id, table, name)

    hp_max = int(row.get("hp_max") or 0)
    cur_hp = int(row.get("hp") or 0)
    if hp_max <= 0:
        hp_max = cur_hp + int(amount)
        execute(guild_id, f"UPDATE {table} SET hp_max=%s WHERE id=%s", (hp_max, row["id"]))

    new_hp = min(hp_max, cur_hp + int(amount))
    execute(guild_id, f"UPDATE {table} SET hp=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (new_hp, row["id"]))

    execute(guild_id, "INSERT INTO history (guild_id, action, data) VALUES (%s,%s,%s)",
            (guild_id, "heal", json.dumps({"target": name, "type": target_type,
                                 "old": cur_hp, "new": new_hp, "amount": int(amount)})))
    execute(guild_id, "INSERT INTO timeline (guild_id, event) VALUES (%s,%s)",
            (guild_id, f"{name} disembuhkan {int(amount)} HP → {new_hp}/{hp_max} HP",))
    return new_hp

async def use_resource(guild_id: int, target_type, name, field: str, amount: int, regen=False):
    """Kurangi / regen resource (energy/stamina)."""
    table = _table(target_type)
    row = _ensure_exists(guild_id, table, name)

    cur = int(row.get(field) or 0)
    mx = int(row.get(f"{field}_max") or 0)

    if regen and mx <= 0:
        mx = cur + int(amount)
        execute(guild_id, f"UPDATE {table} SET {field}_max=%s WHERE id=%s", (mx, row["id"]))

    new_val = min(mx, cur + int(amount)) if regen else max(0, cur - int(amount))
    execute(guild_id, f"UPDATE {table} SET {field}=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (new_val, row["id"]))

    action = "regen" if regen else "use"
    execute(guild_id, "INSERT INTO history (guild_id, action, data) VALUES (%s,%s,%s)",
            (guild_id, f"{field}_{action}", json.dumps({"target": name, "type": target_type,
                                              "old": cur, "new": new_val, "amount": int(amount)})))
    return new_val

# ===============================
# EFFECTS (Delegasi ke effect_service)
# ===============================
async def add_effect(guild_id: int, target_type: str, name: str, effect_name: str, duration: int = None, is_buff: bool = True):
    """Gunakan sistem library dari effect_service."""
    ok, msg = await effect_service.apply_effect(guild_id, name, effect_name, duration)
    if not ok:
        return f"❌ {msg}"
    return msg

async def clear_effects(guild_id: int, target_type: str, name: str, is_buff: bool = True):
    """Gunakan sistem clear dari effect_service."""
    ok, msg = await effect_service.clear_effects(guild_id, name, is_buff=is_buff)
    if not ok:
        return f"❌ {msg}"
    return msg

async def tick_all_effects(guild_id: int):
    """Delegasi ke sistem tick dari effect_service."""
    results = await effect_service.tick_effects(guild_id)
    return results

# ===============================
# EQUIPMENT (char only)
# ===============================
async def set_equipment(guild_id: int, name, slot: str, item: str):
    row = _ensure_exists(guild_id, "characters", name)
    eq = json.loads(row.get("equipment") or "{}")
    eq[slot] = item
    execute(guild_id, "UPDATE characters SET equipment=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (json.dumps(eq), row["id"]))
    return eq

# ===============================
# COMPANIONS (char only)
# ===============================
async def add_companion(guild_id: int, name, comp: dict):
    row = _ensure_exists(guild_id, "characters", name)
    comps = json.loads(row.get("companions") or "[]")
    comps.append(comp)
    execute(guild_id, "UPDATE characters SET companions=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (json.dumps(comps), row["id"]))
    return comps

async def remove_companion(guild_id: int, name, comp_name: str):
    row = _ensure_exists(guild_id, "characters", name)
    comps = json.loads(row.get("companions") or "[]")
    comps = [c for c in comps if c.get("name","").lower() != comp_name.lower()]
    execute(guild_id, "UPDATE characters SET companions=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (json.dumps(comps), row["id"]))
    return comps

# ===============================
# GENERIC FIELD UPDATE
# ===============================
async def set_status(guild_id: int, target_type, name, field: str, value):
    table = _table(target_type)
    row = _ensure_exists(guild_id, table, name)
    old_value = row.get(field)
    execute(guild_id, f"UPDATE {table} SET {field}=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (value, row["id"]))
    execute(guild_id, "INSERT INTO history (guild_id, action, data) VALUES (%s,%s,%s)",
            (guild_id, "set_status", json.dumps({"target": name, "type": target_type,
                                       "field": field, "old": old_value, "new": value})))
    return value

# ===============================
# GOLD & XP HELPERS (char only)
# ===============================
async def add_gold(guild_id: int, name, amount: int):
    row = _ensure_exists(guild_id, "characters", name)
    cur = int(row.get("gold") or 0)
    new_val = max(0, cur + int(amount))
    execute(guild_id, "UPDATE characters SET gold=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (new_val, row["id"]))
    return new_val

async def add_xp(guild_id: int, name, amount: int):
    """Tambah XP. MODEL: kolom `xp` = TOTAL kumulatif; `level` diturunkan.
    Lonjakan besar tertangani otomatis (butuh 100, dikasih 150 -> naik 1 lv, sisa 50).
    Return level baru bila naik level, None kalau tidak."""
    row = _ensure_exists(guild_id, "characters", name)
    cur_xp = int(row.get("xp") or 0)
    old_level, _, _ = level_from_total_xp(cur_xp)

    new_xp = max(0, cur_xp + int(amount))
    new_level, _, _ = level_from_total_xp(new_xp)

    execute(
        guild_id,
        "UPDATE characters SET xp=%s, level=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
        (new_xp, new_level, row["id"])
    )

    return new_level if new_level > old_level else None
