import discord
from discord.ext import commands
import aiohttp
import os
import random
import asyncio

chat_sessions = {}

def mk_embed(title, desc, color=0x9B59B6, thumb=None):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="🤖 NinjaBot AI | Made by sdb_darkninja")
    if thumb:
        e.set_thumbnail(url=thumb)
    return e

async def ask_ai(prompt: str, system: str = "") -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return "❌ `OPENROUTER_API_KEY` not set in `.env`. Free key lo: openrouter.ai"

    # Fast + confirmed free models (DeepSeek V3 & R1 are free on OpenRouter)
    models = [
        "deepseek/deepseek-chat",     # ✅ FAST + FREE (best)
        "mistralai/mistral-7b-instruct",  # ✅ fallback
        "meta-llama/llama-3-8b-instruct", # ✅ fallback
    ]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with aiohttp.ClientSession() as s:
        for model in models:
            try:
                resp = await s.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "HTTP-Referer": "https://github.com/ninjabot",
                        "X-Title": "NinjaBot Discord",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 300,
                        "temperature": 0.9,
                    },
                    timeout=aiohttp.ClientTimeout(total=20)
                )
                data = await resp.json()
                print(f"[AI/{model}] Status: {resp.status}")

                if "error" in data:
                    print(f"[AI] Error on {model}: {data['error'].get('message')}")
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue

                content = choices[0].get("message", {}).get("content")

                if isinstance(content, str) and content.strip():
                    text = content.strip()
                    print(f"[AI] Success with model: {model}")
                    return text
                if text:
                    print(f"[AI] Success with model: {model}")
                    return text

            except asyncio.TimeoutError:
                print(f"[AI/{model}] Timeout, trying next...")
                continue
            except Exception as e:
                print(f"[AI/{model}] Exception: {e}")
                continue

    return "❌ Abhi AI busy hai. 1-2 minute baad try karo!"


async def get_gif(query: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as s:
            resp = await s.get(
                "https://tenor.googleapis.com/v2/search",
                params={"q": query, "key": "AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCYQ", "limit": 10, "contentfilter": "medium"},
                timeout=aiohttp.ClientTimeout(total=10)
            )
            data = await resp.json()
            results = data.get("results", [])
            if results:
                return random.choice(results[:8])["media_formats"]["gif"]["url"]
    except:
        pass
    return None


class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── -ask ──────────────────────────────────────────────────────────────────
    @commands.command(name="ask")
    async def ask(self, ctx, *, question: str):
        msg = await ctx.send(embed=mk_embed("🤔 Soch raha hoon...", f"`{question}`", color=0xFFAA00))
        answer = await ask_ai(
            question,
            system="Always respond in Hinglish - Hindi words written in Roman English letters (not Devanagari). Be casual, fun and helpful. Example style: 'Tera sawaal bahut accha hai yaar!'"
        )
        await msg.edit(embed=mk_embed("🤖 Jawab", f"**Q:** {question}\n\n**A:** {answer[:3000]}"))

    # ── -roast @user ──────────────────────────────────────────────────────────
    @commands.command(name="roast")
    async def roast(self, ctx, member: discord.Member):
        msg = await ctx.send(embed=mk_embed("🔥 Roast ban raha hai...", f"{member.mention} ko roast kar raha hoon...", color=0xFF4500))
        roast_text, gif_url = await asyncio.gather(
            ask_ai(
                f"Roast the Discord user named '{member.display_name}'. Address them directly as 'tu' and use their name. Make it personal, funny and creative based on their name. Under 150 words. End with a savage one-liner.",
                system="You are a comedy roast master. Write in Hinglish - Hindi words in Roman English letters only (not Devanagari). Example: 'Tera kya hoga re bhai'. Be playful not mean. Address person directly by name."
            ),
            get_gif("roast burn savage funny reaction")
        )
        embed = discord.Embed(title=f"🔥 {member.display_name} ka Roast!", description=f"{member.mention}\n\n{roast_text}", color=0xFF4500)
        embed.set_thumbnail(url=member.display_avatar.url)
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="🤖 NinjaBot AI | Made by sdb_darkninja")
        await msg.edit(embed=embed)

    # ── -compliment @user ─────────────────────────────────────────────────────
    @commands.command(name="compliment")
    async def compliment(self, ctx, member: discord.Member):
        msg = await ctx.send(embed=mk_embed("💜 Compliment ban raha hai...", f"{member.mention} ke liye...", color=0x9B59B6))
        comp_text, gif_url = await asyncio.gather(
            ask_ai(
                f"Give a heartfelt compliment to Discord user '{member.display_name}'. Address them directly as 'tu' and use their name. Make it personal, warm and creative. Under 100 words. End with an encouraging line.",
                system="You are a kind compliment generator. Write in Hinglish - Hindi words in Roman English letters only (not Devanagari). Example: 'Tu bahut amazing hai yaar'. Be warm and genuine. Address person directly by name."
            ),
            get_gif("wholesome sweet cute happy reaction")
        )
        embed = discord.Embed(title=f"💜 {member.display_name} ke liye!", description=f"{member.mention}\n\n{comp_text}", color=0x9B59B6)
        embed.set_thumbnail(url=member.display_avatar.url)
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="🤖 NinjaBot AI | Made by sdb_darkninja")
        await msg.edit(embed=embed)

    # ── -chat ─────────────────────────────────────────────────────────────────
    @commands.command(name="chat")
    @commands.has_permissions(manage_channels=True)
    async def chat(self, ctx):
        key = f"{ctx.guild.id}_{ctx.channel.id}"
        if key in chat_sessions:
            del chat_sessions[key]
            await ctx.send(embed=mk_embed("🤖 AI Chat", "AI chat mode **band** kar diya is channel mein."))
        else:
            chat_sessions[key] = []
            await ctx.send(embed=mk_embed("🤖 AI Chat", "AI chat mode **chalu** ho gaya! Har message ka jawab dunga.\nBand karne ke liye `-chat` dubara use karo."))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith("-"):
            return
        key = f"{message.guild.id}_{message.channel.id}" if message.guild else None
        if not key or key not in chat_sessions:
            return
        if not os.getenv("OPENROUTER_API_KEY"):
            return

        history = chat_sessions.get(key, [])
        history.append(message.content)

        async with message.channel.typing():
            context = "\n".join(history[-6:])
            reply = await ask_ai(
                context,
                system="You are NinjaBot, a friendly Discord bot made by sdb_darkninja. Always respond in Hinglish - Hindi words in Roman English letters only. Keep responses short and conversational."
            )

        history.append(reply)
        chat_sessions[key] = history[-20:]
        await message.reply(reply[:2000])


async def setup(bot):
    await bot.add_cog(AI(bot))
