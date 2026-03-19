import discord
from discord.ext import commands, tasks
import aiohttp
import os
<<<<<<< HEAD
from database import get_conn

TWITCH_USERNAME = "sdb_darkninja"

def init_twitch_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS twitch_channels (
            guild_id TEXT PRIMARY KEY,
            followers_vc TEXT,
            status_vc TEXT,
            viewers_vc TEXT,
            game_vc TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_channel_ids():
    init_twitch_table()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM twitch_channels").fetchall()
    conn.close()
    result = {}
    for row in rows:
        result[int(row["guild_id"])] = {
            "followers": int(row["followers_vc"]),
            "status":    int(row["status_vc"]),
            "viewers":   int(row["viewers_vc"]),
            "game":      int(row["game_vc"]),
        }
    return result

def save_channel_ids(guild_id, ids):
    init_twitch_table()
    conn = get_conn()
    conn.execute("""
        INSERT INTO twitch_channels (guild_id, followers_vc, status_vc, viewers_vc, game_vc)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            followers_vc=excluded.followers_vc,
            status_vc=excluded.status_vc,
            viewers_vc=excluded.viewers_vc,
            game_vc=excluded.game_vc
    """, (str(guild_id), str(ids["followers"]), str(ids["status"]),
          str(ids["viewers"]), str(ids["game"])))
    conn.commit()
    conn.close()
=======
import json

TWITCH_USERNAME = "sdb_darkninja"
DATA_FILE = "twitch_channels.json"

def load_channel_ids():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}

def save_channel_ids(data):
    with open(DATA_FILE, "w") as f:
        json.dump({str(k): v for k, v in data.items()}, f)
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450

class Twitch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.access_token = None
        self.channel_ids = load_channel_ids()

    async def get_token(self):
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        if not client_id or not client_secret:
            return None
        async with aiohttp.ClientSession() as s:
            resp = await s.post("https://id.twitch.tv/oauth2/token", params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials"
            })
            data = await resp.json()
            return data.get("access_token")

    async def get_twitch_stats(self):
        client_id = os.getenv("TWITCH_CLIENT_ID")
        if not client_id:
            return None, "❌ `TWITCH_CLIENT_ID` missing from `.env`."
        if not self.access_token:
            self.access_token = await self.get_token()
        if not self.access_token:
            return None, "❌ Could not get Twitch token. Check `.env`."
<<<<<<< HEAD
=======

