import discord
from discord.ext import commands
import random
import time
import asyncio
from database import get_xp, set_xp, get_top_xp

COOLDOWNS = {}

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

    def get_user_xp(self, guild_id, user_id):
        return get_xp(str(guild_id), str(user_id))

    def set_user_xp(self, guild_id, user_id, data):
        set_xp(str(guild_id), str(user_id), data)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
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

async def setup(bot):
    await bot.add_cog(Levels(bot))
