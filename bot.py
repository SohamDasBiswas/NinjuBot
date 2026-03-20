import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from database import init_db

print("🚀 NinjuBot starting...", flush=True)
load_dotenv()
init_db()

from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Thread

flask_app = Flask('')
CORS(flask_app)
start_time = datetime.now(timezone.utc)
_bot_ref = None

@flask_app.route('/')
def home():
    return "✅ NinjuBot is alive!"

@flask_app.route('/health')
def health():
    uptime = datetime.now(timezone.utc) - start_time
    guilds = len(_bot_ref.guilds) if _bot_ref and _bot_ref.is_ready() else 0
    users = sum(g.member_count for g in _bot_ref.guilds) if _bot_ref and _bot_ref.is_ready() else 0
    return jsonify({
        "status": "online" if (_bot_ref and _bot_ref.is_ready()) else "starting",
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime": str(uptime).split(".")[0],
        "guilds": guilds,
        "users": users,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@flask_app.route('/stats')
def stats():
    if not _bot_ref or not _bot_ref.is_ready():
        return jsonify({"error": "Bot not ready"}), 503
    guilds = []
    for g in _bot_ref.guilds:
        guilds.append({
            "id": str(g.id),
            "name": g.name,
            "members": g.member_count,
            "icon": str(g.icon.url) if g.icon else None,
        })
    return jsonify({
        "bot_name": str(_bot_ref.user),
        "bot_id": str(_bot_ref.user.id),
        "avatar": str(_bot_ref.user.display_avatar.url),
        "guild_count": len(_bot_ref.guilds),
        "user_count": sum(g.member_count for g in _bot_ref.guilds),
        "guilds": guilds,
        "uptime": str(datetime.now(timezone.utc) - start_time).split(".")[0],
    })

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

t = Thread(target=run_flask)
t.daemon = True
t.start()
print("✅ Flask thread started", flush=True)

STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "1484110480699031672"))

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

def make_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.members = True
    intents.presences = True
    return commands.Bot(
        command_prefix=os.getenv("BOT_PREFIX", "-"),
        intents=intents,
        help_command=None,
        max_messages=1000,
        chunk_guilds_at_startup=False,
    )

async def start_bot():
    global _bot_ref
    print("🔄 start_bot() called", flush=True)
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        return

    retry_delay = 30

    while True:
        bot = make_bot()
        _bot_ref = bot

        async def send_status(title, description, color):
            try:
                channel = bot.get_channel(STATUS_CHANNEL_ID)
                if not channel:
                    channel = await bot.fetch_channel(STATUS_CHANNEL_ID)
                embed = discord.Embed(title=title, description=description, color=color)
                embed.timestamp = datetime.now(timezone.utc)
                embed.set_footer(text="NinjuBot Status System")
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[Status] Failed: {e}", flush=True)

        @bot.event
        async def on_ready():
            print(f"✅ Logged in as {bot.user} ({bot.user.id})", flush=True)
            print(f"📡 Connected to {len(bot.guilds)} server(s)", flush=True)
            try:
                synced = await bot.tree.sync()
                print(f"✅ Synced {len(synced)} global slash command(s)", flush=True)
            except Exception as e:
                print(f"❌ Slash sync failed: {e}", flush=True)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"-ninju | {len(bot.guilds)} servers"
                )
            )
            await send_status(
                "✅ NinjuBot is Online!",
                f"**Servers:** {len(bot.guilds)}\n**Users:** {sum(g.member_count for g in bot.guilds):,}",
                0x2ECC71
            )

        @bot.event
        async def on_guild_join(guild):
            print(f"➕ Joined: {guild.name} ({guild.id})", flush=True)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"-ninju | {len(bot.guilds)} servers"
                )
            )
            # Send welcome embed to first available text channel
            embed = discord.Embed(
                title="🥷 Hey! I'm NinjuBot!",
                description=(
                    "Thanks for adding me to **{}**!\n\n"
                    "**Getting Started:**\n"
                    "📖 `-ninju` — View all commands\n"
                    "🎵 `/play <song>` — Play music\n"
                    "💰 `-daily` — Claim daily coins\n"
                    "🎭 `-tod @user` — Truth or Dare\n"
                    "🤖 `-ask <question>` — Chat with AI\n\n"
                    "**Need help?** Use `-ninju` to see all commands!"
                ).format(guild.name),
                color=0xFF4500
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="NinjuBot | Made by sdb_darkninja")
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    try:
                        await ch.send(embed=embed)
                        break
                    except:
                        continue

        @bot.event
        async def on_guild_remove(guild):
            print(f"➖ Left: {guild.name} ({guild.id})", flush=True)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"-ninju | {len(bot.guilds)} servers"
                )
            )

        @bot.event
        async def on_resumed():
            print("✅ Bot reconnected!", flush=True)
            await send_status("🔄 NinjuBot Reconnected", "Bot reconnected to Discord.", 0x3498DB)

        @bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                return
            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(f"❌ Missing: `{error.param.name}`. Use `-ninju` for help.")
            elif isinstance(error, commands.MissingPermissions):
                await ctx.send("❌ You don't have permission to do that.")
            elif isinstance(error, commands.BotMissingPermissions):
                await ctx.send("❌ I don't have permission to do that.")
            elif isinstance(error, commands.CommandOnCooldown):
                await ctx.send(f"⏳ Cooldown! Try again in `{error.retry_after:.1f}s`.")
            elif isinstance(error, commands.CommandInvokeError):
                if isinstance(error.original, asyncio.TimeoutError):
                    return
                print(f"[CmdError] {error}", flush=True)

        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✅ {cog}", flush=True)
            except Exception as e:
                print(f"  ❌ {cog}: {e}", flush=True)

        try:
            print("🔄 Attempting to connect to Discord...", flush=True)
            await bot.start(token)
            break
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"⚠️ Rate limited. Waiting {retry_delay}s...", flush=True)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 600)
            else:
                print(f"❌ HTTP error: {e}", flush=True)
                await asyncio.sleep(60)
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(60)

print("▶️ Calling asyncio.run(start_bot())", flush=True)
asyncio.run(start_bot())
