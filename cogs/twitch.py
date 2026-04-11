"""
cogs/twitch.py — Twitch Stats VC updater for NinjuBot

All configuration lives in MongoDB `guild_settings` (shared with the dashboard):
  tw_username       — Twitch username to track
  tw_stats_vc       — bool: whether stats VCs are enabled
  tw_vc_followers   — Discord voice channel ID (string)
  tw_vc_status      — Discord voice channel ID (string)
  tw_vc_viewers     — Discord voice channel ID (string)
  tw_vc_game        — Discord voice channel ID (string)

The -twitchsetup command creates the VC channels AND saves their IDs into
guild_settings so the dashboard can display and edit them.
The update loop reads guild_settings every tick, so dashboard changes
take effect within 5 minutes with no bot restart needed.
"""

import discord
from discord.ext import commands, tasks
import aiohttp
import os


def _get_db():
    from database import get_db
    return get_db()


def _get_guild_settings(guild_id: str) -> dict:
    doc = _get_db().guild_settings.find_one({"guild_id": str(guild_id)}, {"_id": 0}) or {}
    return doc


def _save_guild_settings(guild_id: str, fields: dict):
    _get_db().guild_settings.update_one(
        {"guild_id": str(guild_id)},
        {"$set": {**fields, "guild_id": str(guild_id)}},
        upsert=True
    )


# ── Default VC name format templates ─────────────────────────────────────────
# {value} is replaced with the live stat at update time.
# Status templates have no {value} — they're static strings for LIVE / Offline.
VC_FORMAT_DEFAULTS = {
    "tw_fmt_followers":      "🪻 | Followers : {value}",
    "tw_fmt_status_live":    "🪻 | Status : 🔴 LIVE",
    "tw_fmt_status_offline": "🪻 | Status : ⚫ Offline",
    "tw_fmt_viewers":        "🪻 | Viewers : {value}",
    "tw_fmt_game":           "🪻 | Game : {value}",
}


def _apply_fmt(template: str, value: str = "") -> str:
    """Replace {value} placeholder and trim to Discord's 100-char VC name limit."""
    return template.replace("{value}", value)[:100]


def mk_embed(title, desc="", color=0x9146FF):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="NinjuBot | Made by sdb_darkninja")
    return e


