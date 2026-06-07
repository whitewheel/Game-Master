import math
import json
import discord
from discord.ext import commands
from services import status_service, inventory_service, item_service, effect_service
from services.equipment_service import SLOT_ICONS, SLOTS
from utils.db import fetchall, fetchone, execute

# ===== Utility =====

def _table_exists(guild_id: int, table: str) -> bool:
    row = fetchone(guild_id, "SELECT name FROM sqlite_master WHERE type='table' AND name=%s", (table,))
    return row is not None

def _bar(cur: int, mx: int, width: int = 12) -> str:
    if mx <= 0:
        return "░" * width
    cur = max(0, min(cur, mx))
    filled = int(round(width * (cur / mx)))
    return "█" * filled + "░" * (width - filled)

def _apply_effects(base_stats, effects):
    stats = base_stats.copy()
    notes = []
    for eff in effects:
        text = eff.get("text", "")
        for key in ["str","dex","con","int","wis","cha"]:
            if key.upper() in text.upper():
                try:
                    val = int(text.replace(key.upper(), "").strip())
                except:
                    val = 0
                stats[key] = stats.get(key, 0) + val
                notes.append(f"{'+' if val>=0 else ''}{val} {key.upper()}")
    return stats, notes

def _format_effect_line(e):
    """Format efek aktif (tanpa warna ANSI, tapi tetap ada deskripsi)."""
    name = e.get("name", e.get("text", "?%s?"))
    typ = e.get("type", "").lower()
    dur = e.get("remaining", e.get("duration", -1))
    dur_txt = f"{dur} turn" if dur >= 0 else "∞"
    desc = e.get("description", "")

    # fallback deskripsi otomatis
    if not desc:
        lname = name.lower()
        if "bleed" in lname:
            desc = "Mengurangi HP -1 tiap turn."
        elif "poison" in lname:
            desc = "Keracunan – HP berkurang perlahan."
        elif "focus" in lname or "focused" in lname:
            desc = "Fokus tinggi – meningkatkan akurasi serangan."
        elif "haste" in lname:
            desc = "Kecepatan meningkat – bonus aksi dan DEX."
        elif "regen" in lname:
            desc = "Regenerasi ringan – memulihkan HP tiap turn."
        elif "burn" in lname:
            desc = "Terbakar – menerima damage tiap giliran."
        elif "frozen" in lname or "freeze" in lname:
            desc = "Membeku – kehilangan 1 aksi pada giliran berikutnya."
        elif "stun" in lname:
            desc = "Terpukul keras – tidak bisa bergerak sementara."
        elif "fear" in lname:
            desc = "Ketakutan – akurasi berkurang tiap turn."
        elif "jammed" in lname:
            desc = "Sistem terganggu – tidak bisa menggunakan senjata jarak jauh."

    # tampilan default
    return f"🔹 **{name}** ({dur_txt})\n{desc}"
def _status_text(cur: int, mx: int) -> str:
    if mx <= 0:
        return "❓ Tidak diketahui"
    pct = (cur / mx) * 100
    if cur <= 0:
        return "💀 Tewas"
    elif pct >= 100:
        return "💪 Segar"
    elif pct >= 75:
        return "🙂 Luka Ringan"
    elif pct >= 50:
        return "⚔️ Luka Sedang"
    elif pct >= 25:
        return "🤕 Luka Berat"
    else:
        return "☠️ Sekarat"

def _energy_status(cur: int, mx: int) -> str:
    if mx <= 0: return "❓ Tidak diketahui"
    pct = (cur / mx) * 100
    if pct >= 75: return "⚡ Penuh tenaga"
    elif pct >= 50: return "😐 Cukup bertenaga"
    elif pct >= 25: return "😓 Hampir habis tenaga"
    else: return "🥵 Kehabisan tenaga"

def _stamina_status(cur: int, mx: int) -> str:
    if mx <= 0: return "❓ Tidak diketahui"
    pct = (cur / mx) * 100
    if pct >= 75: return "🏃 Masih segar"
    elif pct >= 50: return "😤 Terengah-engah"
    elif pct >= 25: return "😩 Hampir kelelahan"
    else: return "🥴 Ambruk kelelahan"

# XP/level: gunakan helper terpusat dari status_service (sumber tunggal, sinkron dgn web).
# (status_service sudah diimpor di atas)

# ===== Embed Builder =====

