import json
from utils.db import fetchone, fetchall, execute
from services import item_service, inventory_service, favor_service, quest_service

ICON_DEFAULT = "📦"


def add_item(guild_id: int, npc_name: str, item: str, price: int, stock: int = -1,
             favor_req: dict = None, quest_req: list = None):
    execute(
        guild_id,
        """
        INSERT INTO npc_shop (guild_id, npc_name, item, price, stock, favor_req, quest_req)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (guild_id, npc_name, item) DO UPDATE SET
            price=EXCLUDED.price,
            stock=EXCLUDED.stock,
            favor_req=EXCLUDED.favor_req,
            quest_req=EXCLUDED.quest_req,
            updated_at=NOW()
        """,
        (guild_id, npc_name, item, price, stock,
         json.dumps(favor_req or {}),
         json.dumps(quest_req or []))
    )
    return True


def remove_item(guild_id: int, npc_name: str, item: str):
    execute(guild_id, "DELETE FROM npc_shop WHERE guild_id=%s AND npc_name=%s AND item=%s",
            (guild_id, npc_name, item))
    return True


def clear_shop(guild_id: int, npc_name: str):
    execute(guild_id, "DELETE FROM npc_shop WHERE guild_id=%s AND npc_name=%s", (guild_id, npc_name))
    return True


def _check_requirements(guild_id: int, row, char_name: str):
    favor_req = json.loads(row.get("favor_req") or "{}")
    quest_req = json.loads(row.get("quest_req") or "[]")

    if favor_req:
        for fac, need in favor_req.items():
            # FIX: tambahkan guild_id ke query favors
            f = fetchone(guild_id,
                         "SELECT favor FROM favors WHERE guild_id=%s AND char_name=%s AND faction=%s",
                         (guild_id, char_name, fac))
            have = f["favor"] if f else 0
            if have < need:
                return False

    if quest_req:
        for qname in quest_req:
            q = quest_service.get_quest(guild_id, qname)
            if not q or q["status"] != "completed":
                return False

    return True


def list_items(guild_id: int, npc_name: str, char_name: str = None, gm_view: bool = False):
    rows = fetchall(
        guild_id,
        """
        SELECT s.*
        FROM npc_shop s
        LEFT JOIN items i ON s.item = i.name AND i.guild_id = s.guild_id
        WHERE s.guild_id=%s AND s.npc_name=%s
        """,
        (guild_id, npc_name)
    )

    if not rows:
        return [f"ℹ️ {npc_name} tidak menjual apa-apa."]

    items_sorted = []
    for r in rows:
        item_data = item_service.get_item(guild_id, r["item"])
        rarity = item_data.get("rarity", "Common") if item_data else "Common"
        items_sorted.append((rarity, r["item"].lower(), r, item_data))

    items_sorted.sort(key=lambda e: (item_service.RARITY_ORDER.get(e[0], 99), e[1]))

    out = []
    for rarity, _, r, item_data in items_sorted:
        effect = item_data.get("effect", "-") if item_data else "-"
        requirement = item_data.get("requirement", "") if item_data else ""
        req_text = f"\n⚠️ Req: {requirement}" if requirement else ""
        icon = item_data.get("icon", ICON_DEFAULT) if item_data else ICON_DEFAULT
        rarity_icon = item_service.RARITY_ICON.get(rarity, "⬜")

        price = r["price"]
        stock = r["stock"]
        stock_text = "∞" if stock < 0 else str(stock)

        locked = False
        if not gm_view and char_name:
            locked = not _check_requirements(guild_id, r, char_name)

        if locked:
            out.append(
                f"{rarity_icon}{icon} **{r['item']}** — 💰 - gold | Stock: -\n"
                f"🔒 Sebuah misi harus selesai / butuh syarat tertentu"
            )
        else:
            out.append(
                f"{rarity_icon}{icon} **{r['item']}** — 💰 {price} gold | Stock: {stock_text}\n"
                f"✨ {effect}{req_text}"
            )

    return out


def buy_item(guild_id: int, npc_name: str, char_name: str, item: str, qty: int = 1):
    r = fetchone(
        guild_id,
        "SELECT * FROM npc_shop WHERE guild_id=%s AND npc_name=%s AND item=%s",
        (guild_id, npc_name, item)
    )
    if not r:
        return False, f"❌ {npc_name} tidak menjual {item}."

    if not _check_requirements(guild_id, r, char_name):
        return False, f"🔒 {char_name} belum memenuhi syarat untuk membeli {item}."

    price = int(r["price"]) * qty
    stock = int(r["stock"])

    char = fetchone(guild_id, "SELECT gold, carry_capacity, carry_used FROM characters WHERE guild_id=%s AND name=%s",
                    (guild_id, char_name))
    if not char:
        return False, f"❌ Karakter {char_name} tidak ditemukan."

    gold = int(char.get("gold", 0))
    if gold < price:
        return False, f"❌ {char_name} tidak punya cukup gold ({gold}/{price})."

    if stock >= 0 and stock < qty:
        return False, f"❌ Stok {item} di {npc_name} hanya {stock}."

    item_data = item_service.get_item(guild_id, item)
    weight = float(item_data.get("weight", 0)) if item_data else 0
    new_carry = (char.get("carry_used", 0) or 0) + weight * qty
    if new_carry > (char.get("carry_capacity", 0) or 0):
        return False, f"⚖️ {char_name} kelebihan beban! Tidak bisa membeli {item}."

    new_gold = gold - price
    execute(guild_id, "UPDATE characters SET gold=%s, carry_used=%s WHERE guild_id=%s AND name=%s",
            (new_gold, new_carry, guild_id, char_name))

    if stock >= 0:
        new_stock = stock - qty
        execute(guild_id, "UPDATE npc_shop SET stock=%s, updated_at=NOW() WHERE guild_id=%s AND id=%s",
                (new_stock, guild_id, r["id"]))

    inventory_service.add_item(guild_id, char_name, item, qty, user_id="system")
    return True, f"✅ {char_name} membeli {qty}x {item} dari {npc_name} seharga {price} gold."
