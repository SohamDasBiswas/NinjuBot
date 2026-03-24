"""
cogs/minecraft.py  —  Minecraft ↔ Discord Bridge + Log Watcher
───────────────────────────────────────────────────────────────
Features
  1. DISCORD → MINECRAFT  (requires RCON)
       Any Discord message in the linked channel is forwarded to Minecraft
       via /tellraw so in-game players see it.

  2. MINECRAFT → DISCORD  (requires log file access)
       A background task tails the Minecraft server.log / latest.log file
       and posts player chat, join/leave events to Discord.

  3. LOG CHANNEL  (requires log file access)
       A separate channel receives ALL Minecraft server log lines (filtered).

Commands
  -mc status          : Show Minecraft bridge status.
  -mc connect         : Manually trigger RCON connection test.
  -mc setchat #chan   : Set the bidirectional chat relay channel.
  -mc setlogs #chan   : Set the raw logs channel.
  -mc say <msg>       : Send a message to Minecraft as the bot (admin only).
  -mc players         : List online players via RCON.

Env vars (add to .env / render.yaml):
  MINECRAFT_RCON_HOST     — e.g. "localhost" or your server IP
  MINECRAFT_RCON_PORT     — default 25575
  MINECRAFT_RCON_PASSWORD — your rcon.password from server.properties
  MINECRAFT_LOG_PATH      — absolute path to latest.log / server.log
  MINECRAFT_CHAT_CHANNEL  — Discord channel ID for chat relay
  MINECRAFT_LOG_CHANNEL   — Discord channel ID for raw logs
"""

import asyncio
import os
import re
import discord
from discord.ext import commands, tasks
from datetime import timezone
import datetime

# ─── optional RCON library ────────────────────────────────────────────────────
try:
    from mcrcon import MCRcon   # pip install mcrcon
    RCON_AVAILABLE = True
except ImportError:
    RCON_AVAILABLE = False
    print("[Minecraft] ⚠️  mcrcon not installed — run: pip install mcrcon", flush=True)


# ─── Regex patterns for Minecraft log parsing ────────────────────────────────

# Chat: [12:34:56] [Server thread/INFO]: <PlayerName> Hello world
_RE_CHAT = re.compile(
    r"\[[\d:]+\] \[.*?INFO.*?\]: <([^>]+)> (.+)"
)
# Join/Leave
_RE_JOIN  = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: (\w+) joined the game")
_RE_LEAVE = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: (\w+) left the game")
# Death messages (contains "was" / "died" / "drowned" etc.) — broad match
_RE_DEATH = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: (\w+) (was |died|drowned|fell|burned|hit|tried|went|experienced|suffocated|walked|withered|starved|blew)")
# Server started/stopped
_RE_STARTED = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: Done \(")
_RE_STOPPED = re.compile(r"\[[\d:]+\] \[.*?INFO.*?\]: Stopping the server")


def mk_embed(title, description="", color=0x55AA55):
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="NinjuBot · Minecraft Bridge")
    return e


