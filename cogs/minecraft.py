"""
cogs/minecraft.py  —  Minecraft ↔ Discord Bridge
──────────────────────────────────────────────────
Features
  1. DISCORD → MINECRAFT
       Messages posted in the configured chat-relay channel are forwarded
       to all in-game players via RCON /tellraw.

  2. MINECRAFT → DISCORD  (log watcher)
       A background task tails the server's latest.log and posts:
         • Player chat messages  → chat relay channel  (embed)
         • Join / Leave events   → chat relay channel  (embed)
         • Death messages        → chat relay channel  (embed)
         • Server start / stop   → chat relay channel  (embed)
         • All filtered INFO lines → log channel       (code block)

Settings are loaded per-guild from the bot's own API endpoint:
  GET  /minecraft/settings?guild_id=<id>
  POST /minecraft/settings   { guild_id, ..., chat_channel_id, log_channel_id }

The cog re-reads settings for every guild every 60 s so dashboard
changes take effect without a bot restart.
"""

import asyncio
import os
import re

import aiohttp
import discord
from discord.ext import commands, tasks

# ── Optional RCON library ─────────────────────────────────────────────────────
try:
    from mcrcon import MCRcon          # pip install mcrcon
    RCON_AVAILABLE = True
except ImportError:
    RCON_AVAILABLE = False
    print("[Minecraft] ⚠️  mcrcon not installed — run: pip install mcrcon", flush=True)

# ── Log-line regex patterns ───────────────────────────────────────────────────
_RE_CHAT    = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: <([^>]+)> (.+)")
_RE_JOIN    = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: (\w+) joined the game")
_RE_LEAVE   = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: (\w+) left the game")
_RE_DEATH   = re.compile(
    r"\[[\d:]+\] \[.*?INFO.*?\]: (\w+) "
    r"(was |died|drowned|fell|burned|hit |tried|went |experienced|suffocated|"
    r"walked|withered|starved|blew )"
)
_RE_STARTED = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: Done \(")
_RE_STOPPED = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: Stopping the server")
_RE_STRIP_PREFIX = re.compile(r"^\[[\d:]+\] \[.*?\]: ")

# Noisy log keywords to suppress from the raw log channel
_LOG_SKIP = frozenset((
    "NETTY", "keepAlive", "UnsupportedOperation",
    "uuid", "UUID", "Mojang", "RCON", "Preparing", "chunk", "Chunk",
))


def _embed(title: str, description: str = "", color: int = 0x55AA55) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="NinjuBot · Minecraft Bridge")
    return e


# ── Per-guild state container ─────────────────────────────────────────────────

class GuildState:
    """Holds everything the cog needs for one Discord guild."""

    __slots__ = (
        "guild_id",
        "rcon_host", "rcon_port", "rcon_password",
        "log_path",
        "chat_channel_id", "log_channel_id",
        "_log_file",
    )

    def __init__(self, guild_id: int):
        self.guild_id        = guild_id
        self.rcon_host       = "localhost"
        self.rcon_port       = 25575
        self.rcon_password   = ""
        self.log_path        = ""
        self.chat_channel_id = 0
        self.log_channel_id  = 0
        self._log_file       = None   # open file handle for tailing

    def apply(self, data: dict):
        """Merge a settings dict (from the API) into this state."""
        s = data.get("settings") or data  # API may wrap in {"settings": {...}}
        self.rcon_host       = s.get("host", "localhost")
        self.rcon_port       = int(s.get("rcon_port", 25575) or 25575)
        self.rcon_password   = s.get("rcon_password", "")
        self.log_path        = s.get("log_path", "")
        self.chat_channel_id = int(s.get("chat_channel_id") or 0)
        self.log_channel_id  = int(s.get("log_channel_id")  or 0)

    def close_log(self):
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

    @property
    def rcon_ready(self) -> bool:
        return bool(RCON_AVAILABLE and self.rcon_host and self.rcon_password)

    @property
    def log_ready(self) -> bool:
        return bool(self.log_path and os.path.exists(self.log_path))


# ── Main Cog ──────────────────────────────────────────────────────────────────

