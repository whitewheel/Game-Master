import json
from typing import Dict, List, Optional, Tuple
from utils.db import execute, fetchone, fetchall

DEFAULT_STACK_MAX = 3


def add_effect_lib(guild_id: int, name: str, e_type: str, target_stat: str, formula: str,
                   duration: int, stack_mode: str, description: str, max_stack: Optional[int] = None) -> None:
    if max_stack is None:
        max_stack = DEFAULT_STACK_MAX if stack_mode == "stack" else 1
    execute(
        guild_id,
        """
        INSERT INTO effects (guild_id, name, type, target_stat, formula, duration, stack_mode, max_stack, description)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (guild_id, name) DO UPDATE SET
            type=EXCLUDED.type, target_stat=EXCLUDED.target_stat,
            formula=EXCLUDED.formula, duration=EXCLUDED.duration,
            stack_mode=EXCLUDED.stack_mode, max_stack=EXCLUDED.max_stack,
            description=EXCLUDED.description
        """,
        (guild_id, name.lower(), e_type, target_stat, formula, int(duration), stack_mode, int(max_stack), description),
    )


def get_effect_lib(guild_id: int, name: str) -> Optional[Dict]:
    return fetchone(guild_id, "SELECT * FROM effects WHERE guild_id=%s AND name=%s", (guild_id, name.lower()))


def list_effects_lib(guild_id: int) -> List[Dict]:
    return fetchall(guild_id, "SELECT * FROM effects WHERE guild_id=%s ORDER BY name ASC", (guild_id,))


def remove_effect_lib(guild_id: int, name: str) -> bool:
    row = fetchone(guild_id, "SELECT id FROM effects WHERE guild_id=%s AND name=%s", (guild_id, name.lower()))
    if not row:
        return False
    execute(guild_id, "DELETE FROM effects WHERE guild_id=%s AND id=%s", (guild_id, row["id"]))
    return True


def _find_target(guild_id: int, name: str) -> Optional[Tuple[str, Dict]]:
    for table in ["characters", "enemies", "allies", "companions"]:
        row = fetchone(guild_id, f"SELECT * FROM {table} WHERE guild_id=%s AND name=%s", (guild_id, name))
        if row:
            return table, row

    chars = fetchall(guild_id, "SELECT id, name, companions FROM characters WHERE guild_id=%s", (guild_id,))
    for ch in chars:
        try:
            comps = json.loads(ch.get("companions") or "[]")
            for comp in comps:
                if comp.get("name", "").lower() == name.lower():
                    comp["_owner_id"] = ch["id"]
                    comp["_owner_name"] = ch["name"]
                    return "companion_json", comp
        except Exception:
            continue
    return None


def _load_effects(row: Dict) -> List[Dict]:
    try:
        return json.loads(row.get("effects") or "[]")
    except Exception:
        return []


def _save_effects(guild_id: int, table: str, row_id: int, effects: List[Dict]) -> None:
    if table == "companion_json":
        owner_id = row_id
        owner_row = fetchone(guild_id, "SELECT * FROM characters WHERE guild_id=%s AND id=%s", (guild_id, owner_id))
        if not owner_row:
            return
        comps = json.loads(owner_row.get("companions") or "[]")
        for c in comps:
            if c.get("name", "").lower() == (effects[0].get("id") if effects else "").lower():
                c["effects"] = effects
        execute(guild_id, "UPDATE characters SET companions=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
                (json.dumps(comps), guild_id, owner_id))
    else:
        execute(guild_id, f"UPDATE {table} SET effects=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
                (json.dumps(effects), guild_id, row_id))


def _pretty_name(name: str) -> str:
    return name.replace("_", " ").title()


def _match_effect_instance(inst: Dict, lib_name: str) -> bool:
    return (inst.get("id") or "").lower() == lib_name.lower()