class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Config from env
        self.rcon_host     = os.getenv("MINECRAFT_RCON_HOST", "localhost")
        self.rcon_port     = int(os.getenv("MINECRAFT_RCON_PORT", "25575"))
        self.rcon_password = os.getenv("MINECRAFT_RCON_PASSWORD", "")
        self.log_path      = os.getenv("MINECRAFT_LOG_PATH", "")

        # Channel IDs — can also be set via commands
        self.chat_channel_id = int(os.getenv("MINECRAFT_CHAT_CHANNEL", "0") or 0)
        self.log_channel_id  = int(os.getenv("MINECRAFT_LOG_CHANNEL", "0") or 0)

        # Log tail state
        self._log_file = None
        self._log_position = 0   # start from end so we don't replay old logs

        # Start background tasks
        self.log_watcher.start()

    def cog_unload(self):
        self.log_watcher.cancel()
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass

    # ─── RCON helper ─────────────────────────────────────────────────────────

    def rcon_command(self, command: str) -> str:
        """Run a single RCON command and return the response string."""
        if not RCON_AVAILABLE:
            return "❌ mcrcon not installed."
        if not self.rcon_password:
            return "❌ MINECRAFT_RCON_PASSWORD not set."
        try:
            with MCRcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                return mcr.command(command)
        except Exception as e:
            return f"❌ RCON error: {e}"

    async def send_to_minecraft(self, discord_user: str, message: str):
        """Forward a Discord message to Minecraft via /tellraw."""
        if not self.rcon_password:
            return
        # Sanitise — remove characters that break JSON
        clean_msg = message.replace('"', "'").replace("\\", "/")[:200]
        clean_user = discord_user.replace('"', "'")[:32]
        tellraw = (
            f'/tellraw @a [{{"text":"[Discord] ","color":"blue"}},'
            f'{{"text":"{clean_user}","color":"aqua"}},'
            f'{{"text":": {clean_msg}","color":"white"}}]'
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.rcon_command, tellraw)

    # ─── Background log watcher ──────────────────────────────────────────────

    @tasks.loop(seconds=2.0)
    async def log_watcher(self):
        if not self.log_path or not os.path.exists(self.log_path):
            return

        try:
            # Open once, keep file handle, seek to end on first open
            if self._log_file is None:
                self._log_file = open(self.log_path, "r", encoding="utf-8", errors="replace")
                self._log_file.seek(0, 2)   # seek to end
                return

            lines = self._log_file.readlines()
            if not lines:
                # File may have been rotated — reopen
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None
                return

            chat_channel = self.bot.get_channel(self.chat_channel_id) if self.chat_channel_id else None
            log_channel  = self.bot.get_channel(self.log_channel_id)  if self.log_channel_id  else None

            for raw_line in lines:
                line = raw_line.rstrip()
                if not line:
                    continue

                # ── RAW LOG channel ──────────────────────────────────
                if log_channel:
                    # Filter to INFO lines only; skip spam
                    if "/INFO" in line or "INFO]" in line:
                        # Skip very noisy lines
                        skip_keywords = ("NETTY", "keepAlive", "UnsupportedOperation", "uuid", "UUID",
                                         "Mojang", "RCON", "Preparing", "chunk", "Chunk")
                        if not any(kw in line for kw in skip_keywords):
                            await log_channel.send(f"```\n{line[:1990]}\n```")

                # ── CHAT relay channel ───────────────────────────────
                if chat_channel:
                    m = _RE_CHAT.search(line)
                    if m:
                        player, msg = m.group(1), m.group(2)
                        embed = discord.Embed(
                            description=f"**{player}**: {msg}",
                            color=0x55AA55
                        )
                        embed.set_author(name="⛏️ Minecraft Chat")
                        await chat_channel.send(embed=embed)
                        continue

                    m = _RE_JOIN.search(line)
                    if m:
                        await chat_channel.send(embed=mk_embed(
                            "📗 Player Joined", f"**{m.group(1)}** joined the game!", 0x2ECC71))
                        continue

                    m = _RE_LEAVE.search(line)
                    if m:
                        await chat_channel.send(embed=mk_embed(
                            "📕 Player Left", f"**{m.group(1)}** left the game.", 0xE74C3C))
                        continue

                    m = _RE_DEATH.search(line)
                    if m:
                        # Extract full death message (everything after the timestamp/tag prefix)
                        death_msg = re.sub(r"^\[[\d:]+\] \[.*?\]: ", "", line)
                        await chat_channel.send(embed=mk_embed(
                            "💀 Death", death_msg, 0x8B0000))
                        continue

                    if _RE_STARTED.search(line):
                        await chat_channel.send(embed=mk_embed(
                            "🟢 Server Started", "Minecraft server is now online!", 0x2ECC71))
                        continue

                    if _RE_STOPPED.search(line):
                        await chat_channel.send(embed=mk_embed(
                            "🔴 Server Stopped", "Minecraft server has stopped.", 0xE74C3C))
                        continue

        except Exception as e:
            print(f"[Minecraft] Log watcher error: {e}", flush=True)
            self._log_file = None

    @log_watcher.before_loop
    async def before_log_watcher(self):
        await self.bot.wait_until_ready()

    # ─── on_message: relay Discord → Minecraft ───────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not self.chat_channel_id:
            return
        if message.channel.id != self.chat_channel_id:
            return
        # Don't relay bot commands
        if message.content.startswith(("-", "/", "!")):
            return

        await self.send_to_minecraft(message.author.display_name, message.clean_content)

    # ─── Commands ─────────────────────────────────────────────────────────────

    @commands.group(name="mc", invoke_without_command=True)
    async def mc_group(self, ctx: commands.Context):
        await ctx.send(embed=mk_embed(
            "⛏️ Minecraft Bridge",
            "**Commands:**\n"
            "`-mc status` — Show bridge status\n"
            "`-mc connect` — Test RCON connection\n"
            "`-mc setchat #channel` — Set chat relay channel\n"
            "`-mc setlogs #channel` — Set raw logs channel\n"
            "`-mc say <message>` — Send message to Minecraft (admin)\n"
            "`-mc players` — List online players\n"
        ))

    @mc_group.command(name="status")
    async def mc_status(self, ctx: commands.Context):
        rcon_ok = "✅ Configured" if self.rcon_password else "❌ Not configured"
        log_ok  = f"✅ `{self.log_path}`" if self.log_path and os.path.exists(self.log_path) else "❌ Not found"
        chat_ch = f"<#{self.chat_channel_id}>" if self.chat_channel_id else "Not set"
        log_ch  = f"<#{self.log_channel_id}>"  if self.log_channel_id  else "Not set"
        await ctx.send(embed=mk_embed(
            "⛏️ Minecraft Bridge Status",
            f"**RCON:** {rcon_ok}\n"
            f"**Log file:** {log_ok}\n"
            f"**Chat channel:** {chat_ch}\n"
            f"**Logs channel:** {log_ch}"
        ))

    @mc_group.command(name="connect")
    async def mc_connect(self, ctx: commands.Context):
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.rcon_command, "list")
        await ctx.send(embed=mk_embed("🔌 RCON Test", f"Response: `{result}`", 0x2ECC71 if "error" not in result.lower() else 0xE74C3C))

    @mc_group.command(name="setchat")
    @commands.has_permissions(manage_guild=True)
    async def mc_setchat(self, ctx: commands.Context, channel: discord.TextChannel):
        self.chat_channel_id = channel.id
        await ctx.send(embed=mk_embed("✅ Chat Channel Set", f"Minecraft ↔ Discord relay: {channel.mention}", 0x2ECC71))

    @mc_group.command(name="setlogs")
    @commands.has_permissions(manage_guild=True)
    async def mc_setlogs(self, ctx: commands.Context, channel: discord.TextChannel):
        self.log_channel_id = channel.id
        await ctx.send(embed=mk_embed("✅ Logs Channel Set", f"Raw Minecraft logs → {channel.mention}", 0x2ECC71))

    @mc_group.command(name="say")
    @commands.has_permissions(manage_guild=True)
    async def mc_say(self, ctx: commands.Context, *, message: str):
        clean = message.replace('"', "'").replace("\\", "/")[:200]
        cmd = f'/tellraw @a [{{"text":"[Bot] {clean}","color":"gold"}}]'
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.rcon_command, cmd)
        await ctx.send(embed=mk_embed("📢 Sent to Minecraft", f"`{message}`\nRCON: `{result or 'OK'}`"))

    @mc_group.command(name="players")
    async def mc_players(self, ctx: commands.Context):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.rcon_command, "list")
        # "There are X of a max of Y players online: name1, name2"
        await ctx.send(embed=mk_embed("👥 Online Players", result or "No response from server."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))
    print("✅ Minecraft cog loaded", flush=True)