class Minecraft(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self._guilds: dict[int, GuildState] = {}   # guild_id → GuildState

        # The bot's own API base URL (same host:port the dashboard calls)
        self._api_base = os.getenv("BOT_API_BASE", "http://localhost:5000")
        self._api_token = os.getenv("BOT_API_TOKEN", "")   # if your API needs auth

        self._settings_refresh.start()
        self._log_watcher.start()

    def cog_unload(self):
        self._settings_refresh.cancel()
        self._log_watcher.cancel()
        for gs in self._guilds.values():
            gs.close_log()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _state(self, guild_id: int) -> GuildState:
        if guild_id not in self._guilds:
            self._guilds[guild_id] = GuildState(guild_id)
        return self._guilds[guild_id]

    async def _fetch_settings(self, guild_id: int) -> dict | None:
        """Call the bot's own API to retrieve saved minecraft settings."""
        url = f"{self._api_base}/minecraft/settings?guild_id={guild_id}"
        headers = {}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        return await r.json()
        except Exception as e:
            print(f"[Minecraft] settings fetch error (guild {guild_id}): {e}", flush=True)
        return None

    def _rcon(self, gs: GuildState, command: str) -> str:
        """Blocking RCON call — run in executor."""
        if not gs.rcon_ready:
            return "❌ RCON not configured."
        try:
            with MCRcon(gs.rcon_host, gs.rcon_password, port=gs.rcon_port) as mcr:
                return mcr.command(command)
        except Exception as e:
            return f"❌ RCON error: {e}"

    async def _send_to_minecraft(self, gs: GuildState, discord_user: str, message: str):
        """Forward a Discord message to Minecraft via /tellraw."""
        if not gs.rcon_ready:
            return
        clean_msg  = message.replace('"', "'").replace("\\", "/")[:200]
        clean_user = discord_user.replace('"', "'")[:32]
        tellraw = (
            f'/tellraw @a [{{"text":"[Discord] ","color":"blue"}},'
            f'{{"text":"{clean_user}","color":"aqua"}},'
            f'{{"text":": {clean_msg}","color":"white"}}]'
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._rcon, gs, tellraw)

    # ── Background: refresh settings every 60 s ───────────────────────────────

    @tasks.loop(seconds=60.0)
    async def _settings_refresh(self):
        for guild in self.bot.guilds:
            data = await self._fetch_settings(guild.id)
            if data:
                gs = self._state(guild.id)
                old_log = gs.log_path
                gs.apply(data)
                # If log path changed, reset the file handle so we re-open it
                if gs.log_path != old_log:
                    gs.close_log()

    @_settings_refresh.before_loop
    async def _before_settings_refresh(self):
        await self.bot.wait_until_ready()
        # Initial load: fetch all guilds immediately
        for guild in self.bot.guilds:
            data = await self._fetch_settings(guild.id)
            if data:
                self._state(guild.id).apply(data)

    # ── Background: tail log files every 2 s ─────────────────────────────────

    @tasks.loop(seconds=2.0)
    async def _log_watcher(self):
        for guild in self.bot.guilds:
            gs = self._state(guild.id)
            if not gs.log_ready:
                continue
            await self._process_log_lines(gs)

    @_log_watcher.before_loop
    async def _before_log_watcher(self):
        await self.bot.wait_until_ready()

    async def _process_log_lines(self, gs: GuildState):
        try:
            # Open file handle once; seek to end on first open to avoid replay
            if gs._log_file is None:
                gs._log_file = open(gs.log_path, "r", encoding="utf-8", errors="replace")
                gs._log_file.seek(0, 2)
                return

            lines = gs._log_file.readlines()
            if not lines:
                # Log may have rotated — reopen next cycle
                gs.close_log()
                return

            chat_ch = self.bot.get_channel(gs.chat_channel_id) if gs.chat_channel_id else None
            log_ch  = self.bot.get_channel(gs.log_channel_id)  if gs.log_channel_id  else None

            for raw in lines:
                line = raw.rstrip()
                if not line:
                    continue
                await self._dispatch_line(line, chat_ch, log_ch)

        except Exception as e:
            print(f"[Minecraft] log watcher error (guild {gs.guild_id}): {e}", flush=True)
            gs.close_log()

    async def _dispatch_line(
        self,
        line: str,
        chat_ch: discord.TextChannel | None,
        log_ch:  discord.TextChannel | None,
    ):
        # ── Raw log channel (filtered INFO lines) ──────────────────────────
        if log_ch and ("/INFO" in line or "INFO]" in line):
            if not any(kw in line for kw in _LOG_SKIP):
                await log_ch.send(f"```\n{line[:1990]}\n```")

        if not chat_ch:
            return

        # ── Chat relay ─────────────────────────────────────────────────────
        m = _RE_CHAT.search(line)
        if m:
            player, msg = m.group(1), m.group(2)
            e = discord.Embed(description=f"**{player}**: {msg}", color=0x55AA55)
            e.set_author(name="⛏️ Minecraft Chat")
            await chat_ch.send(embed=e)
            return

        m = _RE_JOIN.search(line)
        if m:
            await chat_ch.send(embed=_embed("📗 Player Joined", f"**{m.group(1)}** joined the game!", 0x2ECC71))
            return

        m = _RE_LEAVE.search(line)
        if m:
            await chat_ch.send(embed=_embed("📕 Player Left", f"**{m.group(1)}** left the game.", 0xE74C3C))
            return

        m = _RE_DEATH.search(line)
        if m:
            death_msg = _RE_STRIP_PREFIX.sub("", line)
            await chat_ch.send(embed=_embed("💀 Death", death_msg, 0x8B0000))
            return

        if _RE_STARTED.search(line):
            await chat_ch.send(embed=_embed("🟢 Server Started", "Minecraft server is now online!", 0x2ECC71))
            return

        if _RE_STOPPED.search(line):
            await chat_ch.send(embed=_embed("🔴 Server Stopped", "Minecraft server has stopped.", 0xE74C3C))
            return

    # ── Discord → Minecraft relay ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        gs = self._state(message.guild.id)
        if not gs.chat_channel_id:
            return
        if message.channel.id != gs.chat_channel_id:
            return
        # Don't relay commands
        if message.content.startswith(("-", "/", "!")):
            return
        await self._send_to_minecraft(gs, message.author.display_name, message.clean_content)

    # ── Slash-free status command (-mc status) ────────────────────────────────

    @commands.group(name="mc", invoke_without_command=True)
    async def mc_group(self, ctx: commands.Context):
        await ctx.send(embed=_embed(
            "⛏️ Minecraft Bridge",
            "`-mc status` — Show bridge status for this server\n"
            "`-mc connect` — Test RCON connection\n"
            "`-mc players` — List online players\n"
        ))

    @mc_group.command(name="status")
    async def mc_status(self, ctx: commands.Context):
        if not ctx.guild:
            return
        gs = self._state(ctx.guild.id)
        rcon_s   = "✅ Configured" if gs.rcon_password else "❌ Not set"
        log_s    = f"✅ `{gs.log_path}`" if gs.log_ready else ("⚠️ Path not found" if gs.log_path else "❌ Not set")
        chat_s   = f"<#{gs.chat_channel_id}>"  if gs.chat_channel_id else "Not set"
        log_ch_s = f"<#{gs.log_channel_id}>"   if gs.log_channel_id  else "Not set"
        await ctx.send(embed=_embed(
            "⛏️ Minecraft Bridge Status",
            f"**RCON host:** `{gs.rcon_host}:{gs.rcon_port}`\n"
            f"**RCON password:** {rcon_s}\n"
            f"**Log file:** {log_s}\n"
            f"**Chat relay channel:** {chat_s}\n"
            f"**Log channel:** {log_ch_s}\n"
            f"\n*Settings refresh automatically from the dashboard every 60 s.*"
        ))

    @mc_group.command(name="connect")
    async def mc_connect(self, ctx: commands.Context):
        if not ctx.guild:
            return
        gs = self._state(ctx.guild.id)
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._rcon, gs, "list")
        color = 0x2ECC71 if "error" not in result.lower() else 0xE74C3C
        await ctx.send(embed=_embed("🔌 RCON Test", f"`{result}`", color))

    @mc_group.command(name="players")
    async def mc_players(self, ctx: commands.Context):
        if not ctx.guild:
            return
        gs = self._state(ctx.guild.id)
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._rcon, gs, "list")
        await ctx.send(embed=_embed("👥 Online Players", result or "No response from server."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))
    print("✅ Minecraft cog loaded", flush=True)