class Twitch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.access_token = None

    # ── Twitch API ────────────────────────────────────────────────────────────

    async def _get_token(self) -> str | None:
        cid = os.getenv("TWITCH_CLIENT_ID")
        cs  = os.getenv("TWITCH_CLIENT_SECRET")
        if not cid or not cs:
            return None
        async with aiohttp.ClientSession() as s:
            r = await s.post("https://id.twitch.tv/oauth2/token", params={
                "client_id": cid, "client_secret": cs, "grant_type": "client_credentials"
            })
            data = await r.json()
            return data.get("access_token")

    async def _get_stats(self, username: str) -> tuple[dict | None, str | None]:
        cid = os.getenv("TWITCH_CLIENT_ID")
        if not cid:
            return None, "❌ `TWITCH_CLIENT_ID` env var missing."
        if not self.access_token:
            self.access_token = await self._get_token()
        if not self.access_token:
            return None, "❌ Could not obtain Twitch access token."

        headers = {"Client-ID": cid, "Authorization": f"Bearer {self.access_token}"}
        try:
            async with aiohttp.ClientSession() as s:
                r = await s.get(f"https://api.twitch.tv/helix/users?login={username}", headers=headers)
                # Refresh token on 401
                if r.status == 401:
                    self.access_token = await self._get_token()
                    if not self.access_token:
                        return None, "❌ Token refresh failed."
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    r = await s.get(f"https://api.twitch.tv/helix/users?login={username}", headers=headers)
                user_data = await r.json()
                if not user_data.get("data"):
                    return None, f"❌ Twitch user `{username}` not found."
                user    = user_data["data"][0]
                user_id = user["id"]

                r2 = await s.get(
                    f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={user_id}",
                    headers=headers)
                followers = (await r2.json()).get("total", 0)

                r3 = await s.get(
                    f"https://api.twitch.tv/helix/streams?user_login={username}",
                    headers=headers)
                stream_data = await r3.json()
                stream = stream_data["data"][0] if stream_data.get("data") else None

                return {
                    "username": user["display_name"],
                    "followers": followers,
                    "is_live":  stream is not None,
                    "viewers":  stream["viewer_count"] if stream else 0,
                    "game":     stream["game_name"]    if stream else "Offline",
                    "title":    stream["title"]        if stream else "—",
                }, None
        except Exception as e:
            return None, f"❌ Twitch API error: {e}"

    # ── VC updater ────────────────────────────────────────────────────────────

    async def _update_guild_vcs(self, guild: discord.Guild, stats: dict, settings: dict):
        def fmt(field: str, value: str = "") -> str:
            template = settings.get(field) or VC_FORMAT_DEFAULTS[field]
            return _apply_fmt(template, value)

        vc_map = {
            "tw_vc_followers": fmt("tw_fmt_followers", f"{stats['followers']:,}"),
            "tw_vc_status":    fmt("tw_fmt_status_live" if stats["is_live"] else "tw_fmt_status_offline"),
            "tw_vc_viewers":   fmt("tw_fmt_viewers", f"{stats['viewers']:,}"),
            "tw_vc_game":      fmt("tw_fmt_game", stats["game"][:28]),
        }
        for key, new_name in vc_map.items():
            ch_id = settings.get(key, "")
            if not ch_id:
                continue
            try:
                ch = guild.get_channel(int(ch_id))
                if ch and ch.name != new_name:
                    await ch.edit(name=new_name)
            except Exception as e:
                print(f"[Twitch] Failed to update {key} in {guild.name}: {e}", flush=True)

    # ── Background loop ───────────────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def update_loop(self):
        try:
            docs = list(_get_db().guild_settings.find(
                {"tw_stats_vc": True, "tw_username": {"$nin": [None, ""]}},
                {"_id": 0}
            ))
        except Exception as e:
            print(f"[Twitch] DB query failed: {e}", flush=True)
            return

        for doc in docs:
            try:
                guild = self.bot.get_guild(int(doc["guild_id"]))
            except Exception:
                continue
            if not guild:
                continue
            username = doc.get("tw_username", "").strip()
            if not username:
                continue
            stats, err = await self._get_stats(username)
            if err:
                print(f"[Twitch] {guild.name} — {err}", flush=True)
                continue
            await self._update_guild_vcs(guild, stats, doc)

    @update_loop.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.update_loop.is_running():
            self.update_loop.start()

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name="twitchsetup")
    @commands.has_permissions(administrator=True)
    async def twitch_setup(self, ctx, category_id: int = None):
        """Creates 4 Twitch stat VCs and saves their IDs to guild_settings."""
        settings = _get_guild_settings(str(ctx.guild.id))
        username = settings.get("tw_username", "").strip()

        if not username:
            return await ctx.send(embed=mk_embed(
                "❌ No Twitch Username Set",
                "Go to your dashboard → **Streams** → set **Twitch Username** → Save.\n"
                "Then run `-twitchsetup` again.",
                0xE74C3C
            ))

        msg = await ctx.send(f"⏳ Fetching stats for **{username}**...")
        stats, err = await self._get_stats(username)
        if err:
            return await msg.edit(content=None, embed=mk_embed("❌ Error", err, 0xE74C3C))

        guild = ctx.guild

        # If channels already exist — just update and return
        existing = [settings.get(k) for k in ("tw_vc_followers","tw_vc_status","tw_vc_viewers","tw_vc_game")]
        if all(existing) and all(guild.get_channel(int(i)) for i in existing):
            await self._update_guild_vcs(guild, stats, settings)
            return await msg.edit(content=None, embed=mk_embed(
                "✅ Already Set Up!",
                "Channels exist — names updated.\n"
                "Delete them manually and re-run `-twitchsetup` to recreate.",
                0x2ECC71
            ))

        # Find or create category
        category = None
        if category_id:
            category = guild.get_channel(category_id)
            if not isinstance(category, discord.CategoryChannel):
                return await msg.edit(content=None, embed=mk_embed(
                    "❌ Bad Category", f"`{category_id}` is not a category channel.", 0xE74C3C))
        if not category:
            category = await guild.create_category("📊 Twitch Analytics")

        overwrite = {guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}

        def fmt(field: str, value: str = "") -> str:
            template = settings.get(field) or VC_FORMAT_DEFAULTS[field]
            return _apply_fmt(template, value)

        f_vc = await guild.create_voice_channel(fmt("tw_fmt_followers", f"{stats['followers']:,}"),   category=category, overwrites=overwrite)
        s_vc = await guild.create_voice_channel(fmt("tw_fmt_status_live" if stats["is_live"] else "tw_fmt_status_offline"), category=category, overwrites=overwrite)
        v_vc = await guild.create_voice_channel(fmt("tw_fmt_viewers", f"{stats['viewers']:,}"),       category=category, overwrites=overwrite)
        g_vc = await guild.create_voice_channel(fmt("tw_fmt_game", stats["game"][:28]),               category=category, overwrites=overwrite)

        # Save IDs into guild_settings — dashboard will now show them
        _save_guild_settings(str(guild.id), {
            "tw_stats_vc":     True,
            "tw_vc_followers": str(f_vc.id),
            "tw_vc_status":    str(s_vc.id),
            "tw_vc_viewers":   str(v_vc.id),
            "tw_vc_game":      str(g_vc.id),
        })

        embed = discord.Embed(
            title="✅ Twitch Analytics Ready!",
            description=(
                f"📊 Tracking **{stats['username']}**\n"
                f"📁 Category: **{category.name}**\n\n"
                f"Channel IDs are now in your dashboard under **Streams → Stats VC Channels**.\n"
                f"Auto-updates every **5 minutes**."
            ),
            color=0x9146FF
        )
        embed.add_field(name="Followers VC", value=f"`{f_vc.id}`", inline=True)
        embed.add_field(name="Status VC",    value=f"`{s_vc.id}`", inline=True)
        embed.add_field(name="Viewers VC",   value=f"`{v_vc.id}`", inline=True)
        embed.add_field(name="Game VC",      value=f"`{g_vc.id}`", inline=True)
        embed.set_footer(text="NinjuBot | Made by sdb_darkninja")
        await msg.edit(content=None, embed=embed)

        if not self.update_loop.is_running():
            self.update_loop.start()

    @commands.command(name="twitchstats", aliases=["twitch"])
    async def twitch_stats(self, ctx):
        settings = _get_guild_settings(str(ctx.guild.id))
        username = settings.get("tw_username", "").strip()
        if not username:
            return await ctx.send(embed=mk_embed(
                "❌ No Username", "Set Twitch username in the dashboard first.", 0xE74C3C))

        msg = await ctx.send(f"⏳ Fetching stats for **{username}**...")
        stats, err = await self._get_stats(username)
        if err:
            return await msg.edit(content=None, embed=mk_embed("❌ Error", err, 0xE74C3C))

        if settings.get("tw_stats_vc"):
            await self._update_guild_vcs(ctx.guild, stats, settings)

        status = "🔴 **LIVE**" if stats["is_live"] else "⚫ **Offline**"
        embed = discord.Embed(
            title=f"📊 Twitch Stats — {stats['username']}",
            color=0x9146FF if stats["is_live"] else 0x666666
        )
        embed.add_field(name="Status",       value=status,                    inline=True)
        embed.add_field(name="🪻 Followers", value=f"{stats['followers']:,}", inline=True)
        embed.add_field(name="🪻 Viewers",   value=f"{stats['viewers']:,}",   inline=True)
        embed.add_field(name="🪻 Game",      value=stats["game"],              inline=True)
        if stats["is_live"]:
            embed.add_field(name="📺 Title", value=stats["title"][:100], inline=False)
        footer = "NinjuBot | VC channels updated!" if settings.get("tw_stats_vc") else "NinjuBot"
        embed.set_footer(text=footer)
        await msg.edit(content=None, embed=embed)

    @commands.command(name="twitchreset")
    @commands.has_permissions(administrator=True)
    async def twitch_reset(self, ctx):
        _save_guild_settings(str(ctx.guild.id), {
            "tw_stats_vc": False,
            "tw_vc_followers": "", "tw_vc_status": "",
            "tw_vc_viewers": "",  "tw_vc_game": "",
        })
        await ctx.send(embed=mk_embed(
            "🔄 Reset Done",
            "VC IDs cleared. Run `-twitchsetup` to recreate channels.",
            0xF39C12
        ))


async def setup(bot):
    await bot.add_cog(Twitch(bot))
