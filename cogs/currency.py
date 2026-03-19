import discord
from discord.ext import commands
import random
import asyncio
import time
from database import get_balance, set_balance, get_top_currency

CURRENCY_SYMBOL = "₹"
CURRENCY_NAME = "Rupees"

def mk_embed(title, desc, color=0xF1C40F):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text=f"{CURRENCY_SYMBOL} NinjaBot Economy | Made by sdb_darkninja")
    return e

class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def bal(self, ctx, member=None):
        member = member or ctx.author
        return get_balance(str(ctx.guild.id), str(member.id))

    def save(self, ctx, user_data, member=None):
        member = member or ctx.author
        set_balance(str(ctx.guild.id), str(member.id), user_data)

    @commands.command(name="balance", aliases=["bal", "wallet"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = get_balance(str(ctx.guild.id), str(member.id))
        await ctx.send(embed=mk_embed(
            f"{CURRENCY_SYMBOL} {member.display_name}'s Wallet",
            f"**Balance:** {CURRENCY_SYMBOL} {data['balance']:,} {CURRENCY_NAME}"
        ))

    @commands.command(name="daily")
    async def daily(self, ctx):
        data = self.bal(ctx)
        now = time.time()
        cooldown = 86400
        remaining = cooldown - (now - data["last_daily"])
        if remaining > 0:
            h, m = divmod(int(remaining), 3600)
            m //= 60
            return await ctx.send(embed=mk_embed("⏳ Daily Cooldown", f"Try again in **{h}h {m}m**", 0xE74C3C))
        reward = random.randint(100, 300)
        data["balance"] += reward
        data["last_daily"] = now
        self.save(ctx, data)
        await ctx.send(embed=mk_embed("💰 Daily Reward!", f"You received **{CURRENCY_SYMBOL} {reward}**!\nBalance: {CURRENCY_SYMBOL} {data['balance']:,}"))

    @commands.command(name="work")
    async def work(self, ctx):
        data = self.bal(ctx)
        now = time.time()
        cooldown = 3600
        remaining = cooldown - (now - data["last_work"])
        if remaining > 0:
            m = int(remaining // 60)
            return await ctx.send(embed=mk_embed("⏳ Work Cooldown", f"Try again in **{m}m**", 0xE74C3C))
        jobs = ["delivered packages", "coded a website", "fixed a server", "taught a class", "drove a cab"]
        reward = random.randint(30, 100)
        data["balance"] += reward
        data["last_work"] = now
        self.save(ctx, data)
        await ctx.send(embed=mk_embed("💼 Work Done!", f"You {random.choice(jobs)} and earned **{CURRENCY_SYMBOL} {reward}**!\nBalance: {CURRENCY_SYMBOL} {data['balance']:,}"))

    @commands.command(name="gamble", aliases=["bet"])
    async def gamble(self, ctx, amount: str):
        data = self.bal(ctx)
        bal = data["balance"]
        if amount.lower() == "all":
            amount = bal
        else:
            try:
                amount = int(amount)
            except ValueError:
                return await ctx.send(embed=mk_embed("❌ Error", "Use a number or `all`", 0xE74C3C))
        if amount <= 0 or amount > bal:
            return await ctx.send(embed=mk_embed("❌ Error", f"Invalid amount. Balance: {CURRENCY_SYMBOL} {bal:,}", 0xE74C3C))
        if random.random() > 0.5:
            data["balance"] += amount
            data["wins"] = data.get("wins", 0) + 1
            result = f"🎉 You **won** {CURRENCY_SYMBOL} {amount:,}!\nBalance: {CURRENCY_SYMBOL} {data['balance']:,}"
            color = 0x2ECC71
        else:
            data["balance"] -= amount
            data["losses"] = data.get("losses", 0) + 1
            result = f"💸 You **lost** {CURRENCY_SYMBOL} {amount:,}!\nBalance: {CURRENCY_SYMBOL} {data['balance']:,}"
            color = 0xE74C3C
        self.save(ctx, data)
        await ctx.send(embed=mk_embed("🎰 Gamble Result", result, color))

    @commands.command(name="give", aliases=["pay"])
    async def give(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            return await ctx.send(embed=mk_embed("❌ Error", "You can't pay yourself!", 0xE74C3C))
        data = self.bal(ctx)
        if amount <= 0 or amount > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Error", "Invalid amount.", 0xE74C3C))
        data["balance"] -= amount
        self.save(ctx, data)
        recv = get_balance(str(ctx.guild.id), str(member.id))
        recv["balance"] += amount
        set_balance(str(ctx.guild.id), str(member.id), recv)
        await ctx.send(embed=mk_embed("💸 Transfer Done", f"Sent **{CURRENCY_SYMBOL} {amount:,}** to {member.mention}"))

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        rows = get_top_currency(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=mk_embed("🏆 Leaderboard", "No data yet!"))
        desc = ""
        for i, row in enumerate(rows, 1):
            uid = row["key"].split("_")[1]
            desc += f"**{i}.** <@{uid}> — {CURRENCY_SYMBOL} {row['balance']:,}\n"
        await ctx.send(embed=mk_embed("🏆 Economy Leaderboard", desc))

async def setup(bot):
    await bot.add_cog(Currency(bot))