def update_effect_field(guild_id: int, name: str, field: str, value: str):
    valid_fields = ["name", "type", "target_stat", "formula", "duration", "stack_mode", "description", "max_stack"]
    if field not in valid_fields:
        return False
    row = fetchone(guild_id, "SELECT id FROM effects WHERE guild_id=%s AND name=%s", (guild_id, name))
    if not row:
        return False
    execute(guild_id, f"UPDATE effects SET {field}=%s WHERE guild_id=%s AND name=%s", (value, guild_id, name))
    return True


async def apply_effect(guild_id: int, target_name: str, effect_name: str, override_duration: Optional[str] = None):
    found = _find_target(guild_id, target_name)
    if not found:
        return False, f"❌ Target **{target_name}** tidak ditemukan."
    table, row = found
    lib = get_effect_lib(guild_id, effect_name)
    if not lib:
        return False, f"❌ Efek **{effect_name}** tidak ada di library."

    effects = _load_effects(row)
    mode = (lib.get("stack_mode") or "unique").lower()
    max_stack = int(lib.get("max_stack") or (DEFAULT_STACK_MAX if mode == "stack" else 1))

    formula = lib.get("formula") or ""
    duration = int(lib.get("duration") or 1)
    if override_duration is not None:
        parts = str(override_duration).split()
        if len(parts) == 2 and parts[0].startswith(("+", "-")):
            formula = parts[0]
            duration = int(parts[1])
        elif str(override_duration).startswith(("+", "-")):
            formula = str(override_duration)
        else:
            duration = int(override_duration)
    base_duration = duration

    existing_idx = next((i for i, e in enumerate(effects) if _match_effect_instance(e, lib["name"])), None)
    display = _pretty_name(lib["name"])
    e_type = lib["type"] or "debuff"

    def _make_inst(stack=1):
        return {
            "id": lib["name"],
            "text": f"{display}" + (f" Lv {stack}" if stack > 1 else ""),
            "type": e_type,
            "duration": base_duration,
            "stack": stack,
            "mode": mode,
            "formula": formula,
            "target_stat": lib.get("target_stat") or "",
            "description": lib.get("description") or ""
        }

    if mode == "multi-instance":
        effects.append(_make_inst())
        _save_effects(guild_id, table, row.get("id") or row.get("_owner_id"), effects)
        return True, f"☠️ {target_name} mendapat **{display}** ({base_duration} turn)."

    if mode == "refresh":
        if existing_idx is None:
            effects.append(_make_inst())
        else:
            effects[existing_idx]["duration"] = base_duration
            effects[existing_idx]["formula"] = formula
        _save_effects(guild_id, table, row.get("id") or row.get("_owner_id"), effects)
        return True, f"🔁 {target_name}: **{display}** di-refresh ({base_duration} turn)."

    if mode == "stack":
        if existing_idx is None:
            effects.append(_make_inst(1))
            msg = f"📈 {target_name} mendapat **{display} Lv1** ({base_duration} turn)."
        else:
            cur = effects[existing_idx]
            new_stack = min(int(cur.get("stack", 1)) + 1, max_stack)
            cur.update(_make_inst(new_stack))
            msg = f"📈 {target_name}: **{display}** naik ke **Lv{new_stack}** ({base_duration} turn)."
        _save_effects(guild_id, table, row.get("id") or row.get("_owner_id"), effects)
        return True, msg

    if existing_idx is not None:
        return True, f"ℹ️ {target_name} sudah memiliki **{display}** (unique)."
    effects.append(_make_inst())
    _save_effects(guild_id, table, row.get("id") or row.get("_owner_id"), effects)
    return True, f"✅ {target_name} mendapat **{display}** ({base_duration} turn)."


def get_active_effects(guild_id: int, target_name: str):
    found = _find_target(guild_id, target_name)
    if not found:
        return False, f"❌ Target **{target_name}** tidak ditemukan.", []
    table, row = found
    return True, table, _load_effects(row)