>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
        headers = {
            "Client-ID": client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        try:
            async with aiohttp.ClientSession() as s:
                resp = await s.get(f"https://api.twitch.tv/helix/users?login={TWITCH_USERNAME}", headers=headers)
                user_data = await resp.json()
                if not user_data.get("data"):
                    return None, f"❌ Twitch user `{TWITCH_USERNAME}` not found."
                user = user_data["data"][0]
                user_id = user["id"]
<<<<<<< HEAD
                resp2 = await s.get(f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={user_id}", headers=headers)
                followers = (await resp2.json()).get("total", 0)
                resp3 = await s.get(f"https://api.twitch.tv/helix/streams?user_login={TWITCH_USERNAME}", headers=headers)
                stream_data = await resp3.json()
                stream = stream_data["data"][0] if stream_data.get("data") else None
=======

                resp2 = await s.get(f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={user_id}", headers=headers)
                followers = (await resp2.json()).get("total", 0)

                resp3 = await s.get(f"https://api.twitch.tv/helix/streams?user_login={TWITCH_USERNAME}", headers=headers)
                stream_data = await resp3.json()
                stream = stream_data["data"][0] if stream_data.get("data") else None

>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
                return {
                    "username": user["display_name"],
                    "followers": followers,
                    "is_live": stream is not None,
                    "viewers": stream["viewer_count"] if stream else 0,
                    "game": stream["game_name"] if stream else "Offline",
                    "title": stream["title"] if stream else "—",
                }, None
        except Exception as e:
            return None, f"❌ Twitch API error: {e}"

<<<<<<< HEAD
=======
    # ── -twitchsetup [category_id] ────────────────────────────────────────────
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
    @commands.command(name="twitchsetup")
    @commands.has_permissions(administrator=True)
    async def twitch_setup(self, ctx, category_id: int = None):
        msg = await ctx.send("⏳ Setting up Twitch analytics channels...")
        stats, error = await self.get_twitch_stats()
        if not stats:
            return await msg.edit(content=error)

        guild = ctx.guild
<<<<<<< HEAD

        # If channels already exist in DB and are still valid, just update
        if guild.id in self.channel_ids:
            ids = self.channel_ids[guild.id]
            existing = all(guild.get_channel(v) is not None for v in ids.values())
            if existing:
                await self.do_update(stats)
                return await msg.edit(content=None, embed=discord.Embed(
                    title="✅ Already Set Up!",
                    description="Existing channels updated with latest stats. No new channels created.",
                    color=0x9146FF
                ))

=======
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
        category = None
        if category_id:
            category = guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                return await msg.edit(content=f"❌ Category `{category_id}` not found.")
        if not category:
            category = await guild.create_category("📊 Twitch Analytics")

<<<<<<< HEAD
        overwrite = {guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
        followers_vc = await guild.create_voice_channel(f"🪻 | Followers : {stats['followers']:,}", category=category, overwrites=overwrite)
        status_vc    = await guild.create_voice_channel("🪻 | Status : 🔴 LIVE" if stats["is_live"] else "🪻 | Status : ⚫ Offline", category=category, overwrites=overwrite)
        viewers_vc   = await guild.create_voice_channel(f"🪻 | Viewers : {stats['viewers']:,}", category=category, overwrites=overwrite)
        game_vc      = await guild.create_voice_channel(f"🪻 | Game : {stats['game'][:28]}", category=category, overwrites=overwrite)

        ids = {
=======
        followers_vc = await guild.create_voice_channel(f"🪻 | Followers : {stats['followers']:,}", category=category)
        status_vc    = await guild.create_voice_channel("🪻 | Status : 🔴 LIVE" if stats["is_live"] else "🪻 | Status : ⚫ Offline", category=category)
        viewers_vc   = await guild.create_voice_channel(f"🪻 | Viewers : {stats['viewers']:,}", category=category)
        game_vc      = await guild.create_voice_channel(f"🪻 | Game : {stats['game'][:28]}", category=category)

        overwrite = {guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
        for vc in [followers_vc, status_vc, viewers_vc, game_vc]:
            await vc.edit(overwrites=overwrite)

        self.channel_ids[guild.id] = {
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
            "followers": followers_vc.id,
            "status":    status_vc.id,
            "viewers":   viewers_vc.id,
            "game":      game_vc.id,
        }
<<<<<<< HEAD
        self.channel_ids[guild.id] = ids
        save_channel_ids(guild.id, ids)

        embed = discord.Embed(
            title="✅ Twitch Analytics Ready!",
            description=(f"📊 Tracking **{stats['username']}**\n📁 Category: **{category.name}**\n\nChannels auto-update every **5 minutes**."),
=======
        save_channel_ids(self.channel_ids)

        embed = discord.Embed(
            title="✅ Twitch Analytics Ready!",
            description=(
                f"📊 Tracking **{stats['username']}**\n"
                f"📁 Category: **{category.name}**\n\n"
                f"Channels auto-update every **5 minutes**."
            ),
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
            color=0x9146FF
        )
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja")
        await msg.edit(content=None, embed=embed)
        if not self.update_twitch_channels.is_running():
            self.update_twitch_channels.start()

<<<<<<< HEAD
=======
    # ── -twitchstats ──────────────────────────────────────────────────────────
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
    @commands.command(name="twitchstats", aliases=["twitch"])
    async def twitch_stats(self, ctx):
        msg = await ctx.send("⏳ Fetching Twitch stats...")
        stats, error = await self.get_twitch_stats()
        if not stats:
            return await msg.edit(content=error)
<<<<<<< HEAD
        await self.do_update(stats)
=======

        await self.do_update(stats)

>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
        status = "🔴 **LIVE**" if stats["is_live"] else "⚫ **Offline**"
        embed = discord.Embed(title=f"📊 Twitch Stats — {stats['username']}", color=0x9146FF if stats["is_live"] else 0x666666)
        embed.add_field(name="Status",       value=status,                   inline=True)
        embed.add_field(name="🪻 Followers", value=f"{stats['followers']:,}", inline=True)
        embed.add_field(name="🪻 Viewers",   value=f"{stats['viewers']:,}",   inline=True)
        embed.add_field(name="🪻 Game",      value=stats["game"],             inline=True)
        if stats["is_live"]:
            embed.add_field(name="📺 Title", value=stats["title"][:100], inline=False)
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja | Channels updated!")
        await msg.edit(content=None, embed=embed)

<<<<<<< HEAD
    @commands.command(name="twitchreset")
    @commands.has_permissions(administrator=True)
    async def twitch_reset(self, ctx):
        """Delete saved channel IDs — use before running twitchsetup fresh."""
        guild = ctx.guild
        if guild.id in self.channel_ids:
            del self.channel_ids[guild.id]
            conn = get_conn()
            conn.execute("DELETE FROM twitch_channels WHERE guild_id=?", (str(guild.id),))
            conn.commit()
            conn.close()
            await ctx.send("✅ Reset done. Run `-twitchsetup` to create fresh channels.")
        else:
            await ctx.send("⚠️ No Twitch setup found for this server.")

=======
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
    async def do_update(self, stats):
        for guild_id, ids in self.channel_ids.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            try:
                ch = guild.get_channel(ids["followers"])
                if ch: await ch.edit(name=f"🪻 | Followers : {stats['followers']:,}")
                ch = guild.get_channel(ids["status"])
                if ch: await ch.edit(name="🪻 | Status : 🔴 LIVE" if stats["is_live"] else "🪻 | Status : ⚫ Offline")
                ch = guild.get_channel(ids["viewers"])
                if ch: await ch.edit(name=f"🪻 | Viewers : {stats['viewers']:,}")
                ch = guild.get_channel(ids["game"])
                if ch: await ch.edit(name=f"🪻 | Game : {stats['game'][:28]}")
            except Exception as e:
<<<<<<< HEAD
                print(f"[Twitch] Update failed for guild {guild_id}: {e}")
=======
                print(f"[Twitch] Update failed: {e}")
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450

    @tasks.loop(minutes=5)
    async def update_twitch_channels(self):
        stats, _ = await self.get_twitch_stats()
        if stats:
            await self.do_update(stats)

    @update_twitch_channels.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
<<<<<<< HEAD
        self.channel_ids = load_channel_ids()
=======
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450
        if self.channel_ids and not self.update_twitch_channels.is_running():
            self.update_twitch_channels.start()

async def setup(bot):
    await bot.add_cog(Twitch(bot))
