import discord
from discord.ext import commands
import random
import asyncio

WORDLE_WORDS = [
    "apple", "brave", "crane", "dance", "eagle", "flame", "grace", "heart",
    "ivory", "joker", "kneel", "light", "music", "night", "ocean", "piano",
    "queen", "river", "storm", "tiger", "ultra", "valor", "water", "xenon",
    "youth", "zebra", "blaze", "chess", "drift", "evoke", "frost", "glide",
    "haste", "inlet", "juice", "karma", "lemon", "maple", "noble", "orbit",
    "pixel", "quest", "realm", "shine", "trace", "unity", "vivid", "width"
]

TRIVIA_QUESTIONS = [
    {"q": "What is the capital of France?", "a": "paris", "opts": ["London", "Berlin", "Paris", "Rome"]},
    {"q": "How many sides does a hexagon have?", "a": "6", "opts": ["5", "6", "7", "8"]},
    {"q": "What planet is closest to the Sun?", "a": "mercury", "opts": ["Venus", "Earth", "Mercury", "Mars"]},
    {"q": "What is the largest ocean?", "a": "pacific", "opts": ["Atlantic", "Indian", "Arctic", "Pacific"]},
    {"q": "Who painted the Mona Lisa?", "a": "da vinci", "opts": ["Picasso", "Da Vinci", "Monet", "Rembrandt"]},
    {"q": "What is 12 × 12?", "a": "144", "opts": ["124", "132", "144", "156"]},
    {"q": "What gas do plants absorb?", "a": "co2", "opts": ["Oxygen", "CO2", "Nitrogen", "Hydrogen"]},
    {"q": "How many bones in the human body?", "a": "206", "opts": ["186", "196", "206", "216"]},
    {"q": "What is the fastest land animal?", "a": "cheetah", "opts": ["Lion", "Cheetah", "Horse", "Leopard"]},
    {"q": "In what year did WW2 end?", "a": "1945", "opts": ["1943", "1944", "1945", "1946"]},
]

EIGHT_BALL = [
    "✅ It is certain.", "✅ Without a doubt.", "✅ Yes, definitely!",
    "✅ You may rely on it.", "✅ Most likely.", "🤔 Ask again later.",
    "🤔 Cannot predict now.", "🤔 Concentrate and ask again.",
    "❌ Don't count on it.", "❌ Very doubtful.", "❌ My reply is no.",
]

