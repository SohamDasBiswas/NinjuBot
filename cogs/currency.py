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
    e.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
    return e

# ── Confirm Gamble View ───────────────────────────────────────────────────────
class ConfirmView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=15)
        self.value = None
        self.author_id = author_id

    @discord.ui.button(label="Confirm", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        self.value = False
        self.stop()
        await interaction.response.defer()

# ── Blackjack View ────────────────────────────────────────────────────────────
class BlackjackView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=30)
        self.action = None
        self.author_id = author_id

    @discord.ui.button(label="Hit", emoji="👊", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Not your game!", ephemeral=True)
        self.action = "hit"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Stand", emoji="🛑", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Not your game!", ephemeral=True)
        self.action = "stand"
        self.stop()
        await interaction.response.defer()

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
        embed = discord.Embed(title=f"👛 {member.display_name}'s Wallet", color=0xF1C40F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name=f"{CURRENCY_SYMBOL} Balance", value=f"**{data['balance']:,} {CURRENCY_NAME}**", inline=True)
        embed.add_field(name="🏆 Wins", value=str(data.get("wins", 0)), inline=True)
        embed.add_field(name="💀 Losses", value=str(data.get("losses", 0)), inline=True)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="daily")
    async def daily(self, ctx):
        data = self.bal(ctx)
        now = time.time()
        remaining = 86400 - (now - data["last_daily"])
        if remaining > 0:
            h, m = divmod(int(remaining), 3600)
            m //= 60
            embed = discord.Embed(title="⏰ Already Claimed!", color=0xFF6600)
            embed.add_field(name="⏳ Cooldown", value=f"Come back in **{h}h {m}m**")
            embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
            return await ctx.send(embed=embed)
        reward = random.randint(100, 300)
        data["balance"] += reward
        data["last_daily"] = now
        self.save(ctx, data)
        embed = discord.Embed(title="💰 Daily Reward!", color=0x2ECC71)
        embed.add_field(name="Reward", value=f"**+{CURRENCY_SYMBOL}{reward:,}**", inline=True)
        embed.add_field(name="New Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="work")
    async def work(self, ctx):
        data = self.bal(ctx)
        now = time.time()
        remaining = 3600 - (now - data["last_work"])
        if remaining > 0:
            m = int(remaining // 60)
            return await ctx.send(embed=mk_embed("⏰ Still Working!", f"Rest for **{m} minutes** before working again.", 0xFF6600))
        jobs = [
            ("🎮 streamed on Twitch", random.randint(50, 200)),
            ("🎵 made a YouTube video", random.randint(80, 250)),
            ("💻 fixed a bug", random.randint(50, 150)),
            ("🎨 designed a logo", random.randint(100, 200)),
            ("📦 delivered packages", random.randint(50, 120)),
        ]
        job, earned = random.choice(jobs)
        data["balance"] += earned
        data["last_work"] = now
        self.save(ctx, data)
        embed = discord.Embed(title="💼 Work Complete!", color=0x2ECC71)
        embed.add_field(name="Job", value=f"You {job}", inline=False)
        embed.add_field(name="Earned", value=f"**+{CURRENCY_SYMBOL}{earned:,}**", inline=True)
        embed.add_field(name="Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

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
                return await ctx.send(embed=mk_embed("❌ Invalid Amount", "Use a number or `all`", 0xFF0000))
        if amount <= 0 or amount > bal:
            return await ctx.send(embed=mk_embed("❌ Invalid Amount", f"Your balance: {CURRENCY_SYMBOL}{bal:,}", 0xFF0000))

        view = ConfirmView(ctx.author.id)
        embed = discord.Embed(title="🎰 Confirm Gamble", color=0xFFAA00)
        embed.add_field(name="Bet", value=f"**{CURRENCY_SYMBOL}{amount:,}**", inline=True)
        embed.add_field(name="Balance", value=f"**{CURRENCY_SYMBOL}{bal:,}**", inline=True)
        embed.add_field(name="Win Chance", value="**50%**", inline=True)
        embed.set_footer(text="You have 15 seconds to confirm")
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if not view.value:
            return await msg.edit(embed=mk_embed("❌ Cancelled", "Gamble cancelled.", 0x808080), view=None)

        if random.random() > 0.5:
            data["balance"] += amount
            data["wins"] = data.get("wins", 0) + 1
            embed = discord.Embed(title="🎉 You Won!", color=0x2ECC71)
            embed.add_field(name="Winnings", value=f"**+{CURRENCY_SYMBOL}{amount:,}**", inline=True)
        else:
            data["balance"] -= amount
            data["losses"] = data.get("losses", 0) + 1
            embed = discord.Embed(title="💸 You Lost!", color=0xE74C3C)
            embed.add_field(name="Lost", value=f"**-{CURRENCY_SYMBOL}{amount:,}**", inline=True)
        embed.add_field(name="New Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        self.save(ctx, data)
        await msg.edit(embed=embed, view=None)

    @commands.command(name="give", aliases=["pay"])
    async def give(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            return await ctx.send(embed=mk_embed("❌ Error", "You can't pay yourself!", 0xFF0000))
        data = self.bal(ctx)
        if amount <= 0 or amount > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Insufficient Funds", f"Balance: {CURRENCY_SYMBOL}{data['balance']:,}", 0xFF0000))
        data["balance"] -= amount
        self.save(ctx, data)
        recv = get_balance(str(ctx.guild.id), str(member.id))
        recv["balance"] += amount
        set_balance(str(ctx.guild.id), str(member.id), recv)
        embed = discord.Embed(title="💸 Transfer Complete!", color=0x2ECC71)
        embed.add_field(name="From", value=ctx.author.mention, inline=True)
        embed.add_field(name="To", value=member.mention, inline=True)
        embed.add_field(name="Amount", value=f"**{CURRENCY_SYMBOL}{amount:,}**", inline=True)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "richlist"])
    async def leaderboard(self, ctx):
        rows = get_top_currency(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=mk_embed("🏆 Leaderboard", "No data yet! Start earning coins."))
        embed = discord.Embed(title=f"🏆 {ctx.guild.name} Economy Leaderboard", color=0xF1C40F)
        medals = ["🥇", "🥈", "🥉"]
        desc = ""
        for i, row in enumerate(rows, 1):
            uid = row["key"].split("_")[1]
            medal = medals[i-1] if i <= 3 else f"`#{i}`"
            desc += f"{medal} <@{uid}> — **{CURRENCY_SYMBOL}{row['balance']:,}**\n"
        embed.description = desc
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="slots")
    async def slots(self, ctx, amount: str = "50"):
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send(embed=mk_embed("❌ Invalid", "Usage: `-slots 100`", 0xFF0000))
        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Insufficient Funds", f"Balance: {CURRENCY_SYMBOL}{data['balance']:,}", 0xFF0000))

        symbols = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
        weights = [30, 25, 20, 15, 6, 3, 1]
        reels = random.choices(symbols, weights=weights, k=3)

        if reels[0] == reels[1] == reels[2]:
            mult = {"7️⃣": 10, "💎": 7, "⭐": 5}.get(reels[0], 3)
            won = bet * mult
            data["balance"] += won
            data["wins"] = data.get("wins", 0) + 1
            result = f"🎊 **JACKPOT! {mult}x multiplier!**\n+**{CURRENCY_SYMBOL}{won:,}**"
            color = 0xF1C40F
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            won = bet // 2
            data["balance"] += won
            result = f"Two of a kind!\n+**{CURRENCY_SYMBOL}{won:,}**"
            color = 0x2ECC71
        else:
            data["balance"] -= bet
            data["losses"] = data.get("losses", 0) + 1
            result = f"No match!\n-**{CURRENCY_SYMBOL}{bet:,}**"
            color = 0xFF0000

        self.save(ctx, data)
        embed = discord.Embed(title="🎰 Slot Machine", color=color)
        embed.add_field(name="Reels", value=f"┌──────────────┐\n│  {' '.join(reels)}  │\n└──────────────┘", inline=False)
        embed.add_field(name="Result", value=result, inline=True)
        embed.add_field(name="Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="coinbet", aliases=["cbet"])
    async def coinbet(self, ctx, amount: str, choice: str = "heads"):
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send(embed=mk_embed("❌ Invalid", "Usage: `-coinbet 100 heads`", 0xFF0000))
        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Invalid Bet", f"Balance: {CURRENCY_SYMBOL}{data['balance']:,}", 0xFF0000))
        choice = choice.lower()
        if choice not in ("heads", "tails", "h", "t"):
            return await ctx.send(embed=mk_embed("❌ Invalid Choice", "Choose `heads` or `tails`!", 0xFF0000))
        result = random.choice(["heads", "tails"])
        won = choice in (result, result[0])
        if won:
            data["balance"] += bet
            data["wins"] = data.get("wins", 0) + 1
            embed = discord.Embed(title="🪙 You Won!", color=0x2ECC71)
            embed.add_field(name="Result", value=f"Coin landed **{result.upper()}**!", inline=False)
            embed.add_field(name="Won", value=f"**+{CURRENCY_SYMBOL}{bet:,}**", inline=True)
        else:
            data["balance"] -= bet
            data["losses"] = data.get("losses", 0) + 1
            embed = discord.Embed(title="🪙 You Lost!", color=0xE74C3C)
            embed.add_field(name="Result", value=f"Coin landed **{result.upper()}**!", inline=False)
            embed.add_field(name="Lost", value=f"**-{CURRENCY_SYMBOL}{bet:,}**", inline=True)
        embed.add_field(name="Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        self.save(ctx, data)
        await ctx.send(embed=embed)

    @commands.command(name="roulette", aliases=["rl"])
    async def roulette(self, ctx, amount: str, color: str = "red"):
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send(embed=mk_embed("❌ Invalid", "Usage: `-roulette 100 red`", 0xFF0000))
        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Invalid Bet", f"Balance: {CURRENCY_SYMBOL}{data['balance']:,}", 0xFF0000))
        color = color.lower()
        if color not in ("red", "black", "green"):
            return await ctx.send(embed=mk_embed("❌ Invalid Color", "Choose `red`, `black`, or `green`!", 0xFF0000))
        spin = random.randint(0, 37)
        reds = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        if spin in (0, 37):
            result, emoji = "green", "🟢"
        elif spin in reds:
            result, emoji = "red", "🔴"
        else:
            result, emoji = "black", "⚫"
        if result == color:
            mult = 14 if color == "green" else 2
            winnings = bet * (mult - 1)
            data["balance"] += winnings
            data["wins"] = data.get("wins", 0) + 1
            embed = discord.Embed(title=f"🎡 {emoji} You Won!", color=0x2ECC71)
            embed.add_field(name="Spin", value=f"**{result.upper()} ({spin})**", inline=True)
            embed.add_field(name="Won", value=f"**+{CURRENCY_SYMBOL}{winnings:,}**", inline=True)
        else:
            data["balance"] -= bet
            data["losses"] = data.get("losses", 0) + 1
            embed = discord.Embed(title=f"🎡 {emoji} You Lost!", color=0xE74C3C)
            embed.add_field(name="Spin", value=f"**{result.upper()} ({spin})**", inline=True)
            embed.add_field(name="Lost", value=f"**-{CURRENCY_SYMBOL}{bet:,}**", inline=True)
        embed.add_field(name="Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        embed.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        self.save(ctx, data)
        await ctx.send(embed=embed)

    @commands.command(name="blackjack", aliases=["bj"])
    async def blackjack(self, ctx, amount: str = "50"):
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send(embed=mk_embed("❌ Invalid", "Usage: `-blackjack 100`", 0xFF0000))
        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Invalid Bet", f"Balance: {CURRENCY_SYMBOL}{data['balance']:,}", 0xFF0000))

        suits = ["♠️","♥️","♦️","♣️"]
        values = {"A":11,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":10,"Q":10,"K":10}
        deck = [(f"{v}{s}", values[v]) for s in suits for v in values]
        random.shuffle(deck)

        def hand_value(hand):
            total = sum(v for _, v in hand)
            aces = sum(1 for c, _ in hand if c[0] == "A")
            while total > 21 and aces:
                total -= 10
                aces -= 1
            return total

        def hand_str(hand, hide=False):
            if hide:
                return f"{hand[0][0]} | ❓"
            return " | ".join(c for c, _ in hand)

        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        def make_embed(status="Your turn"):
            pval = hand_value(player)
            e = discord.Embed(title="🃏 Blackjack", color=0x2C3E50)
            e.add_field(name=f"Your Hand ({pval})", value=hand_str(player), inline=False)
            e.add_field(name="Dealer Hand", value=hand_str(dealer, hide=(status == "Your turn")), inline=False)
            e.add_field(name="Bet", value=f"{CURRENCY_SYMBOL}{bet:,}", inline=True)
            e.add_field(name="Balance", value=f"{CURRENCY_SYMBOL}{data['balance']:,}", inline=True)
            e.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
            return e

        msg = await ctx.send(embed=make_embed(), view=BlackjackView(ctx.author.id))

        while hand_value(player) < 21:
            view = BlackjackView(ctx.author.id)
            await msg.edit(embed=make_embed(), view=view)
            await view.wait()
            if view.action == "hit":
                player.append(deck.pop())
                if hand_value(player) > 21:
                    break
            else:
                break

        while hand_value(dealer) < 17:
            dealer.append(deck.pop())

        pval = hand_value(player)
        dval = hand_value(dealer)

        if pval > 21:
            result, color, change = "💀 Bust!", 0xFF0000, -bet
            data["losses"] = data.get("losses", 0) + 1
        elif dval > 21 or pval > dval:
            result, color, change = "🎉 You Win!", 0x2ECC71, bet
            data["wins"] = data.get("wins", 0) + 1
        elif pval == dval:
            result, color, change = "🤝 Push! Tie.", 0xF1C40F, 0
        else:
            result, color, change = "💀 Dealer Wins.", 0xFF0000, -bet
            data["losses"] = data.get("losses", 0) + 1

        data["balance"] += change
        self.save(ctx, data)

        e = discord.Embed(title=f"🃏 {result}", color=color)
        e.add_field(name=f"Your Hand ({pval})", value=hand_str(player), inline=False)
        e.add_field(name=f"Dealer Hand ({dval})", value=hand_str(dealer), inline=False)
        change_str = f"+{CURRENCY_SYMBOL}{change:,}" if change >= 0 else f"-{CURRENCY_SYMBOL}{abs(change):,}"
        e.add_field(name="Result", value=f"**{change_str}**", inline=True)
        e.add_field(name="Balance", value=f"{CURRENCY_SYMBOL}{data['balance']:,}", inline=True)
        e.set_footer(text=f"{CURRENCY_SYMBOL} NinjuBot Economy | Made by sdb_darkninja")
        await msg.edit(embed=e, view=None)


    # ── Admin: Generate Currency (sdb_darkninja only) ─────────────────────────
    OWNER_ID = 769225445803032617

    @commands.command(name="addcoins", aliases=["givecoins", "gencoins"])
    async def addcoins(self, ctx, member: discord.Member, amount: int):
        """Generate coins for a user. Owner only."""
        if ctx.author.id != self.OWNER_ID:
            return await ctx.send(embed=mk_embed(
                "⛔ Access Denied",
                "Only **sdb_darkninja** can generate currency.",
                0xFF0000
            ))
        if amount <= 0:
            return await ctx.send(embed=mk_embed("❌ Invalid Amount", "Amount must be positive.", 0xFF0000))

        data = get_balance(str(ctx.guild.id), str(member.id))
        data["balance"] += amount
        set_balance(str(ctx.guild.id), str(member.id), data)

        e = mk_embed(
            "💸 Coins Generated",
            f"Added **{CURRENCY_SYMBOL}{amount:,}** to {member.mention}'s wallet.",
            0x00FF88
        )
        e.add_field(name="New Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        e.add_field(name="Generated by", value=f"👑 {ctx.author.display_name}", inline=True)
        await ctx.send(embed=e)

    @commands.command(name="removecoins", aliases=["deductcoins"])
    async def removecoins(self, ctx, member: discord.Member, amount: int):
        """Remove coins from a user. Owner only."""
        if ctx.author.id != self.OWNER_ID:
            return await ctx.send(embed=mk_embed(
                "⛔ Access Denied",
                "Only **sdb_darkninja** can remove currency.",
                0xFF0000
            ))
        if amount <= 0:
            return await ctx.send(embed=mk_embed("❌ Invalid Amount", "Amount must be positive.", 0xFF0000))

        data = get_balance(str(ctx.guild.id), str(member.id))
        data["balance"] = max(0, data["balance"] - amount)
        set_balance(str(ctx.guild.id), str(member.id), data)

        e = mk_embed(
            "🗑️ Coins Removed",
            f"Removed **{CURRENCY_SYMBOL}{amount:,}** from {member.mention}'s wallet.",
            0xFF6B6B
        )
        e.add_field(name="New Balance", value=f"**{CURRENCY_SYMBOL}{data['balance']:,}**", inline=True)
        await ctx.send(embed=e)

    @commands.command(name="setcoins")
    async def setcoins(self, ctx, member: discord.Member, amount: int):
        """Set a user's balance to an exact amount. Owner only."""
        if ctx.author.id != self.OWNER_ID:
            return await ctx.send(embed=mk_embed(
                "⛔ Access Denied",
                "Only **sdb_darkninja** can set balances.",
                0xFF0000
            ))
        if amount < 0:
            return await ctx.send(embed=mk_embed("❌ Invalid Amount", "Amount cannot be negative.", 0xFF0000))

        data = get_balance(str(ctx.guild.id), str(member.id))
        data["balance"] = amount
        set_balance(str(ctx.guild.id), str(member.id), data)

        e = mk_embed(
            "⚙️ Balance Set",
            f"Set {member.mention}'s balance to **{CURRENCY_SYMBOL}{amount:,}**.",
            0x3498DB
        )
        await ctx.send(embed=e)

    @commands.command(name="resetcoins")
    async def resetcoins(self, ctx, member: discord.Member):
        """Reset a user's balance to 0. Owner only."""
        if ctx.author.id != self.OWNER_ID:
            return await ctx.send(embed=mk_embed(
                "⛔ Access Denied",
                "Only **sdb_darkninja** can reset balances.",
                0xFF0000
            ))
        data = get_balance(str(ctx.guild.id), str(member.id))
        data["balance"] = 0
        set_balance(str(ctx.guild.id), str(member.id), data)
        await ctx.send(embed=mk_embed("🔄 Balance Reset", f"{member.mention}'s balance has been reset to **{CURRENCY_SYMBOL}0**.", 0xFFA500))

async def setup(bot):
    await bot.add_cog(Currency(bot))