async def make_embed(characters: list, ctx, title="🧍 Status Karakter"):
    embed = discord.Embed(title=title, color=discord.Color.blurple())
    if not characters:
        embed.add_field(name="(kosong)", value="Gunakan `!status set` untuk menambah karakter.", inline=False)
        return embed

    for c in characters:
        hp_text = f"{c['hp']}/{c['hp_max']}"
        en_text = f"{c['energy']}/{c['energy_max']}"
        st_text = f"{c['stamina']}/{c['stamina_max']}"

        # ===== Efek aktif =====
        effects = json.loads(c.get("effects") or "[]")
        buffs, debuffs = [], []
        for e in effects:
            typ = e.get("type", "").lower()
            if typ == "buff":
                buffs.append(e)
            elif typ == "debuff":
                debuffs.append(e)
            else:
                form = e.get("formula", "")
                (debuffs if "-" in form else buffs).append(e)

        base_stats = {
            "str": c.get("str", 0),
            "dex": c.get("dex", 0),
            "con": c.get("con", 0),
            "int": c.get("int", 0),
            "wis": c.get("wis", 0),
            "cha": c.get("cha", 0),
        }
        final_stats, notes = _apply_effects(base_stats, effects)
        note_line = f" ({', '.join(notes)})" if notes else ""
        stats_line = (
            f"STR {final_stats['str']} | DEX {final_stats['dex']} | CON {final_stats['con']}\n"
            f"INT {final_stats['int']} | WIS {final_stats['wis']} | CHA {final_stats['cha']}{note_line}"
        )

        # ===== Core info =====
        # ===== Core info =====
        # xp = TOTAL kumulatif -> turunkan level + progress-dalam-level untuk display
        cur_level, xp_into, xp_need = status_service.level_from_total_xp(c.get("xp", 0))
        profile_line = f"Lv {cur_level} | XP {xp_into}/{xp_need} | 💰 {c.get('gold',0)} gold"
        combat_line = f"AC {c['ac']} | Init {c['init_mod']} | Speed {c.get('speed',30)}"
        carry_line = f"⚖️ Carry: {c.get('carry_used',0):.1f} / {c.get('carry_capacity',0)}"
        
        # ===== FINAL EMBED VALUE =====
        value = (
            f"{profile_line}\n\n"
            f"❤️ HP {hp_text} [{_bar(c['hp'], c['hp_max'])}]\n"
            f"🔋 Energy {en_text} [{_bar(c['energy'], c['energy_max'])}]\n"
            f"⚡ Stamina {st_text} [{_bar(c['stamina'], c['stamina_max'])}]\n\n"
            f"📘 **Stats**\n{stats_line}\n\n"       # <── INI YANG BELUM ADA
            f"⚔️ Combat\n{combat_line}\n{carry_line}"
        )
        embed.add_field(name=f"🧍 {c['name']}", value=value, inline=False)

        # ===== Buffs =====
        if buffs:
            buff_lines = "\n\n".join([_format_effect_line(b) for b in buffs])
            embed.add_field(name="✨ Buffs", value=buff_lines, inline=False)
        else:
            embed.add_field(name="✨ Buffs", value="*(tidak ada)*", inline=False)

        # ===== Debuffs =====
        if debuffs:
            debuff_lines = "\n\n".join([_format_effect_line(d) for d in debuffs])
            embed.add_field(name="☠️ Debuffs", value=debuff_lines, inline=False)
        else:
            embed.add_field(name="☠️ Debuffs", value="*(tidak ada)*", inline=False)

        # ===== 🐜 Companion List =====
        companions = []
        try:
            companions = json.loads(c.get("companions") or "[]")
        except Exception:
            companions = []

        if companions:
            comp_lines = []
            for comp in companions:
                name = comp.get("name", "(tanpa nama)")
                status = comp.get("status", "Alive")
                icon = "🟢" if status.lower() in ["alive", "hidup"] else "🔴"
                comp_lines.append(f"- {name} ({icon} {status.title()})")
            comp_text = "\n".join(comp_lines)
        else:
            comp_text = "_(tidak ada companion)_"

        embed.add_field(name="🐜 Companions", value=comp_text, inline=False)

    # ===== Footer =====
    embed.set_footer(text="Gunakan !comp show <Nama> untuk lihat detail setiap companion.")
    return embed

