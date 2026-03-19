import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import init_db

load_dotenv()

# Initialize database on startup
init_db()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.presences = True

bot = commands.Bot(
    command_prefix="-",
    intents=intents,
    help_command=None,
    max_messages=500,
    chunk_guilds_at_startup=False,
)

COGS = [
    "cogs.music",
    "cogs.music_extras",
    "cogs.twitch",
    "cogs.ai",
    "cogs.levels",
    "cogs.fun",
    "cogs.images",
    "cogs.currency",
    "cogs.info",
]

MY_GUILD = discord.Object(id=1342866797958926368)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    print(f"📡 Connected to {len(bot.guilds)} server(s)")
    try:
        bot.tree.copy_global_to(guild=MY_GUILD)
        synced = await bot.tree.sync(guild=MY_GUILD)
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Slash sync failed: {e}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="/play | sdb_darkninja"
        )
    )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing: `{error.param.name}`. Use `-help`.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission.")
    elif isinstance(error, commands.CommandInvokeError):
        if isinstance(error.original, asyncio.TimeoutError):
            return
        await ctx.send(f"❌ {str(error.original)}")
    else:
        return

async def main():
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✅ {cog}")
            except Exception as e:
                print(f"  ❌ {cog}: {e}")
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("DISCORD_TOKEN not set!")
        await bot.start(token)

keep_alive()
asyncio.run(main())
