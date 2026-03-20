import discord
from discord.ext import commands
import aiohttp
import asyncio
import re

def mk_embed(title, desc, color=0xE74C3C):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="🖼️ NinjaBot | Made by sdb_darkninja")
    return e

class Images(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = []

    # ── -meme ─────────────────────────────────────────────────────────────────
    @commands.command(name="meme")
    async def meme(self, ctx):
        """Get a random meme from Reddit."""
        subreddits = ["memes", "dankmemes", "me_irl", "wholesomememes", "gaming"]
        sub = subreddits[__import__("random").randint(0, len(subreddits)-1)]
        try:
            async with aiohttp.ClientSession() as s:
                resp = await s.get(
                    f"https://www.reddit.com/r/{sub}/random.json?limit=1",
                    headers={"User-Agent": "NinjaBot/1.0"},
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                data = await resp.json()
                post = data[0]["data"]["children"][0]["data"]
                if post.get("is_video") or not post.get("url", "").endswith(("jpg", "jpeg", "png", "gif")):
                    await self.meme(ctx)
                    return
                embed = discord.Embed(title=post["title"][:256], color=0xFF4500)
                embed.set_image(url=post["url"])
                embed.set_footer(text=f"👍 {post['ups']:,} | r/{sub} | NinjaBot by sdb_darkninja")
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(embed=mk_embed("❌ Error", f"Could not fetch meme: {e}", color=0xFF0000))

    # ── -gif <query> ──────────────────────────────────────────────────────────
    @commands.command(name="gif")
    async def gif(self, ctx, *, query: str):
        """Search and send a GIF."""
        try:
            async with aiohttp.ClientSession() as s:
                resp = await s.get(
                    "https://tenor.googleapis.com/v2/search",
                    params={
                        "q": query,
                        "key": "AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCYQ",
                        "limit": 20,
                        "contentfilter": "medium"
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                data = await resp.json()
                results = data.get("results", [])
                if not results:
                    return await ctx.send(embed=mk_embed("❌ No GIFs Found", f"No GIFs found for `{query}`"))
                item = __import__("random").choice(results[:10])
                url = item["media_formats"]["gif"]["url"]
                embed = discord.Embed(title=f"🎬 {query}", color=0x1DA1F2)
                embed.set_image(url=url)
                embed.set_footer(text="Powered by Tenor | NinjaBot by sdb_darkninja")
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(embed=mk_embed("❌ Error", str(e), color=0xFF0000))

    # ── -avatar @user ─────────────────────────────────────────────────────────
    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar(self, ctx, member: discord.Member = None):
        """Show someone's profile picture."""
        member = member or ctx.author
        embed = discord.Embed(title=f"🖼️ {member.display_name}'s Avatar", color=0x3498DB)
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(name="Download", value=f"[PNG]({member.display_avatar.with_format('png').url}) | [JPG]({member.display_avatar.with_format('jpg').url}) | [WEBP]({member.display_avatar.with_format('webp').url})")
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    # ── -remind ───────────────────────────────────────────────────────────────
    @commands.command(name="remind", aliases=["reminder"])
    async def remind(self, ctx, *, args: str):
        """Set a reminder. Usage: -remind 10m do something"""
        # Parse time from args
        match = re.match(r"(\d+)(s|m|h|d)\s*(.*)", args.strip())
        if not match:
            return await ctx.send(embed=mk_embed("❌ Usage", "`-remind 10m take a break`\nUnits: `s` sec, `m` min, `h` hours, `d` days", color=0xFF0000))

        amount = int(match.group(1))
        unit = match.group(2)
        message = match.group(3) or "Something!"

        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        seconds = amount * multipliers[unit]
        unit_names = {"s": "second", "m": "minute", "h": "hour", "d": "day"}

        await ctx.send(embed=mk_embed("⏰ Reminder Set!", f"I'll remind you in **{amount} {unit_names[unit]}{'s' if amount > 1 else ''}**\n📝 {message}", color=0x2ECC71))

        await asyncio.sleep(seconds)
        await ctx.send(embed=discord.Embed(
            title="⏰ Reminder!",
            description=f"{ctx.author.mention} You asked me to remind you:\n\n📝 **{message}**",
            color=0xF1C40F
        ).set_footer(text="NinjaBot | Made by sdb_darkninja"))

    # ── -timer ────────────────────────────────────────────────────────────────
    @commands.command(name="timer")
    async def timer(self, ctx, *, args: str):
        """Start a countdown timer. Usage: -timer 5m"""
        match = re.match(r"(\d+)(s|m|h)", args.strip())
        if not match:
            return await ctx.send(embed=mk_embed("❌ Usage", "`-timer 5m`\nUnits: `s` sec, `m` min, `h` hours", color=0xFF0000))

        amount = int(match.group(1))
        unit = match.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600}
        unit_names = {"s": "second", "m": "minute", "h": "hour"}
        seconds = amount * multipliers[unit]

        msg = await ctx.send(embed=mk_embed(
            "⏱️ Timer Started!",
            f"**{amount} {unit_names[unit]}{'s' if amount > 1 else ''}** countdown started!\nI'll ping you when done.",
            color=0xF1C40F
        ))

        await asyncio.sleep(seconds)
        await msg.edit(embed=mk_embed("✅ Timer Done!", f"**{amount} {unit_names[unit]}{'s' if amount > 1 else ''}** is up!", color=0x2ECC71))
        await ctx.send(f"⏰ {ctx.author.mention} Your **{amount}{unit}** timer is done!")

async def setup(bot):
    await bot.add_cog(Images(bot))
