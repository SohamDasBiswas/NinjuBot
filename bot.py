import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from database import init_db

load_dotenv()
init_db()

# Flask keep-alive
from flask import Flask, jsonify
from threading import Thread

flask_app = Flask('')
start_time = datetime.now(timezone.utc)

@flask_app.route('/')
def home():
    return "✅ NinjuBot is alive!"

@flask_app.route('/health')
def health():
    uptime = datetime.now(timezone.utc) - start_time
    return jsonify({
        "status": "online",
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime": str(uptime).split(".")[0],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# Start Flask in background thread FIRST
t = Thread(target=run_flask)
t.daemon = True
t.start()

print("✅ Flask started")

# Now set up Discord bot
STATUS_CHANNEL_ID = 1484110480699031672

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

async def send_status(title, description, color):
    try:
        channel = bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            channel = await bot.fetch_channel(STATUS_CHANNEL_ID)
        embed = discord.Embed(title=title, description=description, color=color)
        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text="NinjuBot Status")
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Status] Failed: {e}")

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
    await send_status(
        "✅ NinjuBot is Online!",
        f"Bot started successfully.\n**Servers:** {len(bot.guilds)}",
        0x2ECC71
    )

@bot.event
async def on_resumed():
    print("✅ Bot reconnected!")
    await send_status("🔄 NinjuBot Reconnected", "Bot reconnected to Discord.", 0x3498DB)

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

async def start_bot():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!")
        return

    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  ✅ {cog}")
        except Exception as e:
            print(f"  ❌ {cog}: {e}")

    retry_delay = 30
    while True:
        try:
            print("🔄 Attempting to connect to Discord...")
            await bot.start(token)
            break
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"⚠️ Rate limited. Waiting {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 600)
                try:
                    await bot.close()
                except:
                    pass
            else:
                print(f"❌ HTTP error: {e}")
                await asyncio.sleep(60)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            await asyncio.sleep(60)

asyncio.run(start_bot())
