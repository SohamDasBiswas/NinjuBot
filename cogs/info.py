import discord
from discord.ext import commands

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="credits", aliases=["creator", "about", "made"])
    async def credits(self, ctx):
        embed = discord.Embed(
            title="🤖 About NinjaBot",
            description=(
                "This bot was created by **sdb_darkninja**!\n\n"
                "🎮 **Twitch:** [sdb_darkninja](https://twitch.tv/sdb_darkninja)\n"
                "📺 **YouTube:** [sdb_darkninja](https://youtube.com/@sdb_darkninja)\n"
                "💬 **Discord:** @sdb_darkninja\n\n"
                "Go show some love and follow/subscribe! 🔥"
            ),
            color=0xFF4500
        )
        embed.set_footer(text="NinjaBot | Powered by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="hel")
    async def help(self, ctx):
        embed = discord.Embed(
            title="🎵 NinjaBot — Command List",
            description="Made by **sdb_darkninja** | Prefix: `-`",
            color=0x1DB954
        )
        embed.add_field(name="🎵 Music", value=(
            "`/play` or `-p <song>` — Play with suggestions\n"
            "`-play <song/url>` — Play directly\n"
            "`-skip` `-pause` `-resume` `-stop`\n"
            "`-queue` `-np` `-loop` `-volume`\n"
            "`-shuffle` `-remove <#>` `-lyrics`\n"
            "`-radio <genre>` `-eq <effect>` `-247`\n"
            "`-musictrivia` — Guess the song!"
        ), inline=False)
        embed.add_field(name="📋 Playlists", value=(
            "`-playlist save <n>` `-playlist play <n>`\n"
            "`-playlist list` `-playlist delete <n>`"
        ), inline=False)
        embed.add_field(name="📊 Twitch", value=(
            "`-twitchsetup [cat_id]` — Twitch VC channels\n"
            "`-twitchstats` — Live Twitch stats"
        ), inline=False)
        embed.add_field(name="🤖 AI", value=(
            "`-ask <q>` `-roast @user` `-compliment @user`\n"
            "`-chat` — Toggle AI chat in channel"
        ), inline=False)
        embed.add_field(name="📈 Levels", value=(
            "`-rank [@user]` `-leaderboard` `-serverinfo`"
        ), inline=False)
        embed.add_field(name="₹ Economy", value=(
            "`-balance` — Check your wallet\n"
            "`-daily` — Claim ₹500 daily reward\n"
            "`-work` — Work to earn coins (1h cooldown)\n"
            "`-give @user <amount>` — Send coins\n"
            "`-richlist` — Top 10 richest users\n"
            "`-gamble <amount>` — 45% to double\n"
            "`-slots <amount>` — Slot machine\n"
            "`-coinbet <amount> heads/tails` — Coin flip bet\n"
            "`-roulette <amount> red/black/green`\n"
            "`-blackjack <amount>` — Play Blackjack"
        ), inline=False)
        embed.add_field(name="🎮 Fun & Games", value=(
            "`-8ball <q>` `-coinflip` `-roll [dice]`\n"
            "`-wordle` `-tictactoe @user` `-rps [@user]`\n"
            "`-gtrivia` — Trivia quiz"
        ), inline=False)
        embed.add_field(name="🖼️ Images & Utils", value=(
            "`-meme` `-gif <q>` `-avatar [@user]`\n"
            "`-remind 10m <msg>` `-timer 5m`"
        ), inline=False)
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja 🔥")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