def _format_eff_line(e: Dict, guild_id: int) -> str:
    dur = int(e.get("duration", -1))
    dur_txt = f"{dur}" if dur >= 0 else "∞"
    form = e.get("formula") or "-"
    stack = e.get("stack", 1)
    stack_txt = f" Lv{stack}" if stack > 1 else ""

    desc = e.get("description", "")
    if not desc and e.get("id"):
        row = fetchone(guild_id, "SELECT description FROM effects WHERE guild_id=%s AND name=%s",
                       (guild_id, e["id"].lower()))
        if row and row.get("description"):
            desc = row["description"]

    return f"🔹 **{e.get('text','')}**{stack_txt} — {form} *(sisa {dur_txt} turn)*\n🛈 {desc or '(tidak ada deskripsi)'}"


async def tick_effects(guild_id: int) -> Dict:
    results = {"char": {}, "enemy": {}, "ally": {}, "companion": {}}
    for ttype, table in [("char", "characters"), ("enemy", "enemies"), ("ally", "allies"), ("companion", "companions")]:
        rows = fetchall(guild_id, f"SELECT * FROM {table} WHERE guild_id=%s", (guild_id,))
        for r in rows:
            name = r["name"]
            effs = _load_effects(r)
            remain, expired = [], []
            for e in effs:
                d = int(e.get("duration", -1))
                if d == -1:
                    remain.append(e)
                elif d > 1:
                    e["duration"] = d - 1
                    remain.append(e)
                else:
                    expired.append(e)
            _save_effects(guild_id, table, r["id"], remain)
            if expired:
                for e in expired:
                    execute(guild_id, "INSERT INTO timeline (guild_id, event) VALUES (%s,%s)",
                            (guild_id, f"⌛ {name} kehilangan efek: {e.get('text','')}"))
            results[ttype][name] = {"active": remain, "expired": expired}
    return results


async def clear_effects(guild_id: int, target_name: str, is_buff: Optional[bool] = None) -> Tuple[bool, str]:
    found = _find_target(guild_id, target_name)
    if not found:
        return False, f"❌ Target **{target_name}** tidak ditemukan."

    table, row = found
    effects = _load_effects(row)
    if not effects:
        return True, f"ℹ️ {target_name} tidak memiliki efek aktif."

    if is_buff is None:
        effects = []
        msg = f"🧹 Semua efek dihapus dari **{target_name}**."
    else:
        typ = "buff" if is_buff else "debuff"
        before = len(effects)
        effects = [e for e in effects if e.get("type", "").lower() != typ]
        removed = before - len(effects)
        if removed == 0:
            msg = f"ℹ️ Tidak ada {typ} pada {target_name}."
        else:
            icon = "✨" if is_buff else "☠️"
            msg = f"{icon} {removed} {typ} dihapus dari **{target_name}**."

    _save_effects(guild_id, table, row.get("id") or row.get("_owner_id"), effects)
    return True, msg


def build_tick_embed(discord, guild_id: int, guild_name: str, results: Dict, engaged: list = None):
    embed = discord.Embed(
        title="⏳ Tick Round Effects",
        description=f"Server: **{guild_name}**\n(Manual GM mode — tidak ada auto damage)",
        color=discord.Color.orange(),
    )

    def _section(ttype, icon, label):
        data = results.get(ttype) or {}
        if engaged:
            data = {k: v for k, v in data.items() if k in engaged}
        if not data:
            return
        lines = []
        for name, info in data.items():
            active = [_format_eff_line(e, guild_id) for e in info.get("active", [])] or ["(tidak ada efek aktif)"]
            expired = [f"• {e.get('text','')}" for e in info.get("expired", [])]
            block = f"**{name}**\n✨ Active:\n" + "\n".join(active)
            if expired:
                block += "\n⌛ **Expired:**\n" + "\n".join(expired)
            lines.append(block)
        embed.add_field(name=f"{icon} {label}", value="\n\n".join(lines), inline=False)

    _section("char", "🧍", "Characters")
    _section("enemy", "👹", "Enemies")
    _section("ally", "🤝", "Allies")
    _section("companion", "🐜", "Companions")
    return embed
