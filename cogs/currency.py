import discord
from discord.ext import commands
import json
import os
import random
import asyncio
import time

CURRENCY_FILE = "currency.json"
CURRENCY_SYMBOL = "₹"
CURRENCY_NAME = "Rupees"

def load_currency():
    if os.path.exists(CURRENCY_FILE):
        with open(CURRENCY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_currency(data):
    with open(CURRENCY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_balance(data, guild_id, user_id):
    key = f"{guild_id}_{user_id}"
    return data.get(key, {"balance": 100, "last_daily": 0, "last_work": 0, "wins": 0, "losses": 0})

def set_balance(data, guild_id, user_id, user_data):
    key = f"{guild_id}_{user_id}"
    data[key] = user_data
    save_currency(data)

def mk_embed(title, desc, color=0xF1C40F):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text=f"{CURRENCY_SYMBOL} NinjaBot Economy | Made by sdb_darkninja")
    return e

class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_currency()

    def reload(self):
        self.data = load_currency()

    def bal(self, ctx, member=None):
        member = member or ctx.author
        return get_balance(self.data, str(ctx.guild.id), str(member.id))

    def save(self, ctx, user_data, member=None):
        member = member or ctx.author
        set_balance(self.data, str(ctx.guild.id), str(member.id), user_data)

    # ── -balance ──────────────────────────────────────────────────────────────
    @commands.command(name="balance", aliases=["bal", "wallet", "coins"])
    async def balance(self, ctx, member: discord.Member = None):
        """Check your virtual currency balance."""
        member = member or ctx.author
        data = get_balance(self.data, str(ctx.guild.id), str(member.id))
        embed = discord.Embed(title=f"👛 {member.display_name}'s Wallet", color=0xF1C40F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name=f"{CURRENCY_SYMBOL} Balance", value=f"**{data['balance']:,} {CURRENCY_NAME}**", inline=True)
        embed.add_field(name="🏆 Wins",   value=str(data.get("wins", 0)),   inline=True)
        embed.add_field(name="💀 Losses", value=str(data.get("losses", 0)), inline=True)
        embed.set_footer(text="NinjaBot Economy | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    # ── -daily ────────────────────────────────────────────────────────────────
    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily ₹500 reward."""
        data = self.bal(ctx)
        now = time.time()
        cooldown = 86400  # 24 hours
        remaining = data["last_daily"] + cooldown - now

        if remaining > 0:
            hrs = int(remaining // 3600)
            mins = int((remaining % 3600) // 60)
            return await ctx.send(embed=mk_embed("⏰ Already Claimed!", f"Come back in **{hrs}h {mins}m** for your daily reward.", color=0xFF6600))

        reward = random.randint(400, 600)
        data["balance"] += reward
        data["last_daily"] = now
        self.save(ctx, data)
        await ctx.send(embed=mk_embed("💰 Daily Reward!", f"You claimed **{CURRENCY_SYMBOL}{reward:,}**!\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0x2ECC71))

    # ── -work ─────────────────────────────────────────────────────────────────
    @commands.command(name="work")
    async def work(self, ctx):
        """Work to earn ₹50-₹200 (1 hour cooldown)."""
        data = self.bal(ctx)
        now = time.time()
        cooldown = 3600
        remaining = data["last_work"] + cooldown - now

        if remaining > 0:
            mins = int(remaining // 60)
            return await ctx.send(embed=mk_embed("⏰ Still Working!", f"Rest for **{mins} minutes** before working again.", color=0xFF6600))

        jobs = [
            ("🎮 streamed on Twitch", random.randint(50, 200)),
            ("🎵 made a YouTube video", random.randint(80, 250)),
            ("💻 fixed a bug", random.randint(50, 150)),
            ("🎨 designed a logo", random.randint(100, 200)),
            ("📦 delivered packages", random.randint(50, 120)),
            ("🍕 delivered pizza", random.randint(40, 100)),
        ]
        job, earned = random.choice(jobs)
        data["balance"] += earned
        data["last_work"] = now
        self.save(ctx, data)
        await ctx.send(embed=mk_embed("💼 Work Done!", f"You {job} and earned **{CURRENCY_SYMBOL}{earned:,}**!\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0x2ECC71))

    # ── -give @user amount ────────────────────────────────────────────────────
    @commands.command(name="give", aliases=["pay", "transfer"])
    async def give(self, ctx, member: discord.Member, amount: int):
        """Give coins to another user."""
        if member == ctx.author:
            return await ctx.send("❌ You can't give coins to yourself!")
        if amount <= 0:
            return await ctx.send("❌ Amount must be positive!")

        sender = self.bal(ctx)
        if sender["balance"] < amount:
            return await ctx.send(embed=mk_embed("❌ Insufficient Funds", f"You only have **{CURRENCY_SYMBOL}{sender['balance']:,}**!", color=0xFF0000))

        receiver = get_balance(self.data, str(ctx.guild.id), str(member.id))
        sender["balance"] -= amount
        receiver["balance"] += amount
        self.save(ctx, sender)
        set_balance(self.data, str(ctx.guild.id), str(member.id), receiver)

        await ctx.send(embed=mk_embed("💸 Transfer Done!", f"**{ctx.author.display_name}** gave **{CURRENCY_SYMBOL}{amount:,}** to **{member.display_name}**!", color=0x2ECC71))

    # ── -leaderboard (economy) ────────────────────────────────────────────────
    @commands.command(name="richlist", aliases=["rlb", "econlb"])
    async def richlist(self, ctx):
        """Top 10 richest users."""
        guild_id = str(ctx.guild.id)
        guild_data = {k: v for k, v in self.data.items() if k.startswith(guild_id)}
        if not guild_data:
            return await ctx.send("❌ No economy data yet!")

        sorted_users = sorted(guild_data.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        desc = ""
        for i, (key, udata) in enumerate(sorted_users):
            user_id = int(key.split("_")[1])
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            desc += f"{medal} **{name}** — {CURRENCY_SYMBOL}{udata['balance']:,}\n"

        await ctx.send(embed=mk_embed(f"💰 Richest in {ctx.guild.name}", desc))

    # ── -gamble amount ────────────────────────────────────────────────────────
    @commands.command(name="gamble", aliases=["bet"])
    async def gamble(self, ctx, amount: str):
        """Gamble your coins. 45% chance to double!"""
        data = self.bal(ctx)
        if amount.lower() == "all":
            amount = data["balance"]
        else:
            try:
                amount = int(amount)
            except:
                return await ctx.send("❌ Usage: `-gamble 100` or `-gamble all`")

        if amount <= 0:
            return await ctx.send("❌ Amount must be positive!")
        if amount > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Not Enough!", f"You only have **{CURRENCY_SYMBOL}{data['balance']:,}**!", color=0xFF0000))
        if amount > 10000:
            return await ctx.send(embed=mk_embed("❌ Too Much!", f"Max gamble is **{CURRENCY_SYMBOL}10,000** per bet!", color=0xFF0000))

        win = random.random() < 0.45
        if win:
            data["balance"] += amount
            data["wins"] = data.get("wins", 0) + 1
            self.save(ctx, data)
            await ctx.send(embed=mk_embed("🎰 You Won!", f"You bet **{CURRENCY_SYMBOL}{amount:,}** and **doubled it**!\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0x2ECC71))
        else:
            data["balance"] -= amount
            data["losses"] = data.get("losses", 0) + 1
            self.save(ctx, data)
            await ctx.send(embed=mk_embed("🎰 You Lost!", f"You bet **{CURRENCY_SYMBOL}{amount:,}** and lost it all!\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0xFF0000))

    # ── -slots amount ─────────────────────────────────────────────────────────
    @commands.command(name="slots")
    async def slots(self, ctx, amount: str = "50"):
        """Play the slot machine!"""
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send("❌ Usage: `-slots 100`")

        if bet <= 0:
            return await ctx.send("❌ Bet must be positive!")
        if bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Not Enough!", f"You only have **{CURRENCY_SYMBOL}{data['balance']:,}**!", color=0xFF0000))

        symbols = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
        weights = [30, 25, 20, 15, 6, 3, 1]

        reels = random.choices(symbols, weights=weights, k=3)
        result = " | ".join(reels)

        if reels[0] == reels[1] == reels[2]:
            if reels[0] == "7️⃣":
                mult = 10
            elif reels[0] == "💎":
                mult = 7
            elif reels[0] == "⭐":
                mult = 5
            else:
                mult = 3
            won = bet * mult
            data["balance"] += won
            data["wins"] = data.get("wins", 0) + 1
            msg = f"**JACKPOT! {reels[0]} {reels[0]} {reels[0]}!** {mult}x multiplier!\n+**{CURRENCY_SYMBOL}{won:,}**"
            color = 0xF1C40F
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            won = bet // 2
            data["balance"] += won
            msg = f"**{result}**\nTwo of a kind! +**{CURRENCY_SYMBOL}{won:,}**"
            color = 0x2ECC71
        else:
            data["balance"] -= bet
            data["losses"] = data.get("losses", 0) + 1
            won = -bet
            msg = f"**{result}**\nNo match! -**{CURRENCY_SYMBOL}{bet:,}**"
            color = 0xFF0000

        self.save(ctx, data)
        await ctx.send(embed=mk_embed(
            "🎰 Slot Machine",
            f"┌─────────────┐\n│  {result}  │\n└─────────────┘\n\n{msg}\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**",
            color=color
        ))

    # ── -coinbet amount heads/tails ───────────────────────────────────────────
    @commands.command(name="coinbet", aliases=["cbet"])
    async def coinbet(self, ctx, amount: str, choice: str = "heads"):
        """Bet on a coin flip. Usage: -coinbet 100 heads"""
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send("❌ Usage: `-coinbet 100 heads`")

        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Invalid Bet", f"Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0xFF0000))

        choice = choice.lower()
        if choice not in ("heads", "tails", "h", "t"):
            return await ctx.send("❌ Choose `heads` or `tails`!")

        result = random.choice(["heads", "tails"])
        won = choice in (result, result[0])

        if won:
            data["balance"] += bet
            data["wins"] = data.get("wins", 0) + 1
            self.save(ctx, data)
            await ctx.send(embed=mk_embed("🪙 You Won!", f"Coin landed on **{result.upper()}**!\n+**{CURRENCY_SYMBOL}{bet:,}**\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0x2ECC71))
        else:
            data["balance"] -= bet
            data["losses"] = data.get("losses", 0) + 1
            self.save(ctx, data)
            await ctx.send(embed=mk_embed("🪙 You Lost!", f"Coin landed on **{result.upper()}**!\n-**{CURRENCY_SYMBOL}{bet:,}**\n\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0xFF0000))

    # ── -roulette amount color ─────────────────────────────────────────────────
    @commands.command(name="roulette", aliases=["rl"])
    async def roulette(self, ctx, amount: str, color: str = "red"):
        """Bet on roulette! red/black = 2x, green = 14x. Usage: -roulette 100 red"""
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send("❌ Usage: `-roulette 100 red`")

        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Invalid Bet", f"Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0xFF0000))

        color = color.lower()
        if color not in ("red", "black", "green"):
            return await ctx.send("❌ Choose `red`, `black`, or `green`!")

        # 18 red, 18 black, 2 green (0, 00)
        spin = random.randint(0, 37)
        reds = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        if spin in (0, 37):
            result = "green"
            emoji = "🟢"
        elif spin in reds:
            result = "red"
            emoji = "🔴"
        else:
            result = "black"
            emoji = "⚫"

        if result == color:
            mult = 14 if color == "green" else 2
            winnings = bet * (mult - 1)
            data["balance"] += winnings
            data["wins"] = data.get("wins", 0) + 1
            self.save(ctx, data)
            await ctx.send(embed=mk_embed("🎡 Roulette", f"Ball landed on {emoji} **{result.upper()} ({spin})**!\n\n🎉 You won **{CURRENCY_SYMBOL}{winnings:,}**!\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0x2ECC71))
        else:
            data["balance"] -= bet
            data["losses"] = data.get("losses", 0) + 1
            self.save(ctx, data)
            await ctx.send(embed=mk_embed("🎡 Roulette", f"Ball landed on {emoji} **{result.upper()} ({spin})**!\n\n💀 You lost **{CURRENCY_SYMBOL}{bet:,}**!\n💰 Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0xFF0000))

    # ── -blackjack amount ─────────────────────────────────────────────────────
    @commands.command(name="blackjack", aliases=["bj"])
    async def blackjack(self, ctx, amount: str = "50"):
        """Play Blackjack! Get closer to 21 than the dealer."""
        data = self.bal(ctx)
        if amount.lower() == "all":
            bet = data["balance"]
        else:
            try:
                bet = int(amount)
            except:
                return await ctx.send("❌ Usage: `-blackjack 100`")

        if bet <= 0 or bet > data["balance"]:
            return await ctx.send(embed=mk_embed("❌ Invalid Bet", f"Balance: **{CURRENCY_SYMBOL}{data['balance']:,}**", color=0xFF0000))

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

        def hand_str(hand, hide_second=False):
            if hide_second:
                return f"{hand[0][0]} | ❓"
            return " | ".join(c for c, _ in hand)

        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        def make_embed(status="Your turn"):
            pval = hand_value(player)
            dval = hand_value(dealer)
            e = discord.Embed(title="🃏 Blackjack", color=0x2C3E50)
            e.add_field(name=f"Your Hand ({pval})", value=hand_str(player), inline=False)
            e.add_field(name="Dealer Hand", value=hand_str(dealer, hide_second=(status == "Your turn")), inline=False)
            e.add_field(name="Bet", value=f"{CURRENCY_SYMBOL}{bet:,}", inline=True)
            e.add_field(name="Balance", value=f"{CURRENCY_SYMBOL}{data['balance']:,}", inline=True)
            e.set_footer(text=f"{status} | React 👍 Hit | 👎 Stand")
            return e

        msg = await ctx.send(embed=make_embed())
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        def check(r, u): return u == ctx.author and str(r.emoji) in ("👍","👎") and r.message.id == msg.id

        while hand_value(player) < 21:
            try:
                r, _ = await self.bot.wait_for("reaction_add", timeout=30, check=check)
                if str(r.emoji) == "👍":
                    player.append(deck.pop())
                    if hand_value(player) > 21:
                        break
                    await msg.edit(embed=make_embed())
                else:
                    break
            except asyncio.TimeoutError:
                break

        # Dealer plays
        while hand_value(dealer) < 17:
            dealer.append(deck.pop())

        pval = hand_value(player)
        dval = hand_value(dealer)

        if pval > 21:
            result, color, change = "💀 Bust! You lose.", 0xFF0000, -bet
            data["losses"] = data.get("losses", 0) + 1
        elif dval > 21 or pval > dval:
            result, color, change = "🎉 You win!", 0x2ECC71, bet
            data["wins"] = data.get("wins", 0) + 1
        elif pval == dval:
            result, color, change = "🤝 Push! Tie.", 0xF1C40F, 0
        else:
            result, color, change = "💀 Dealer wins.", 0xFF0000, -bet
            data["losses"] = data.get("losses", 0) + 1

        data["balance"] += change
        self.save(ctx, data)

        e = discord.Embed(title=f"🃏 Blackjack — {result}", color=color)
        e.add_field(name=f"Your Hand ({pval})", value=hand_str(player), inline=False)
        e.add_field(name=f"Dealer Hand ({dval})", value=hand_str(dealer), inline=False)
        change_str = f"+{CURRENCY_SYMBOL}{change:,}" if change >= 0 else f"-{CURRENCY_SYMBOL}{abs(change):,}"
        e.add_field(name="Result", value=f"**{change_str}**", inline=True)
        e.add_field(name="Balance", value=f"{CURRENCY_SYMBOL}{data['balance']:,}", inline=True)
        e.set_footer(text="NinjaBot Economy | Made by sdb_darkninja")
        await msg.edit(embed=e)

async def setup(bot):
    await bot.add_cog(Currency(bot))
