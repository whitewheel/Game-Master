# cogs/core/initmem.py
import asyncio
import json
import random
import re
import discord
from discord.ext import commands

from utils.db import execute, fetchone, fetchall

# ===============================
# DB Helpers & Setup
# ===============================

def _ensure_tables(guild_id: int):
    # Schema sudah ada di Supabase
    pass

def _load_initiative(guild_id: int):
    row = fetchone(guild_id, "SELECT * FROM initiative LIMIT 1")
    if not row:
        return {"order": [], "ptr": 0, "round": 1}
    try:
        order = json.loads(row.get("order_json") or "[]")
    except Exception:
        order = []
    return {
        "order": [(n, int(s)) for (n, s) in order],
        "ptr": int(row["ptr"] or 0),
        "round": int(row["round"] or 1)
    }

def _save_initiative(guild_id: int, state: dict):
    order_json = json.dumps(state.get("order", []))
    ptr = int(state.get("ptr", 0))
    rnd = int(state.get("round", 1))
    execute(guild_id, """
    INSERT INTO initiative (id, order_json, ptr, round)
    VALUES (1,%s,%s,%s)
    ON CONFLICT(id)
    DO UPDATE SET order_json=excluded.order_json,
                  ptr=excluded.ptr,
                  round=excluded.round,
                  updated_at=CURRENT_TIMESTAMP;
    """, (order_json, ptr, rnd))

def _clear_initiative(guild_id: int):
    execute(guild_id, "DELETE FROM initiative")

# ===============================
# Utils
# ===============================

def _sorted_order(arr):
    return sorted(arr, key=lambda x: (-int(x[1]), x[0].lower()))

def _make_embed(ctx, title: str, s: dict, highlight: bool = True):
    order = s.get("order", [])
    ptr = s.get("ptr", 0)
    rnd = s.get("round", 1)

    embed = discord.Embed(
        title=title,
        description=f"📜 Round **{rnd}** • Total Peserta: **{len(order)}**",
        color=discord.Color.red()
    )

    if not order:
        embed.add_field(name="⚔️ Initiative Order", value="(kosong)", inline=False)
        embed.set_footer(text="Tambahkan peserta dengan !init add <Nama> <Skor>")
        return embed

    lines = []
    for i, (name, score) in enumerate(order):
        if highlight and i == ptr:
            marker = "🔥"
            lines.append(f"{marker} **{i+1}. {name}** ({score}) ← Giliran")
        else:
            marker = "⏳"
            lines.append(f"{marker} {i+1}. {name} ({score})")

    embed.add_field(name="⚔️ Initiative Order", value="\n".join(lines), inline=False)
    embed.set_footer(text="Gunakan !init next / !next untuk lanjut giliran.")
    return embed

# ===============================
# Cog
# ===============================