async def make_embed_page2(c, ctx):
    embed = discord.Embed(title=f"🎒 Equipment: {c['name']}", color=discord.Color.blurple())
    eq = json.loads(c.get("equipment") or "{}")
    if not eq:
        eq = {s: "" for s in SLOTS}
        eq["mods"] = []
    equip_lines = []
    for slot in SLOTS:
        item_name = eq.get(slot, "")
        if not item_name:
            line = f"**🔹 {slot.title()}**\n(kosong)"
        else:
            item = item_service.get_item(ctx.guild.id, item_name)
            item_icon = item.get("icon", "📦") if item else "📦"
            line = f"**🔹 {slot.title()}**\n{item_icon} {item_name}"
        equip_lines.append(line)
    mods = eq.get("mods", [])
    mod_lines = [f"• {m}" for m in mods] or ["(kosong) tidak ada mod"]
    items = inventory_service.get_inventory(ctx.guild.id, c["name"])
    inv_line = "\n".join([f"({it['qty']}x) {it['item']}" for it in items]) or "-"
    embed.add_field(name="Equipment", value="\n\n".join(equip_lines), inline=False)
    embed.add_field(name="Mods", value="\n".join(mod_lines), inline=False)
    embed.add_field(name="Inventory", value=inv_line, inline=False)
    return embed

# ===== Pagination View =====

class StatusView(discord.ui.View):
    def __init__(self, ctx, c):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.c = c
        self.page = 1

    async def update_embed(self, interaction):
        embed = await (make_embed([self.c], self.ctx, title=f"🧍 Status {self.c['name']}")
                       if self.page == 1 else make_embed_page2(self.c, self.ctx))
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.gray)
    async def prev(self, interaction, button): self.page, _ = 1, await self.update_embed(interaction)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.gray)
    async def next(self, interaction, button): self.page, _ = 2, await self.update_embed(interaction)

# ===== Cog =====

