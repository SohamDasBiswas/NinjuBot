import discord
from discord.ext import commands
<<<<<<< HEAD
import random
import time
import asyncio
from database import get_xp, set_xp, get_top_xp

COOLDOWNS = {}
=======
import json
import os
import random
import time
import asyncio

XP_FILE = "xp_data.json"
COOLDOWNS = {}  # user_id -> last message timestamp

def load_xp():
    if os.path.exists(XP_FILE):
        with open(XP_FILE, "r") as f:
            return json.load(f)
    return {}

def save_xp(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f, indent=2)
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450

def get_level(xp):
    return int((xp / 100) ** 0.5)

def xp_for_level(level):
    return (level ** 2) * 100

def mk_embed(title, desc, color=0x3498DB):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="📈 NinjaBot | Made by sdb_darkninja")
    return e

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
<<<<<<< HEAD

    def get_user_xp(self, guild_id, user_id):
        return get_xp(str(guild_id), str(user_id))

    def set_user_xp(self, guild_id, user_id, data):
        set_xp(str(guild_id), str(user_id), data)
=======
        self.xp_data = load_xp()

    def get_user_xp(self, guild_id, user_id):
        key = f"{guild_id}_{user_id}"
        return self.xp_data.get(key, {"xp": 0, "level": 0})

    def set_user_xp(self, guild_id, user_id, data):
        key = f"{guild_id}_{user_id}"
        self.xp_data[key] = data
        save_xp(self.xp_data)
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
<<<<<<< HEAD
        uid = message.author.id
        now = time.time()
        if now - COOLDOWNS.get(uid, 0) < 60:
            return
        COOLDOWNS[uid] = now
        data = self.get_user_xp(message.guild.id, uid)
        gained = random.randint(10, 25)
        data["xp"] += gained
        new_level = get_level(data["xp"])
        if new_level > data["level"]:
            data["level"] = new_level
            try:
                await message.channel.send(embed=mk_embed(
                    "🎉 Level Up!",
                    f"{message.author.mention} reached **Level {new_level}**! 🚀",
                    0x2ECC71
                ))
            except Exception:
                pass
        self.set_user_xp(message.guild.id, uid, data)

    @commands.command(name="rank", aliases=["level", "xp"])
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = self.get_user_xp(ctx.guild.id, member.id)
        xp = data["xp"]
        level = data["level"]
        next_xp = xp_for_level(level + 1)
        await ctx.send(embed=mk_embed(
            f"📊 {member.display_name}'s Rank",
            f"**Level:** {level}\n**XP:** {xp:,} / {next_xp:,}\n**Progress:** {'█' * min(int((xp/next_xp)*10), 10)}{'░' * (10 - min(int((xp/next_xp)*10), 10))}"
        ))

    @commands.command(name="toplevel", aliases=["xplb"])
    async def toplevel(self, ctx):
        rows = get_top_xp(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=mk_embed("🏆 XP Leaderboard", "No data yet!"))
        desc = ""
        for i, row in enumerate(rows, 1):
            uid = row["key"].split("_")[1]
            desc += f"**{i}.** <@{uid}> — Level {row['level']} ({row['xp']:,} XP)\n"
        await ctx.send(embed=mk_embed("🏆 XP Leaderboard", desc))