class InitiativeMemory(commands.Cog):
    """
    Initiative tracker per server.
    """
    def __init__(self, bot):
        self.bot = bot
        self.state = {}

    # ---------- internal helpers ----------
    def _ensure_state(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.state:
            _ensure_tables(guild_id)
            self.state[guild_id] = _load_initiative(guild_id)
        return self.state[guild_id]

    def _persist(self, ctx):
        guild_id = ctx.guild.id
        _save_initiative(guild_id, self.state[guild_id])

    # ---------- group ----------
    @commands.group(name="init", invoke_without_command=True)
    async def init_group(self, ctx):
        embed = discord.Embed(
            title="📖 Initiative Commands",
            description=(
                "• `!init add <Nama> <Skor>`\n"
                "• `!init addmany \"Alice 18, Goblin 12, Borin 14\"`\n"
                "• `!init show`   (alias: `!order`)\n"
                "• `!init next`   (alias: `!next` / `!n`)\n"
                "• `!init setptr <index>` (mulai dari 1)\n"
                "• `!init remove <Nama>`\n"
                "• `!init clear`\n"
                "• `!init shuffle`\n"
                "• `!init round [angka]`\n"
                "• `!engage` / `!victory`"
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    # ---------- add ----------
    @init_group.command(name="add")
    async def init_add(self, ctx, name: str, score: int):
        s = self._ensure_state(ctx)
        existing = {n: sc for (n, sc) in s["order"]}
        existing[name] = int(score)
        s["order"] = _sorted_order(list(existing.items()))
        s["ptr"] = s["ptr"] % len(s["order"]) if s["order"] else 0
        self._persist(ctx)

        embed = discord.Embed(
            title="✅ Peserta Ditambahkan / Diupdate",
            description=f"**{name}** = `{score}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @init_group.command(name="addmany")
    async def init_addmany(self, ctx, *, entries: str = None):
        if entries is None:
            raw = ctx.message.content
            idx = raw.lower().find("addmany")
            entries = raw[idx + len("addmany"):].strip() if idx != -1 else ""

        if not entries:
            return await ctx.send("⚠️ Format: `!init addmany Alice 18, Goblin 12`")

        s = self._ensure_state(ctx)
        existing = {n: sc for (n, sc) in s["order"]}
        chunks = [c.strip() for c in re.split(r'[,\n;|]+', entries) if c.strip()]
        added = 0
        skipped = []

        for ch in chunks:
            m = re.match(r'^(%sP<name>.+%s)\s+(%sP<score>-?\d+)\s*$', ch)
            if not m:
                skipped.append(ch)
                continue
            name = m.group('name').strip()
            score = int(m.group('score'))
            existing[name] = score
            added += 1

        s["order"] = _sorted_order(list(existing.items()))
        s["ptr"] = s["ptr"] % len(s["order"]) if s["order"] else 0

        desc = f"✅ Ditambahkan / diupdate **{added}** peserta."
        if skipped:
            preview = ", ".join(skipped[:5]) + (" ..." if len(skipped) > 5 else "")
            desc += f"\n⚠️ Di-skip: {preview}"

        self._persist(ctx)
        embed = discord.Embed(
            title="📥 Add Many",
            description=desc,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    # ---------- remove / clear ----------
    @init_group.command(name="remove")
    async def init_remove(self, ctx, name: str):
        s = self._ensure_state(ctx)
        before = len(s["order"])
        s["order"] = [(n, sc) for (n, sc) in s["order"] if n.lower() != name.lower()]
        if len(s["order"]) < before:
            s["ptr"] = s["ptr"] % len(s["order"]) if s["order"] else 0
            self._persist(ctx)
            embed = discord.Embed(
                title="🗑️ Peserta Dihapus",
                description=f"**{name}** dihapus dari urutan.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("⚠️ Nama tidak ditemukan.")

    @init_group.command(name="clear")
    async def init_clear(self, ctx):
        guild_id = ctx.guild.id
        self.state[guild_id] = {"order": [], "ptr": 0, "round": 1}
        self._persist(ctx)
        embed = discord.Embed(
            title="🧹 Initiative Reset",
            description="Semua peserta dihapus. Urutan kosong.",
            color=discord.Color.dark_gray()
        )
        await ctx.send(embed=embed)

    # ---------- show / order ----------
    @init_group.command(name="show")
    async def init_show(self, ctx):
        guild_id = ctx.guild.id
        self.state[guild_id] = _load_initiative(guild_id)
        s = self._ensure_state(ctx)
        self._persist(ctx)
        embed = _make_embed(ctx, "⚔️ Initiative Order", s)
        await ctx.send(embed=embed)

    # ---------- next / setptr / round / shuffle ----------
    @init_group.command(name="next")
    async def init_next(self, ctx):
        s = self._ensure_state(ctx)
        if not s["order"]:
            return await ctx.send("⚠️ Belum ada peserta.")

        s["ptr"] = (s["ptr"] + 1) % len(s["order"])
        if s["ptr"] == 0:
            s["round"] += 1
            await ctx.send(f"🔄 **Round {s['round']} dimulai!**")

        self._persist(ctx)
        embed = _make_embed(ctx, "⏭️ Initiative Next", s)
        current = s["order"][s["ptr"]][0]
        embed.add_field(name="Giliran Saat Ini", value=f"✨ **{current}**", inline=False)
        await ctx.send(embed=embed)

    @init_group.command(name="setptr")
    async def init_setptr(self, ctx, index: int):
        s = self._ensure_state(ctx)
        if not s["order"]:
            return await ctx.send("⚠️ Belum ada peserta.")
        idx = max(1, min(index, len(s["order"]))) - 1
        s["ptr"] = idx
        self._persist(ctx)
        embed = _make_embed(ctx, "📌 Pointer Diset Manual", s)
        await ctx.send(embed=embed)

    @init_group.command(name="round")
    async def init_round(self, ctx, value: int = None):
        s = self._ensure_state(ctx)
        if value is None:
            return await ctx.send(f"📜 Round saat ini: **{s['round']}**")
        s["round"] = max(1, int(value))
        self._persist(ctx)
        await ctx.send(f"📜 Round diset ke **{s['round']}**")

    @init_group.command(name="shuffle")
    async def init_shuffle(self, ctx):
        s = self._ensure_state(ctx)
        if not s["order"]:
            return await ctx.send("⚠️ Belum ada peserta.")
        s["ptr"] = random.randint(0, len(s["order"]) - 1)
        self._persist(ctx)
        embed = _make_embed(ctx, "🎲 Shuffle Giliran", s)
        current = s["order"][s["ptr"]][0]
        embed.add_field(name="Giliran Pertama", value=f"👉 **{current}**", inline=False)
        await ctx.send(embed=embed)

    # ---------- Engage / Victory ----------
    @commands.command(name="engage", aliases=["start", "begin"])
    async def engage(self, ctx):
        s = self._ensure_state(ctx)
        if not s["order"]:
            return await ctx.send("⚠️ Belum ada data initiative.")
        drum = await ctx.send("🥁 Mengocok urutan giliran...")
        await asyncio.sleep(2)
        try:
            await drum.delete()
        except Exception:
            pass

        self._persist(ctx)
        embed = _make_embed(ctx, "⚔️ Encounter Dimulai!", s)
        current = s["order"][s["ptr"]][0]
        embed.add_field(name="Giliran Pertama", value=f"👉 **{current}**", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="victory", aliases=["end", "finish", "win"])
    async def victory(self, ctx, *flags):
        flags = {f.lower() for f in flags}
        keep_enemies = "keep" in flags
        force_end = "force" in flags

        s = self._ensure_state(ctx)
        order = s.get("order", [])
        ptr = s.get("ptr", 0)
        rnd = s.get("round", 1)
        current_turn = order[ptr][0] if order else "-"

        guild_id = ctx.guild.id
        enemies = fetchall(guild_id, "SELECT name, hp FROM enemies")
        total = len(enemies)
        alive = sum(1 for e in enemies if int(e["hp"] or 0) > 0)
        defeated = total - alive

        if alive > 0 and not force_end:
            return await ctx.send(
                f"⚠️ Masih ada **{alive}** musuh hidup. "
                "Gunakan `!victory force` untuk memaksa."
            )

        embed = discord.Embed(
            title="🎉 Victory!",
            description="Pertempuran berakhir dengan kemenangan!",
            color=discord.Color.green()
        )
        embed.add_field(name="👹 Musuh", value=f"Total: {total} • Alive: {alive} • Defeated: {defeated}", inline=False)
        embed.add_field(name="📜 Round Terakhir", value=str(rnd), inline=True)
        embed.add_field(name="✨ Giliran Terakhir", value=current_turn, inline=True)

        self.state[guild_id] = {"order": [], "ptr": 0, "round": 1}
        self._persist(ctx)

        if not keep_enemies:
            execute(guild_id, "DELETE FROM enemies")

        await ctx.send(embed=embed)

    # ---------- Aliases ----------
    @commands.command(name="next", aliases=["n"])
    async def alias_next(self, ctx):
        await self.init_next(ctx)

    @commands.command(name="order")
    async def alias_order(self, ctx):
        await self.init_show(ctx)

# ===============================
# Setup
# ===============================
async def setup(bot):
    cog = InitiativeMemory(bot)
    await bot.add_cog(cog)
