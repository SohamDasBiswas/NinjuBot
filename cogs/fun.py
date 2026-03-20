import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import os

# ── Truth or Dare Data ────────────────────────────────────────────────────────

# Fallback lists (used if AI fails)
TRUTHS_FALLBACK = [
    "What's the most embarrassing thing you've ever done?",
    "Have you ever lied to get out of trouble? What was it?",
    "What's your biggest fear?",
    "Who was your first crush?",
    "What's the most childish thing you still do?",
    "Have you ever cheated on a test or game?",
    "What's the worst gift you've ever received?",
    "Have you ever blamed someone else for something you did?",
    "What's a secret talent you have?",
    "What's the most trouble you've ever been in?",
    "Have you ever stalked someone's social media for hours?",
    "What's the weirdest dream you've ever had?",
    "What's one thing you would change about yourself?",
    "Have you ever said 'I love you' and not meant it?",
    "What's your most embarrassing nickname?",
    "Have you ever sent a text to the wrong person?",
    "What's the biggest lie you've ever told?",
    "What's something you've never told anyone?",
    "Have you ever pretended to be sick to skip something?",
    "What's a bad habit you have that no one knows about?",
    "Have you ever laughed at the wrong moment?",
    "What's the most awkward situation you've been in?",
    "What's one thing on your phone you wouldn't want others to see?",
    "Have you ever fallen asleep in class or a meeting?",
    "Kya tumne kabhi kisi ko ghante bhar stalk kiya social media pe?",
]

DARES_FALLBACK = [
    "Do your best impression of another member in this server!",
    "Send the last meme you saved to this chat.",
    "Type the next message with your elbows only.",
    "Speak in an accent for the next 3 messages.",
    "Change your nickname to something embarrassing for 10 minutes.",
    "Send a voice message saying 'I am a potato' three times.",
    "Post a selfie with a silly face.",
    "Write a love poem for the person to your left (in the member list).",
    "Say the alphabet backwards.",
    "Act like a chicken for the next 2 minutes.",
    "Describe the last person you texted using only emojis.",
    "Do 10 push-ups right now and report back.",
    "Send a compliment to every person currently online.",
    "Change your profile picture to something funny for 1 hour.",
    "Type only in CAPS for the next 5 messages.",
    "Speak only in questions for the next 10 minutes.",
    "Send a screenshot of your home screen.",
    "Let someone else send one message from your account.",
    "Tell a joke — if nobody laughs, do another dare.",
    "Do your best robot dance and describe it in chat.",
    "Send the most recent photo in your camera roll.",
    "Write a haiku about the server.",
    "Convince someone you're an AI for 2 messages.",
    "Sing a song and post a voice clip of it.",
    "Text your mom/dad 'I love you' and show proof.",
]

# ── AI Generator ─────────────────────────────────────────────────────────────

async def generate_tod_ai(mode: str) -> str:
    """Generate a funny Hindi Truth or Dare using free AI (OpenRouter)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    prompt = (
        f"Generate ONE funny and hilarious {mode} for a Truth or Dare game. "
        f"Write ONLY in Hinglish (Hindi words written in English letters, like: Kya tune kabhi...). "
        f"Make it funny, embarrassing, and suitable for friends. "
        f"Do NOT use Hindi script. Just one sentence. No quotes, no numbering, no explanation."
    )

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek/deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.9,
                },
                timeout=aiohttp.ClientTimeout(total=8)
            )
            data = await resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            # Clean up any quotes or numbering
            text = text.strip('"\' ').lstrip('0123456789.-)')
            return text if len(text) > 10 else None
    except Exception as e:
        print(f"[ToD AI] {e}")
        return None

class TruthOrDareView(discord.ui.View):
    def __init__(self, ctx, target: discord.Member):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.target = target

    @discord.ui.button(label="Truth", emoji="🤔", style=discord.ButtonStyle.primary)
    async def truth(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target and interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        question = random.choice(TRUTHS)
        embed = discord.Embed(
            title="🤔 TRUTH",
            description=f"{self.target.mention} must answer honestly!\n\n**{question}**",
            color=0x3498DB
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.set_footer(text="🎭 NinjuBot Truth or Dare | Made by sdb_darkninja")
        for item in self.children:
            item.disabled = True
        view = TruthOrDareAgainView(self.ctx, self.target)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Dare", emoji="🔥", style=discord.ButtonStyle.danger)
    async def dare(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target and interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        dare = random.choice(DARES)
        embed = discord.Embed(
            title="🔥 DARE",
            description=f"{self.target.mention} must complete this dare!\n\n**{dare}**",
            color=0xFF4500
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.set_footer(text="🎭 NinjuBot Truth or Dare | Made by sdb_darkninja")
        view = TruthOrDareAgainView(self.ctx, self.target)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Random", emoji="🎲", style=discord.ButtonStyle.secondary)
    async def random_choice(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target and interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        if random.random() > 0.5:
            question = random.choice(TRUTHS)
            embed = discord.Embed(
                title="🎲 RANDOM → TRUTH",
                description=f"{self.target.mention} got Truth!\n\n**{question}**",
                color=0x3498DB
            )
        else:
            dare = random.choice(DARES)
            embed = discord.Embed(
                title="🎲 RANDOM → DARE",
                description=f"{self.target.mention} got Dare!\n\n**{dare}**",
                color=0xFF4500
            )
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.set_footer(text="🎭 NinjuBot Truth or Dare | Made by sdb_darkninja")
        view = TruthOrDareAgainView(self.ctx, self.target)
        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class TruthOrDareAgainView(discord.ui.View):
    def __init__(self, ctx, target: discord.Member):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.target = target

    @discord.ui.button(label="Play Again", emoji="🔄", style=discord.ButtonStyle.success)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎭 Truth or Dare",
            description=f"{self.target.mention} — choose your fate!",
            color=0xFF6B9D
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.set_footer(text="🎮 NinjuBot | Made by sdb_darkninja")
        view = TruthOrDareView(self.ctx, self.target)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Change Player", emoji="👤", style=discord.ButtonStyle.secondary)
    async def change_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Use `-tod @user` to challenge someone specific, or `-tod` to play yourself!",
            ephemeral=True
        )

    @discord.ui.button(label="End Game", emoji="🛑", style=discord.ButtonStyle.danger)
    async def end_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎭 Game Over!",
            description="Thanks for playing Truth or Dare! Use `-tod` to start again.",
            color=0x808080
        )
        embed.set_footer(text="🎮 NinjuBot | Made by sdb_darkninja")
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


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


    # ── Truth or Dare ─────────────────────────────────────────────────────────
    @commands.command(name="truthordare", aliases=["tod", "td"])
    async def truth_or_dare(self, ctx, member: discord.Member = None):
        """Start a Truth or Dare game! Optionally challenge a specific user."""
        target = member or ctx.author
        embed = discord.Embed(
            title="🎭 Truth or Dare",
            description=f"{target.mention} — choose your fate!",
            color=0xFF6B9D
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="🎮 NinjuBot | Made by sdb_darkninja")
        view = TruthOrDareView(ctx, target)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Fun(bot))