class CharacterStatus(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.group(name="status", invoke_without_command=True)
    async def status_group(self, ctx):
        await ctx.send("Gunakan: `!status all`, `!status show <nama>`, `!status effects <nama>`")

    @status_group.command(name="all")
    async def status_all(self, ctx):
        guild_id = ctx.guild.id
        rows = fetchall(guild_id, "SELECT * FROM characters")
        for r in rows: inventory_service.calc_carry(guild_id, r["name"])
        await ctx.send(embed=await make_embed(rows, ctx, title="🧍 Semua Status Karakter"))

    @status_group.command(name="show")
    async def status_show(self, ctx, name: str):
        guild_id = ctx.guild.id
        inventory_service.calc_carry(guild_id, name)
        row = fetchone(guild_id, "SELECT * FROM characters WHERE name=%s", (name,))
        if not row: return await ctx.send(f"❌ Karakter {name} tidak ditemukan.")
        await ctx.send(embed=await make_embed([row], ctx, title=f"🧍 Status {name}"), view=StatusView(ctx, row))

    @status_group.command(name="effects")
    async def status_effects(self, ctx, name: str):
        effects, desc = status_service.list_effects(ctx.guild.id, "char", name)
        await ctx.send(desc if desc else f"⚪ {name} tidak punya efek aktif.")

    # ==== Combat (HP) ====
    @commands.command(name="dmg")
    async def status_dmg(self, ctx, name: str, amount: int):
        new_val = await status_service.damage(ctx.guild.id, "char", name, amount)
        await ctx.send(f"💥 {name} menerima {amount} damage → HP sekarang {new_val}")

    @commands.command(name="heal")
    async def status_heal(self, ctx, name: str, amount: int):
        new_val = await status_service.heal(ctx.guild.id, "char", name, amount)
        await ctx.send(f"✨ {name} dipulihkan {amount} HP → HP sekarang {new_val}")

    # ==== Buff & Debuff ====
    @commands.command(name="buff")
    async def add_buff(self, ctx, name: str, *, text: str):
        await status_service.add_effect(ctx.guild.id, "char", name, text, is_buff=True)
        await ctx.send(f"✨ Buff ditambahkan ke {name}: {text}")

    @commands.command(name="debuff")
    async def add_debuff(self, ctx, name: str, *, text: str):
        await status_service.add_effect(ctx.guild.id, "char", name, text, is_buff=False)
        await ctx.send(f"☠️ Debuff ditambahkan ke {name}: {text}")

    # ==== Resource Commands ====
    @commands.command(name="addstm")
    async def stamina_regen(self, ctx, name: str, amount: int):
        new_val = await status_service.use_resource(ctx.guild.id, "char", name, "stamina", amount, regen=True)
        await ctx.send(f"✨ {name} memulihkan {amount} stamina → {new_val}")

    @commands.command(name="usestm")
    async def stamina_use(self, ctx, name: str, amount: int):
        new_val = await status_service.use_resource(ctx.guild.id, "char", name, "stamina", amount)
        await ctx.send(f"⚡ {name} menggunakan {amount} stamina → tersisa {new_val}")

    @commands.command(name="addene")
    async def energy_regen(self, ctx, name: str, amount: int):
        new_val = await status_service.use_resource(ctx.guild.id, "char", name, "energy", amount, regen=True)
        await ctx.send(f"✨ {name} memulihkan {amount} energy → {new_val}")

    @commands.command(name="useene")
    async def energy_use(self, ctx, name: str, amount: int):
        new_val = await status_service.use_resource(ctx.guild.id, "char", name, "energy", amount)
        await ctx.send(f"🔋 {name} menggunakan {amount} energy → tersisa {new_val}")

    # ==== Clear Effects ====
    @commands.command(name="clearbuff")
    async def clear_buff(self, ctx, name: str):
        await status_service.clear_effects(ctx.guild.id, "char", name, is_buff=True)
        await ctx.send(f"✨ Semua buff pada {name} dihapus.")

    @commands.command(name="cleardebuff")
    async def clear_debuff(self, ctx, name: str):
        await status_service.clear_effects(ctx.guild.id, "char", name, is_buff=False)
        await ctx.send(f"☠️ Semua debuff pada {name} dihapus.")

    # ==== Setters, XP, Gold, Party, Remove ====
    @status_group.command(name="set")
    async def status_set(self, ctx, name: str, hp: int, energy: int, stamina: int):
        guild_id = ctx.guild.id
        exists = fetchone(guild_id, "SELECT id FROM characters WHERE name=%s", (name,))
        if not exists:
            execute(guild_id, """
                INSERT INTO characters (guild_id, name, hp, hp_max, energy, energy_max, stamina, stamina_max)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (guild_id, name, hp, hp, energy, energy, stamina, stamina))
        else:
            await status_service.set_status(guild_id, "char", name, "hp", hp)
            await status_service.set_status(guild_id, "char", name, "hp_max", hp)
            await status_service.set_status(guild_id, "char", name, "energy", energy)
            await status_service.set_status(guild_id, "char", name, "energy_max", energy)
            await status_service.set_status(guild_id, "char", name, "stamina", stamina)
            await status_service.set_status(guild_id, "char", name, "stamina_max", stamina)
        await ctx.send(f"✅ Karakter **{name}** diupdate.")

    @status_group.command(name="setcore")
    async def status_setcore(self, ctx, name: str, STR: int, DEX: int, CON: int, INT: int, WIS: int, CHA: int):
        guild_id = ctx.guild.id
        for stat, val in zip(["str","dex","con","int","wis","cha"], [STR,DEX,CON,INT,WIS,CHA]):
            await status_service.set_status(guild_id, "char", name, stat, val)
        await ctx.send(f"✅ Core stats {name} diupdate.")

    @status_group.command(name="setclass")
    async def status_setclass(self, ctx, name: str, *, classname: str):
        await status_service.set_status(ctx.guild.id, "char", name, "class", classname)
        await ctx.send(f"🎓 Class {name} → {classname}")

    @status_group.command(name="setrace")
    async def status_setrace(self, ctx, name: str, *, racename: str):
        await status_service.set_status(ctx.guild.id, "char", name, "race", racename)
        await ctx.send(f"🧬 Race {name} → {racename}")

    @status_group.command(name="setlevel")
    async def status_setlevel(self, ctx, name: str, level: int):
        # level = turunan dari xp. Set level berarti set xp ke ambang awal level tsb,
        # lalu simpan level (sinkron). Tanpa ini, level akan ke-reset saat addxp berikutnya.
        level = max(1, level)
        new_xp = status_service.total_xp_for_level(level)
        execute(ctx.guild.id,
                "UPDATE characters SET xp=%s, level=%s, updated_at=CURRENT_TIMESTAMP WHERE name=%s",
                (new_xp, level, name))
        await ctx.send(f"⬆️ Level {name} → {level} (XP di-set ke {new_xp})")

    @status_group.command(name="setac")
    async def status_setac(self, ctx, name: str, ac: int):
        await status_service.set_status(ctx.guild.id, "char", name, "ac", ac)
        await ctx.send(f"🛡️ AC {name} → {ac}")

    @status_group.command(name="setcarry")
    async def status_setcarry(self, ctx, name: str, capacity: float):
        guild_id = ctx.guild.id
        execute(guild_id, "UPDATE characters SET carry_capacity=%s WHERE name=%s", (capacity, name))
        await ctx.send(f"⚖️ Kapasitas carry {name} → {capacity}")

    # ==== XP & Gold ====
    @status_group.command(name="addxp")
    async def status_addxp(self, ctx, name: str, amount: int):
        level_up = await status_service.add_xp(ctx.guild.id, name, amount)
        if level_up:
            await ctx.send(f"✨ {name} naik ke **Level {level_up}**!")
        else:
            await ctx.send(f"📈 {name} mendapat {amount} XP")

    @status_group.command(name="subxp")
    async def status_subxp(self, ctx, name: str, amount: int):
        guild_id = ctx.guild.id
        row = fetchone(guild_id, "SELECT xp FROM characters WHERE name=%s", (name,))
        if not row:
            return await ctx.send(f"❌ Karakter {name} tidak ditemukan.")
        current = row["xp"] or 0
        new_val = max(0, current - amount)
        new_level, _, _ = status_service.level_from_total_xp(new_val)
        execute(guild_id, "UPDATE characters SET xp=%s, level=%s WHERE name=%s", (new_val, new_level, name))
        await ctx.send(f"📉 {name} kehilangan {amount} XP → sisa {new_val} (Lv {new_level})")

    @status_group.command(name="addgold")
    async def status_addgold(self, ctx, name: str, amount: int):
        await status_service.add_gold(ctx.guild.id, name, amount)
        await ctx.send(f"💰 {name} mendapat {amount} gold")

    @status_group.command(name="subgold")
    async def status_subgold(self, ctx, name: str, amount: int):
        guild_id = ctx.guild.id
        row = fetchone(guild_id, "SELECT gold FROM characters WHERE name=%s", (name,))
        if not row:
            return await ctx.send(f"❌ Karakter {name} tidak ditemukan.")
        current = row["gold"] or 0
        new_val = max(0, current - amount)
        execute(guild_id, "UPDATE characters SET gold=%s WHERE name=%s", (new_val, name))
        await ctx.send(f"💸 {name} mengeluarkan {amount} gold → sisa {new_val}")

    # ==== Party ====
    @commands.command(name="party")
    async def party(self, ctx):
        guild_id = ctx.guild.id
        chars = fetchall(guild_id, "SELECT * FROM characters")
        allies = fetchall(guild_id, "SELECT * FROM allies") if _table_exists(guild_id, "allies") else []
        if not chars and not allies:
            return await ctx.send("ℹ️ Belum ada karakter atau ally.")
        lines = ["🧑‍🤝‍🧑 **Party Status**"]
        for c in chars:
            inventory_service.calc_carry(guild_id, c["name"])
            hp_text = f"{c['hp']}/{c['hp_max']} [{_bar(c['hp'], c['hp_max'])}]"
            en_text = f"{c['energy']}/{c['energy_max']} [{_bar(c['energy'], c['energy_max'])}]"
            st_text = f"{c['stamina']}/{c['stamina_max']} [{_bar(c['stamina'], c['stamina_max'])}]"
            lines.append(f"🧍 **{c['name']}** | ❤️ {hp_text} | 🔋 {en_text} | ⚡ {st_text}")
        for a in allies:
            lines.append(f"🤝 **{a['name']}** | ❤️ {_status_text(a['hp'], a['hp_max'])} | 🔋 {_energy_status(a['energy'], a['energy_max'])} | ⚡ {_stamina_status(a['stamina'], a['stamina_max'])}")
        await ctx.send("\n".join(lines))

    # ==== Remove ====
    @status_group.command(name="remove")
    async def status_remove(self, ctx, name: str):
        guild_id = ctx.guild.id
        row = fetchone(guild_id, "SELECT id FROM characters WHERE name=%s", (name,))
        if not row:
            return await ctx.send(f"❌ Karakter **{name}** tidak ditemukan.")
        execute(guild_id, "DELETE FROM characters WHERE name=%s", (name,))
        await ctx.send(f"🗑️ Karakter **{name}** berhasil dihapus.")

async def setup(bot):
    await bot.add_cog(CharacterStatus(bot))
