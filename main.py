import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from openai import OpenAI

from utils.discord_tools import send_long

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bot")

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DISCORD_TOKEN:
    raise RuntimeError("ENV DISCORD_TOKEN kosong.")
if not OPENAI_API_KEY:
    raise RuntimeError("ENV OPENAI_API_KEY kosong.")
if not DATABASE_URL:
    raise RuntimeError("ENV DATABASE_URL kosong.")

client_gpt = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class MyBot(commands.Bot):
    async def setup_hook(self):
        exts = [
            "cogs.gm_tools",
            "cogs.core.initmem",
            "cogs.core.karakter_status",
            "cogs.core.enemy_status",
            "cogs.core.inventory",
            "cogs.core.history",
            "cogs.core.race_manager",
            "cogs.core.class_manager",
            "cogs.core.shop",
            "cogs.core.effect",
            "cogs.core.companion",
            "cogs.core.ally_status",
            "cogs.core.equipment",
            "cogs.world.quest",
            "cogs.world.npc",
            "cogs.world.favor",
            "cogs.world.scene",
            "cogs.world.item",
            "cogs.world.encyclopedia",
            "cogs.world.timeline",
            "cogs.world.skill",
            "cogs.world.crafting",
            "cogs.world.wiki",
            "cogs.world.hollow",
            "cogs.world.faction",
            "cogs.utility.roll",
            "cogs.utility.db_admin",
            "cogs.utility.poll",
            "cogs.utility.multi",
            "cogs.utility.help_ui",
        ]
        for ext in exts:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded {ext}")
            except Exception as e:
                logger.error(f"Gagal load {ext}: {e}")
                import traceback
                traceback.print_exc()

bot = MyBot(command_prefix=commands.when_mentioned_or("!", "/"),
            intents=intents, help_command=None)
try:
    bot.remove_command("help")
except Exception:
    pass

@bot.event
async def on_ready():
    logger.info(f"Bot login sebagai {bot.user}")
    logger.info(f"Connected to Supabase PostgreSQL")

@bot.event
async def on_guild_join(guild):
    logger.info(f"Joined guild: {guild.name} ({guild.id})")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command tidak dikenal. Coba `!help`.")
    else:
        await ctx.send("Terjadi error, coba lagi nanti.")
        import traceback
        logger.error(f"Error di command {getattr(ctx, 'command', None)}: {error}\n{traceback.format_exc()}")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = None):
    if not prompt:
        await send_long(ctx, "Tolong kasih pertanyaan setelah `!ask`")
        return
    msg = await ctx.send("...")
    try:
        response = client_gpt.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten yang ramah."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
        )
        answer = response.choices[0].message.content
        await send_long(ctx, answer)
    except Exception as e:
        logger.error(f"Error GPT: {e}")
        await send_long(ctx, f"Error: {str(e)}")
    finally:
        try:
            await msg.delete()
        except Exception:
            pass

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
