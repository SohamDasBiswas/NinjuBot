import discord
from discord.ext import commands
import random
import time
import asyncio
from database import get_xp, set_xp, get_top_xp, get_global_xp, set_global_xp, GLOBAL_XP_MIN, GLOBAL_XP_MAX, GLOBAL_XP_COOLDOWN

COOLDOWNS        = {}  # server XP cooldowns  {user_id: timestamp}
GLOBAL_COOLDOWNS = {}  # global XP cooldowns  {user_id: timestamp}

def get_level(xp):
    return int((xp / 100) ** 0.5)

def xp_for_level(level):
    return (level ** 2) * 100

def mk_embed(title, desc, color=0x3498DB):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="📈 NinjuBot | Made by sdb_darkninja")
    return e

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_xp(self, guild_id, user_id):
        return get_xp(str(guild_id), str(user_id))

    def set_user_xp(self, guild_id, user_id, data):
        set_xp(str(guild_id), str(user_id), data)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        uid  = message.author.id
        now  = time.time()

        # ── Server XP (configurable per-server settings) ──────────────
        from database import get_db
        guild_id = str(message.guild.id)
        cfg = get_db().guild_settings.find_one({"guild_id": guild_id}, {"_id": 0}) or {}

        xp_enabled  = cfg.get("xp_enabled", True)
        xp_min      = int(cfg.get("xp_min", 15))
        xp_max      = int(cfg.get("xp_max", 40))
        xp_cooldown = int(cfg.get("xp_cooldown_seconds", 60))
        xp_mult     = float(cfg.get("xp_multiplier", 1))
        lvl_announce = cfg.get("levelup_announcements", True)
        lvl_msg      = cfg.get("levelup_message", "🎉 {user} just reached level {level}!")
        lvl_base     = int(cfg.get("level_base_xp", 100))

        if xp_enabled and (now - COOLDOWNS.get(uid, 0) >= xp_cooldown):
            COOLDOWNS[uid] = now
            server_data = self.get_user_xp(message.guild.id, uid)
            gained = int(random.randint(xp_min, max(xp_min, xp_max)) * xp_mult)
            server_data["xp"] += gained

            def get_server_level(xp):
                lvl = 0
                while xp >= (lvl_base * (1.5 ** lvl)):
                    xp -= int(lvl_base * (1.5 ** lvl))
                    lvl += 1
                return lvl

            new_level = get_server_level(server_data["xp"])
            if new_level > server_data["level"]:
                server_data["level"] = new_level
                if lvl_announce:
                    try:
                        desc = lvl_msg.replace("{user}", message.author.mention).replace("{level}", str(new_level))
                        embed = discord.Embed(title="⬆️ Level Up!", description=desc, color=0x2ECC71)
                        embed.set_thumbnail(url=message.author.display_avatar.url)
                        embed.add_field(name="Server Level", value=f"**{new_level}**", inline=True)
                        embed.add_field(name="Server XP", value=f"**{server_data['xp']:,}**", inline=True)
                        embed.set_footer(text="📈 NinjuBot | Made by sdb_darkninja")
                        await message.channel.send(embed=embed)
                    except Exception:
                        pass
            self.set_user_xp(message.guild.id, uid, server_data)

        # ── Global XP (fixed rate, cannot be changed by server admins) ─
        if now - GLOBAL_COOLDOWNS.get(uid, 0) >= GLOBAL_XP_COOLDOWN:
            GLOBAL_COOLDOWNS[uid] = now
            global_data = get_global_xp(uid)
            global_gained = random.randint(GLOBAL_XP_MIN, GLOBAL_XP_MAX)
            global_data["xp"] += global_gained
            new_global_level = get_level(global_data["xp"])
            if new_global_level > global_data["level"]:
                global_data["level"] = new_global_level
            set_global_xp(uid, global_data)

    @commands.command(name="rank", aliases=["level", "xp"])
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        # Server XP
        data   = self.get_user_xp(ctx.guild.id, member.id)
        s_xp   = data["xp"]
        s_lvl  = data["level"]
        # Global XP
        gdata  = get_global_xp(member.id)
        g_xp   = gdata["xp"]
        g_lvl  = gdata["level"]

        next_xp     = xp_for_level(s_lvl + 1)
        current_xp  = xp_for_level(s_lvl)
        progress    = s_xp - current_xp
        needed      = next_xp - current_xp
        bar_filled  = int((progress / needed) * 20) if needed > 0 else 20
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        embed = discord.Embed(title=f"📊 {member.display_name}'s Rank", color=0x3498DB)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏠 Server Level", value=f"**{s_lvl}**", inline=True)
        embed.add_field(name="🏠 Server XP",    value=f"**{s_xp:,}**", inline=True)
        embed.add_field(name="🌐 Global Level", value=f"**{g_lvl}**", inline=True)
        embed.add_field(name="🌐 Global XP",    value=f"**{g_xp:,}**", inline=True)
        embed.add_field(
            name=f"Server Progress to Level {s_lvl+1}",
            value=f"`{bar}` **{progress:,}/{needed:,}**",
            inline=False
        )
        embed.set_footer(text="📈 NinjuBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="toplevel", aliases=["xplb", "lvlboard"])
    async def toplevel(self, ctx):
        rows = get_top_xp(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=mk_embed("🏆 XP Leaderboard", "No data yet! Start chatting to earn XP."))
        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title=f"🏆 {ctx.guild.name} XP Leaderboard", color=0x3498DB)
        desc = ""
        for i, row in enumerate(rows, 1):
            uid = row["key"].split("_")[1]
            medal = medals[i-1] if i <= 3 else f"`#{i}`"
            desc += f"{medal} <@{uid}> — Level **{row['level']}** · {row['xp']:,} XP\n"
        embed.description = desc
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="📈 NinjuBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="serverinfo", aliases=["si"])
    async def serverinfo(self, ctx):
        g = ctx.guild
        bots = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots
        embed = discord.Embed(title=f"📊 {g.name}", color=0x3498DB)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="👑 Owner", value=g.owner.mention, inline=True)
        embed.add_field(name="📅 Created", value=f"<t:{int(g.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="🌍 Locale", value=str(g.preferred_locale), inline=True)
        embed.add_field(name="👥 Members", value=f"**{g.member_count}** total\n{humans} humans · {bots} bots", inline=True)
        embed.add_field(name="💬 Channels", value=f"{len(g.text_channels)} text · {len(g.voice_channels)} voice", inline=True)
        embed.add_field(name="🎭 Roles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="😀 Emojis", value=str(len(g.emojis)), inline=True)
        embed.add_field(name="🚀 Boosts", value=str(g.premium_subscription_count), inline=True)
        embed.add_field(name="📋 Verification", value=str(g.verification_level).title(), inline=True)
        embed.set_footer(text=f"ID: {g.id} | NinjuBot by sdb_darkninja")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Levels(bot))
