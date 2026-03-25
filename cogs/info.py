import discord
from discord.ext import commands
from datetime import datetime, timezone

PAGES = {
    "🎵 Music": {
        "color": 0x1DB954,
        "fields": [
            ("Playback", "`/play` or `-p <song>` — Play with live suggestions\n`-skip` `-pause` `-resume` `-stop` `-np`\n`-queue` `-loop [song/queue/none]` `-volume <1-100>`"),
            ("Discovery", "`-search <query>` — Pick from top 5 results\n`-radio <genre>` — pop, hiphop, rock, lofi, jazz, bollywood\n`-lyrics [song]` — Fetch song lyrics"),
            ("Queue Tools", "`-shuffle` — Randomize queue\n`-remove <#>` — Remove song by position\n`-247` — Stay in VC forever\n`-eq <effect>` — bassboost, nightcore, vaporwave"),
            ("Playlists", "`-playlist save <n>` — Save current queue\n`-playlist play <n>` — Load saved playlist\n`-playlist list` — Show all playlists\n`-playlist delete <n>` — Delete playlist"),
        ]
    },
    "📊 Twitch": {
        "color": 0x9146FF,
        "fields": [
            ("Setup", "`-twitchsetup [category_id]` — Create live VC stats channels\n`-twitchstats` — Show current Twitch stats\n`-twitchreset` — Delete saved channel IDs"),
            ("Auto-Update", "Channels update every **5 minutes** automatically\nTracks: Followers, Live Status, Viewers, Game"),
        ]
    },
    "🤖 AI": {
        "color": 0x9B59B6,
        "fields": [
            ("Commands", "`-ask <question>` — Ask AI anything\n`-roast @user` — AI roasts a user 🔥\n`-compliment @user` — AI compliments a user 💖\n`-chat` — Toggle AI auto-reply in channel"),
        ]
    },
    "📈 Levels": {
        "color": 0x3498DB,
        "fields": [
            ("XP System", "`-rank [@user]` — View your rank card\n`-toplevel` — Top 10 most active members\n`-serverinfo` — Detailed server stats"),
            ("How it Works", "Earn **10-25 XP** per message (60s cooldown)\nLevel up formula: `Level = √(XP/100)`\nLevel-up announcement in chat automatically"),
        ]
    },
    "💰 Economy": {
        "color": 0xF1C40F,
        "fields": [
            ("Earning", "`-balance [@user]` — Check wallet\n`-daily` — Claim ₹100-300 daily\n`-work` — Earn ₹30-100 (1h cooldown)\n`-give @user <amount>` — Transfer coins"),
            ("Gambling", "`-gamble <amount/all>` — 50% to double\n`-slots <amount>` — Slot machine 🎰\n`-coinbet <amount> heads/tails` — Coin flip\n`-roulette <amount> red/black/green` — Roulette\n`-blackjack <amount>` — Play Blackjack 🃏"),
            ("Leaderboard", "`-leaderboard` — Top 10 richest users"),
        ]
    },
    "🎮 Fun": {
        "color": 0xE67E22,
        "fields": [
            ("Games", "`-wordle` — Play Wordle 🟩\n`-tictactoe @user` — Tic Tac Toe ❌⭕\n`-rps [@user]` — Rock Paper Scissors ✊\n`-gtrivia` — Multiple choice trivia quiz\n`-musictrivia` — Guess the song! 🎵"),
            ("🎭 Truth or Dare", "`-tod @user` — Challenge someone to Truth or Dare!\n`-tod @user` — Same command, short alias\nAI generates **funny Hinglish** truths & dares 🤖\nButtons: 🤔 Truth • 🔥 Dare • 🎲 Random"),
            ("Utils", "`-8ball <question>` — Magic 8 ball 🎱\n`-coinflip` — Flip a coin 🪙\n`-roll [NdN]` — Roll dice 🎲\n`-meme` — Random meme 😂\n`-gif <query>` — Search GIFs\n`-avatar [@user]` — Get avatar"),
            ("Reminders", "`-remind <time> <message>` — Set reminder\n`-timer <time>` — Countdown timer"),
        ]
    },
}

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name.split(" ", 1)[1], emoji=name.split(" ")[0], value=name)
            for name in PAGES
        ]
        super().__init__(placeholder="📖 Select a category...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        name = self.values[0]
        page = PAGES[name]
        embed = discord.Embed(title=f"{name} Commands", color=page["color"])
        embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        for fname, fval in page["fields"]:
            embed.add_field(name=fname, value=fval, inline=False)
        embed.set_footer(text="NinjuBot | Made by sdb_darkninja 🔥")
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())

    @discord.ui.button(label="Home", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = make_home_embed(interaction.client)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Twitch", emoji="🎮", style=discord.ButtonStyle.secondary, row=1)
    async def twitch_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎮 Twitch: https://twitch.tv/sdb_darkninja", ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

def make_home_embed(client):
    embed = discord.Embed(
        title="🥷 NinjuBot — Ninja Dojo",
        description=(
            "Welcome to **NinjuBot** — your all-in-one Discord companion!\n\n"
            "**Select a category below** to explore commands.\n\n"
            "**Quick Start:**\n"
            "🎵 `/play <song>` — Play music instantly\n"
            "💰 `-daily` — Claim your daily coins\n"
            "🤖 `-ask <question>` — Chat with AI\n"
            "🎮 `-wordle` — Play Wordle"
        ),
        color=0xFF4500
    )
    embed.add_field(
        name="📦 Categories",
        value="🎵 Music • 📊 Twitch • 🤖 AI\n📈 Levels • 💰 Economy • 🎮 Fun",
        inline=False
    )
    embed.set_thumbnail(url=client.user.display_avatar.url)
    embed.set_footer(text="NinjuBot | Made by sdb_darkninja 🔥 | Prefix: - | Use -ninju for help")
    embed.timestamp = datetime.now(timezone.utc)
    return embed

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ninju", aliases=["ninjubot", "menu", "guide", "bot"])
    async def ninja_help(self, ctx):
        view = HelpView()
        embed = make_home_embed(ctx.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="credits", aliases=["creator", "about", "made"])
    async def credits(self, ctx):
        embed = discord.Embed(
            title="🥷 About NinjuBot",
            description=(
                "Built with ❤️ by **sdb_darkninja**\n\n"
                "🎮 **Twitch:** [sdb_darkninja](https://twitch.tv/sdb_darkninja)\n"
                "📺 **YouTube:** [sdb_darkninja](https://youtube.com/@sdb_darkninja)\n"
                "💬 **Discord:** @sdb_darkninja\n\n"
                "Go show some love and follow/subscribe! 🔥"
            ),
            color=0xFF4500
        )
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        embed.set_footer(text="NinjuBot | Powered by sdb_darkninja")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
