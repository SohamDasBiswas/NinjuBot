# ══════════════════════════════════════════════════════════════
# cogs/minecraft.py — DISABLED (commented out)
# ══════════════════════════════════════════════════════════════

# """
# cogs/minecraft.py  —  Aternos ↔ Discord Bridge (Webhook-based)
# ───────────────────────────────────────────────────────────────
# How it works
#   1. DiscordSRV plugin installed on your Aternos server
#   2. DiscordSRV POSTs events to:  https://ninjubot.onrender.com/minecraft/webhook
#   3. This cog receives those POSTs (via Flask in bot.py) and posts
#      embeds to the configured Discord channels.
#
# Settings stored in MongoDB per guild:
#   { guild_id, chat_channel_id, log_channel_id }
#
# Flask routes in bot.py:
#   GET  /minecraft/settings?guild_id=...
#   POST /minecraft/settings   { guild_id, chat_channel_id, log_channel_id }
#   POST /minecraft/webhook    { type, guild_id, player, message, content }
# """
#
# import discord
# from discord.ext import commands
# from database import get_db
#
#
# def _embed(title: str, description: str = "", color: int = 0x55AA55) -> discord.Embed:
#     e = discord.Embed(title=title, description=description, color=color)
#     e.set_footer(text="NinjuBot · Minecraft Bridge")
#     return e
#
#
# class Minecraft(commands.Cog):
#
#     def __init__(self, bot: commands.Bot):
#         self.bot = bot
#
#     async def handle_webhook(self, data: dict):
#         """
#         Called by the /minecraft/webhook Flask route in bot.py.
#
#         DiscordSRV payload shape:
#           {
#             "guild_id": "123...",
#             "type":     "chat" | "join" | "leave" | "death" |
#                         "server_start" | "server_stop" | "log",
#             "player":   "Steve",
#             "message":  "Hello world",   # chat text or full death message
#             "content":  "raw log line"   # only for type=log
#           }
#         """
#         guild_id = str(data.get("guild_id", ""))
#         if not guild_id:
#             return
#
#         doc = get_db().minecraft_settings.find_one({"guild_id": guild_id})
#         if not doc:
#             return
#
#         chat_ch_id = int(doc.get("chat_channel_id") or 0)
#         log_ch_id  = int(doc.get("log_channel_id")  or 0)
#
#         event   = data.get("type", "")
#         player  = data.get("player", "")
#         message = data.get("message", "")
#         content = data.get("content", "")
#
#         # ── Chat relay ────────────────────────────────────────────────────────
#         if chat_ch_id:
#             ch = self.bot.get_channel(chat_ch_id)
#             if ch:
#                 if event == "chat":
#                     e = discord.Embed(
#                         description=f"**{player}**: {message}",
#                         color=0x55AA55
#                     )
#                     e.set_author(name="⛏️ Minecraft Chat")
#                     e.set_footer(text="NinjuBot · Minecraft Bridge")
#                     await ch.send(embed=e)
#
#                 elif event == "join":
#                     await ch.send(embed=_embed(
#                         "📗 Player Joined",
#                         f"**{player}** joined the game!", 0x2ECC71))
#
#                 elif event == "leave":
#                     await ch.send(embed=_embed(
#                         "📕 Player Left",
#                         f"**{player}** left the game.", 0xE74C3C))
#
#                 elif event == "death":
#                     await ch.send(embed=_embed(
#                         "💀 Death",
#                         message or f"{player} died.", 0x8B0000))
#
#                 elif event == "server_start":
#                     await ch.send(embed=_embed(
#                         "🟢 Server Started",
#                         "Minecraft server is now online!", 0x2ECC71))
#
#                 elif event == "server_stop":
#                     await ch.send(embed=_embed(
#                         "🔴 Server Stopped",
#                         "Minecraft server has stopped.", 0xE74C3C))
#
#         # ── Raw log channel ───────────────────────────────────────────────────
#         if log_ch_id and event == "log" and content:
#             ch = self.bot.get_channel(log_ch_id)
#             if ch:
#                 await ch.send(f"```\n{content[:1990]}\n```")
#
#
# async def setup(bot: commands.Bot):
#     await bot.add_cog(Minecraft(bot))
#     print("✅ Minecraft cog loaded", flush=True)
#