def mk_embed(title, desc, color=0xE74C3C):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="🎮 NinjaBot | Made by sdb_darkninja")
    return e

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wordle_games = {}   # user_id -> game state
        self.ttt_games = {}      # channel_id -> game state
        self.rps_games = {}      # channel_id -> game state

    # ── -8ball ────────────────────────────────────────────────────────────────
    @commands.command(name="8ball", aliases=["8b"])
    async def eight_ball(self, ctx, *, question: str):
        """Ask the magic 8 ball."""
        answer = random.choice(EIGHT_BALL)
        embed = discord.Embed(title="🎱 Magic 8 Ball", color=0x2C3E50)
        embed.add_field(name="❓ Question", value=question, inline=False)
        embed.add_field(name="🎱 Answer",   value=answer,   inline=False)
        embed.set_footer(text="NinjaBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    # ── -coinflip ─────────────────────────────────────────────────────────────
    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip(self, ctx):
        """Flip a coin."""
        result = random.choice(["🪙 Heads!", "🪙 Tails!"])
        await ctx.send(embed=mk_embed("🪙 Coin Flip", result, color=0xF1C40F))

    # ── -roll ─────────────────────────────────────────────────────────────────
    @commands.command(name="roll")
    async def roll(self, ctx, dice: str = "6"):
        """Roll a dice. Usage: -roll 20 or -roll 2d6"""
        try:
            if "d" in dice.lower():
                parts = dice.lower().split("d")
                count = int(parts[0]) if parts[0] else 1
                sides = int(parts[1])
                count = min(count, 10)
                rolls = [random.randint(1, sides) for _ in range(count)]
                desc = f"Rolling **{count}d{sides}**\n\n"
                desc += " + ".join(f"`{r}`" for r in rolls)
                desc += f"\n\n**Total: {sum(rolls)}**"
            else:
                sides = int(dice)
                result = random.randint(1, sides)
                desc = f"Rolling **d{sides}**\n\n🎲 **{result}**"
            await ctx.send(embed=mk_embed("🎲 Dice Roll", desc, color=0xE74C3C))
        except:
            await ctx.send("❌ Usage: `-roll 20` or `-roll 2d6`")

    # ── -trivia ───────────────────────────────────────────────────────────────
    @commands.command(name="gtrivia", aliases=["quiz"])
    async def gtrivia(self, ctx):
        """General knowledge trivia question."""
        q = random.choice(TRIVIA_QUESTIONS)
        options = q["opts"].copy()
        random.shuffle(options)

        letters = ["🇦", "🇧", "🇨", "🇩"]
        desc = "\n".join(f"{letters[i]} {opt}" for i, opt in enumerate(options))
        correct_letter = letters[options.index(next(o for o in options if o.lower().replace(" ", "") == q["a"].replace(" ", "")))]

        embed = discord.Embed(title="🧠 Trivia Question!", description=f"**{q['q']}**\n\n{desc}", color=0x3498DB)
        embed.set_footer(text="You have 15 seconds! | NinjaBot by sdb_darkninja")
        msg = await ctx.send(embed=embed)

        for letter in letters:
            await msg.add_reaction(letter)

        def check(reaction, user):
            return user != self.bot.user and str(reaction.emoji) in letters and reaction.message.id == msg.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=15.0, check=check)
            if str(reaction.emoji) == correct_letter:
                await ctx.send(embed=mk_embed("✅ Correct!", f"**{user.mention}** got it right!\nAnswer: **{q['opts'][options.index(next(o for o in options if o.lower().replace(' ','') == q['a'].replace(' ','')))]}**", color=0x2ECC71))
            else:
                await ctx.send(embed=mk_embed("❌ Wrong!", f"**{user.mention}** got it wrong!\nCorrect answer: **{q['opts'][options.index(next(o for o in options if o.lower().replace(' ','') == q['a'].replace(' ','')))]}**", color=0xFF0000))
        except asyncio.TimeoutError:
            await ctx.send(embed=mk_embed("⏱️ Time's Up!", f"Nobody answered!\nCorrect answer was: **{q['opts'][options.index(next(o for o in options if o.lower().replace(' ','') == q['a'].replace(' ','')))]}**", color=0xFF6600))

    # ── -wordle ───────────────────────────────────────────────────────────────
    @commands.command(name="wordle")
    async def wordle(self, ctx):
        """Play Wordle! Guess the 5-letter word in 6 tries."""
        user_id = ctx.author.id
        if user_id in self.wordle_games:
            game = self.wordle_games[user_id]
            await ctx.send(embed=mk_embed("🟩 Wordle", f"You already have a game running!\nGuesses left: **{6 - len(game['guesses'])}**\nType a 5-letter word to guess."))
            return

        word = random.choice(WORDLE_WORDS).upper()
        self.wordle_games[user_id] = {"word": word, "guesses": [], "channel": ctx.channel.id}

        await ctx.send(embed=mk_embed("🟩 Wordle", (
            f"I've picked a **5-letter word**!\n"
            f"You have **6 tries** to guess it.\n\n"
            f"🟩 = Correct position\n"
            f"🟨 = Wrong position\n"
            f"⬛ = Not in word\n\n"
            f"Type a 5-letter word to start!"
        ), color=0x2ECC71))

        def check(m):
            return m.author.id == user_id and m.channel == ctx.channel and len(m.content) == 5 and m.content.isalpha()

        for attempt in range(6):
            try:
                guess_msg = await self.bot.wait_for("message", check=check, timeout=60)
                guess = guess_msg.content.upper()
                game = self.wordle_games.get(user_id)
                if not game:
                    return

                result = ""
                for i, ch in enumerate(guess):
                    if ch == word[i]:
                        result += "🟩"
                    elif ch in word:
                        result += "🟨"
                    else:
                        result += "⬛"

                game["guesses"].append(f"`{guess}` {result}")
                board = "\n".join(game["guesses"])

                if guess == word:
                    del self.wordle_games[user_id]
                    await ctx.send(embed=mk_embed("🎉 You Won!", f"{board}\n\nGuessed in **{attempt+1}/6** tries!", color=0x2ECC71))
                    return
                elif attempt == 5:
                    del self.wordle_games[user_id]
                    await ctx.send(embed=mk_embed("❌ Game Over", f"{board}\n\nThe word was **{word}**!", color=0xFF0000))
                    return
                else:
                    await ctx.send(embed=mk_embed(f"Wordle — Attempt {attempt+2}/6", board, color=0xF1C40F))

            except asyncio.TimeoutError:
                if user_id in self.wordle_games:
                    word = self.wordle_games[user_id]["word"]
                    del self.wordle_games[user_id]
                await ctx.send(embed=mk_embed("⏱️ Wordle Timed Out", f"The word was **{word}**!", color=0xFF6600))
                return

    # ── -tictactoe @user ──────────────────────────────────────────────────────
    @commands.command(name="tictactoe", aliases=["ttt"])
    async def tictactoe(self, ctx, opponent: discord.Member):
        """Play Tic Tac Toe against another user."""
        if opponent.bot or opponent == ctx.author:
            return await ctx.send("❌ Pick a valid opponent!")

        board = [" "] * 9
        players = {ctx.author: "❌", opponent: "⭕"}
        turn = ctx.author
        nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣"]

        def render():
            rows = ""
            for i in range(0, 9, 3):
                row = []
                for j in range(3):
                    cell = board[i+j]
                    row.append(cell if cell != " " else nums[i+j])
                rows += " | ".join(row) + "\n"
            return rows

        def check_win(symbol):
            wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
            return any(board[a]==board[b]==board[c]==symbol for a,b,c in wins)

        msg = await ctx.send(embed=mk_embed(
            "🎮 Tic Tac Toe",
            f"{ctx.author.mention} ❌ vs {opponent.mention} ⭕\n\n{render()}\n{turn.mention}'s turn!",
            color=0x3498DB
        ))
        for num in nums:
            await msg.add_reaction(num)

        for _ in range(9):
            def check(reaction, user):
                return user == turn and str(reaction.emoji) in nums and reaction.message.id == msg.id

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30, check=check)
                idx = nums.index(str(reaction.emoji))
                if board[idx] != " ":
                    await ctx.send("❌ That spot is taken! Pick another.", delete_after=3)
                    continue

                board[idx] = players[turn]
                symbol = players[turn]

                if check_win(symbol):
                    await msg.edit(embed=mk_embed("🎉 Game Over!", f"{render()}\n**{turn.mention} wins!**", color=0x2ECC71))
                    return
                elif " " not in board:
                    await msg.edit(embed=mk_embed("🤝 Draw!", f"{render()}\nIt's a tie!", color=0xF1C40F))
                    return

                turn = opponent if turn == ctx.author else ctx.author
                await msg.edit(embed=mk_embed("🎮 Tic Tac Toe", f"{ctx.author.mention} ❌ vs {opponent.mention} ⭕\n\n{render()}\n{turn.mention}'s turn!", color=0x3498DB))

            except asyncio.TimeoutError:
                await ctx.send(embed=mk_embed("⏱️ Time's Up!", f"**{turn.mention}** took too long! Game over.", color=0xFF6600))
                return

    # ── -rps @user ────────────────────────────────────────────────────────────
    @commands.command(name="rps")
    async def rps(self, ctx, opponent: discord.Member = None):
        """Rock Paper Scissors against another user or the bot."""
        choices = {"🪨": "Rock", "📄": "Paper", "✂️": "Scissors"}
        beats = {"🪨": "✂️", "📄": "🪨", "✂️": "📄"}

        if not opponent or opponent.bot:
            # vs bot
            await ctx.send(embed=mk_embed("✊ Rock Paper Scissors", "Pick your choice!", color=0x9B59B6))
            msg = await ctx.send("🪨 📄 ✂️")
            for emoji in ["🪨", "📄", "✂️"]:
                await msg.add_reaction(emoji)

            def check(r, u): return u == ctx.author and str(r.emoji) in choices and r.message.id == msg.id
            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=20, check=check)
                player = str(reaction.emoji)
                bot_choice = random.choice(list(choices.keys()))

                if player == bot_choice:
                    result = "🤝 It's a tie!"
                    color = 0xF1C40F
                elif beats[player] == bot_choice:
                    result = "🎉 You win!"
                    color = 0x2ECC71
                else:
                    result = "❌ Bot wins!"
                    color = 0xFF0000

                await msg.edit(embed=mk_embed("✊ RPS Result", f"You: {player} {choices[player]}\nBot: {bot_choice} {choices[bot_choice]}\n\n**{result}**", color=color))
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Timed out!")
        else:
            # vs player
            p1_choice = None
            p2_choice = None

            for player, label in [(ctx.author, "Player 1"), (opponent, "Player 2")]:
                try:
                    dm = await player.send(embed=mk_embed("✊ RPS", f"Pick your choice for the game against **{ctx.author.name if player == opponent else opponent.name}**!\n🪨 📄 ✂️", color=0x9B59B6))
                    for emoji in ["🪨", "📄", "✂️"]:
                        await dm.add_reaction(emoji)
                    def check(r, u): return u == player and str(r.emoji) in choices and r.message.id == dm.id
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=30, check=check)
                    if player == ctx.author:
                        p1_choice = str(reaction.emoji)
                    else:
                        p2_choice = str(reaction.emoji)
                except:
                    await ctx.send(f"❌ Couldn't DM {player.mention}. Enable DMs and try again.")
                    return

            if p1_choice == p2_choice:
                result = "🤝 It's a tie!"
                color = 0xF1C40F
            elif beats[p1_choice] == p2_choice:
                result = f"🎉 {ctx.author.mention} wins!"
                color = 0x2ECC71
            else:
                result = f"🎉 {opponent.mention} wins!"
                color = 0x2ECC71

            await ctx.send(embed=mk_embed("✊ RPS Result",
                f"{ctx.author.mention}: {p1_choice} {choices[p1_choice]}\n"
                f"{opponent.mention}: {p2_choice} {choices[p2_choice]}\n\n**{result}**", color=color))

async def setup(bot):
    await bot.add_cog(Fun(bot))