=======

        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        now = time.time()

        # 60 second cooldown per user
        cooldown_key = f"{guild_id}_{user_id}"
        if now - COOLDOWNS.get(cooldown_key, 0) < 60:
            return
        COOLDOWNS[cooldown_key] = now

        data = self.get_user_xp(guild_id, user_id)
        gained = random.randint(10, 25)
        data["xp"] += gained
        new_level = get_level(data["xp"])

        if new_level > data["level"]:
            data["level"] = new_level
            self.set_user_xp(guild_id, user_id, data)
            embed = discord.Embed(
                title="⬆️ Level Up!",
                description=f"🎉 {message.author.mention} reached **Level {new_level}**!",
                color=0xF1C40F
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text="NinjaBot | Made by sdb_darkninja")
            await message.channel.send(embed=embed)
        else:
            self.set_user_xp(guild_id, user_id, data)

    # ── -rank ─────────────────────────────────────────────────────────────────
    @commands.command(name="rank")
    async def rank(self, ctx, member: discord.Member = None):
        """Show your rank card."""
        member = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        data = self.get_user_xp(guild_id, user_id)

        level = data["level"]
        xp = data["xp"]
        current_level_xp = xp_for_level(level)
        next_level_xp = xp_for_level(level + 1)
        progress = xp - current_level_xp
        needed = next_level_xp - current_level_xp
        bar_filled = int((progress / needed) * 20) if needed > 0 else 20
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        # Rank position
        guild_data = {k: v for k, v in self.xp_data.items() if k.startswith(guild_id)}
        sorted_users = sorted(guild_data.values(), key=lambda x: x["xp"], reverse=True)
        rank_pos = next((i + 1 for i, u in enumerate(sorted_users) if u["xp"] == xp), "?")

        embed = discord.Embed(title=f"📊 {member.display_name}'s Rank", color=0x3498DB)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏆 Rank",  value=f"`#{rank_pos}`",      inline=True)
        embed.add_field(name="⭐ Level", value=f"`{level}`",           inline=True)
        embed.add_field(name="✨ XP",    value=f"`{xp:,}`",            inline=True)
        embed.add_field(name=f"Progress to Level {level+1}",
                        value=f"`{bar}` {progress}/{needed} XP", inline=False)
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    # ── -leaderboard ──────────────────────────────────────────────────────────
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx):
        """Show top 10 most active members."""
        guild_id = str(ctx.guild.id)
        guild_data = {k: v for k, v in self.xp_data.items() if k.startswith(guild_id)}

        if not guild_data:
            return await ctx.send("❌ No XP data yet. Start chatting to earn XP!")

        sorted_users = sorted(guild_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]

        medals = ["🥇", "🥈", "🥉"]
        desc = ""
        for i, (key, data) in enumerate(sorted_users):
            user_id = int(key.split("_")[1])
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            desc += f"{medal} **{name}** — Level `{data['level']}` | `{data['xp']:,}` XP\n"

        embed = discord.Embed(title=f"🏆 {ctx.guild.name} Leaderboard", description=desc, color=0xF1C40F)
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    # ── -serverinfo ───────────────────────────────────────────────────────────
    @commands.command(name="serverinfo", aliases=["si"])
    async def serverinfo(self, ctx):
        """Show server information."""
        g = ctx.guild
        bots = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots
        online = sum(1 for m in g.members if m.status != discord.Status.offline and not m.bot)

        embed = discord.Embed(title=f"📊 {g.name}", color=0x3498DB)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="👑 Owner",    value=g.owner.mention,            inline=True)
        embed.add_field(name="📅 Created",  value=g.created_at.strftime("%d %b %Y"), inline=True)
        embed.add_field(name="🌍 Region",   value=str(g.preferred_locale),    inline=True)
        embed.add_field(name="👥 Members",  value=f"{g.member_count} total\n{humans} humans\n{bots} bots", inline=True)
        embed.add_field(name="🟢 Online",   value=str(online),                inline=True)
        embed.add_field(name="💬 Channels", value=f"{len(g.text_channels)} text\n{len(g.voice_channels)} voice", inline=True)
        embed.add_field(name="🎭 Roles",    value=str(len(g.roles)),          inline=True)
        embed.add_field(name="😀 Emojis",   value=str(len(g.emojis)),         inline=True)
        embed.add_field(name="🚀 Boosts",   value=str(g.premium_subscription_count), inline=True)
        embed.set_footer(text=f"ID: {g.id} | NinjaBot by sdb_darkninja")
        await ctx.send(embed=embed)
>>>>>>> d41d31c352c0ebf98ee13bfc9bc59b6ac02c8450

async def setup(bot):
    await bot.add_cog(Levels(bot))
