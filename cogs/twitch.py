import discord
from discord.ext import commands, tasks
import aiohttp
import os

TWITCH_USERNAME = "sdb_darkninja"

# ── In-memory store (loaded lazily from MongoDB) ──────────────────────────────
_channel_ids = {}

def _get_db():
    from database import get_db
    return get_db()

def _load():
    try:
        db = _get_db()
        docs = db.twitch_channels.find({})
        result = {}
        for doc in docs:
            result[int(doc["guild_id"])] = {
                "followers": int(doc["followers_vc"]),
                "status":    int(doc["status_vc"]),
                "viewers":   int(doc["viewers_vc"]),
                "game":      int(doc["game_vc"]),
            }
        return result
    except Exception as e:
        print(f"[Twitch] DB load failed (non-fatal): {e}")
        return {}

def _save(guild_id, ids):
    try:
        db = _get_db()
        db.twitch_channels.update_one(
            {"guild_id": str(guild_id)},
            {"$set": {
                "guild_id":     str(guild_id),
                "followers_vc": str(ids["followers"]),
                "status_vc":    str(ids["status"]),
                "viewers_vc":   str(ids["viewers"]),
                "game_vc":      str(ids["game"]),
            }},
            upsert=True
        )
    except Exception as e:
        print(f"[Twitch] DB save failed: {e}")

def _delete(guild_id):
    try:
        db = _get_db()
        db.twitch_channels.delete_one({"guild_id": str(guild_id)})
    except Exception as e:
        print(f"[Twitch] DB delete failed: {e}")

class Twitch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.access_token = None
        self.channel_ids = {}  # loaded after bot is ready

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
            return None, "❌ `TWITCH_CLIENT_ID` missing."
        if not self.access_token:
            self.access_token = await self.get_token()
        if not self.access_token:
            return None, "❌ Could not get Twitch token."
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.access_token}"}
        try:
            async with aiohttp.ClientSession() as s:
                resp = await s.get(f"https://api.twitch.tv/helix/users?login={TWITCH_USERNAME}", headers=headers)
                user_data = await resp.json()
                if not user_data.get("data"):
                    return None, f"❌ Twitch user `{TWITCH_USERNAME}` not found."
                user = user_data["data"][0]
                user_id = user["id"]
                resp2 = await s.get(f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={user_id}", headers=headers)
                followers = (await resp2.json()).get("total", 0)
                resp3 = await s.get(f"https://api.twitch.tv/helix/streams?user_login={TWITCH_USERNAME}", headers=headers)
                stream_data = await resp3.json()
                stream = stream_data["data"][0] if stream_data.get("data") else None
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

    @commands.command(name="twitchsetup")
    @commands.has_permissions(administrator=True)
    async def twitch_setup(self, ctx, category_id: int = None):
        msg = await ctx.send("⏳ Setting up Twitch analytics channels...")
        stats, error = await self.get_twitch_stats()
        if not stats:
            return await msg.edit(content=error)
        guild = ctx.guild
        if guild.id in self.channel_ids:
            ids = self.channel_ids[guild.id]
            if all(guild.get_channel(v) is not None for v in ids.values()):
                await self.do_update(stats)
                return await msg.edit(content=None, embed=discord.Embed(
                    title="✅ Already Set Up!",
                    description="Existing channels updated. No new channels created.",
                    color=0x9146FF
                ))
        category = None
        if category_id:
            category = guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                return await msg.edit(content=f"❌ Category `{category_id}` not found.")
        if not category:
            category = await guild.create_category("📊 Twitch Analytics")
        overwrite = {guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
        followers_vc = await guild.create_voice_channel(f"🪻 | Followers : {stats['followers']:,}", category=category, overwrites=overwrite)
        status_vc    = await guild.create_voice_channel("🪻 | Status : 🔴 LIVE" if stats["is_live"] else "🪻 | Status : ⚫ Offline", category=category, overwrites=overwrite)
        viewers_vc   = await guild.create_voice_channel(f"🪻 | Viewers : {stats['viewers']:,}", category=category, overwrites=overwrite)
        game_vc      = await guild.create_voice_channel(f"🪻 | Game : {stats['game'][:28]}", category=category, overwrites=overwrite)
        ids = {"followers": followers_vc.id, "status": status_vc.id, "viewers": viewers_vc.id, "game": game_vc.id}
        self.channel_ids[guild.id] = ids
        _save(guild.id, ids)
        embed = discord.Embed(title="✅ Twitch Analytics Ready!", description=f"📊 Tracking **{stats['username']}**\n📁 Category: **{category.name}**\n\nChannels auto-update every **5 minutes**.", color=0x9146FF)
        embed.set_footer(text="NinjuBot | Made by sdb_darkninja")
        await msg.edit(content=None, embed=embed)
        if not self.update_twitch_channels.is_running():
            self.update_twitch_channels.start()

    @commands.command(name="twitchstats", aliases=["twitch"])
    async def twitch_stats(self, ctx):
        msg = await ctx.send("⏳ Fetching Twitch stats...")
        stats, error = await self.get_twitch_stats()
        if not stats:
            return await msg.edit(content=error)
        await self.do_update(stats)
        status = "🔴 **LIVE**" if stats["is_live"] else "⚫ **Offline**"
        embed = discord.Embed(title=f"📊 Twitch Stats — {stats['username']}", color=0x9146FF if stats["is_live"] else 0x666666)
        embed.add_field(name="Status",       value=status,                   inline=True)
        embed.add_field(name="🪻 Followers", value=f"{stats['followers']:,}", inline=True)
        embed.add_field(name="🪻 Viewers",   value=f"{stats['viewers']:,}",   inline=True)
        embed.add_field(name="🪻 Game",      value=stats["game"],             inline=True)
        if stats["is_live"]:
            embed.add_field(name="📺 Title", value=stats["title"][:100], inline=False)
        embed.set_footer(text="NinjuBot | Made by sdb_darkninja | Channels updated!")
        await msg.edit(content=None, embed=embed)

    @commands.command(name="twitchreset")
    @commands.has_permissions(administrator=True)
    async def twitch_reset(self, ctx):
        guild = ctx.guild
        if guild.id in self.channel_ids:
            del self.channel_ids[guild.id]
            _delete(guild.id)
            await ctx.send("✅ Reset done. Run `-twitchsetup` to create fresh channels.")
        else:
            await ctx.send("⚠️ No Twitch setup found for this server.")

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
                print(f"[Twitch] Update failed for guild {guild_id}: {e}")

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
        self.channel_ids = _load()
        if self.channel_ids and not self.update_twitch_channels.is_running():
            self.update_twitch_channels.start()

async def setup(bot):
    await bot.add_cog(Twitch(bot))
