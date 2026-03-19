import discord
from discord.ext import commands
import asyncio
import aiohttp
import random
import json
import os
from concurrent.futures import ThreadPoolExecutor
import yt_dlp

_executor = ThreadPoolExecutor(max_workers=2)

PLAYLISTS_FILE = "playlists.json"

def load_playlists():
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_playlists(data):
    with open(PLAYLISTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

RADIO_STATIONS = {
    "pop":       "https://stream.zeno.fm/4d61qr5wx8zuv",
    "hiphop":    "https://stream.zeno.fm/f3wvbbqmdg8uv",
    "rock":      "https://stream.zeno.fm/v9gdd4s8g9zuv",
    "lofi":      "https://stream.zeno.fm/0r0xa792kwzuv",
    "jazz":      "https://stream.zeno.fm/4wxdb67t7g8uv",
    "classical": "https://stream.zeno.fm/3qp3yw8g5g8uv",
    "bollywood": "https://stream.zeno.fm/4ywcq3x2uw8uv",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 32 -analyzeduration 0",
    "options": "-vn -bufsize 512k",
}

EFFECTS = {
    "bassboost":  "-af equalizer=f=40:width_type=o:width=2:g=5,equalizer=f=80:width_type=o:width=2:g=4",
    "nightcore":  "-af asetrate=44100*1.25,aresample=44100",
    "vaporwave":  "-af asetrate=44100*0.8,aresample=44100",
    "normal":     "-vn",
}

def mk_embed(title, desc, color=0x1DB954, thumb=None):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="🎵 NinjaBot | Made by sdb_darkninja")
    if thumb:
        e.set_thumbnail(url=thumb)
    return e

class MusicExtras(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playlists = load_playlists()
        self.current_effect = {}  # guild_id -> effect name
        self.trivia_active = {}   # guild_id -> bool

    def get_queue(self, guild_id):
        from cogs.music import get_queue
        return get_queue(guild_id)

    # ── -shuffle ──────────────────────────────────────────────────────────────
    @commands.command(name="shuffle")
    async def shuffle(self, ctx):
        """Shuffle the queue."""
        q = self.get_queue(ctx.guild.id)
        if len(q.queue) < 2:
            return await ctx.send("❌ Need at least 2 songs in queue to shuffle!")
        lst = list(q.queue)
        random.shuffle(lst)
        q.queue.clear()
        q.queue.extend(lst)
        await ctx.send(embed=mk_embed("🔀 Shuffled", f"Shuffled **{len(lst)}** songs in queue!"))

    # ── -remove <number> ──────────────────────────────────────────────────────
    @commands.command(name="remove")
    async def remove(self, ctx, index: int):
        """Remove a song from the queue by its number."""
        q = self.get_queue(ctx.guild.id)
        if not q.queue:
            return await ctx.send("❌ Queue is empty!")
        if not 1 <= index <= len(q.queue):
            return await ctx.send(f"❌ Invalid number. Queue has `{len(q.queue)}` songs.")
        lst = list(q.queue)
        removed = lst.pop(index - 1)
        q.queue.clear()
        q.queue.extend(lst)
        await ctx.send(embed=mk_embed("🗑️ Removed", f"Removed **{removed['title']}** from queue."))

    # ── -247 ─────────────────────────────────────────────────────────────────
    @commands.command(name="247", aliases=["24/7"])
    async def stay247(self, ctx):
        """Toggle 24/7 mode - bot stays in voice channel."""
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first!")
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect(timeout=8.0, reconnect=True, self_deaf=True)
            await ctx.send(embed=mk_embed("🔁 24/7 Mode", "Bot will stay in voice channel 24/7!"))
        else:
            await ctx.send(embed=mk_embed("🔁 24/7 Mode", "Already in voice channel! Use `-leave` to disconnect."))

    # ── -lyrics <song> ────────────────────────────────────────────────────────
    @commands.command(name="lyrics")
    async def lyrics(self, ctx, *, song: str = None):
        """Get lyrics for a song."""
        q = self.get_queue(ctx.guild.id)
        if not song:
            if q.current:
                song = q.current["title"]
            else:
                return await ctx.send("❌ Provide a song name or play something first.")

        msg = await ctx.send(embed=mk_embed("🔍 Searching lyrics...", f"`{song}`", color=0xFFAA00))
        try:
            async with aiohttp.ClientSession() as s:
                resp = await s.get(
                    f"https://api.lyrics.ovh/v1/{song.replace(' ', '/')[:100]}",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                if resp.status == 200:
                    data = await resp.json()
                    lyrics = data.get("lyrics", "")
                    if lyrics:
                        # Split if too long
                        chunks = [lyrics[i:i+1900] for i in range(0, min(len(lyrics), 5700), 1900)]
                        await msg.edit(embed=mk_embed(f"🎵 Lyrics — {song}", chunks[0][:4096]))
                        for chunk in chunks[1:]:
                            await ctx.send(embed=mk_embed("🎵 (continued)", chunk[:4096]))
                        return
        except:
            pass
        await msg.edit(embed=mk_embed("❌ No Lyrics Found", f"Could not find lyrics for `{song}`.", color=0xFF0000))

    # ── -playlist save/play/list/delete ───────────────────────────────────────
    @commands.group(name="playlist", aliases=["pl"])
    async def playlist(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=mk_embed("📋 Playlist Commands", (
                "`-playlist save <name>` — Save current queue\n"
                "`-playlist play <name>` — Load a playlist\n"
                "`-playlist list` — Show all playlists\n"
                "`-playlist delete <name>` — Delete a playlist"
            )))

    @playlist.command(name="save")
    async def playlist_save(self, ctx, *, name: str):
        q = self.get_queue(ctx.guild.id)
        songs = []
        if q.current:
            songs.append({"title": q.current["title"], "url": q.current["webpage_url"]})
        for s in q.queue:
            songs.append({"title": s["title"], "url": s.get("webpage_url", "")})
        if not songs:
            return await ctx.send("❌ Nothing in queue to save!")
        key = f"{ctx.guild.id}_{name}"
        self.playlists[key] = {"name": name, "songs": songs, "owner": str(ctx.author)}
        save_playlists(self.playlists)
        await ctx.send(embed=mk_embed("✅ Playlist Saved", f"Saved **{len(songs)}** songs as `{name}`"))

    @playlist.command(name="play")
    async def playlist_play(self, ctx, *, name: str):
        key = f"{ctx.guild.id}_{name}"
        if key not in self.playlists:
            return await ctx.send(f"❌ Playlist `{name}` not found. Use `-playlist list` to see all.")
        pl = self.playlists[key]
        await ctx.send(embed=mk_embed("📋 Loading Playlist", f"Loading **{len(pl['songs'])}** songs from `{name}`..."))
        await ctx.invoke(self.bot.get_command("play"), query=pl["songs"][0]["url"])
        q = self.get_queue(ctx.guild.id)
        for song in pl["songs"][1:]:
            q.add({"title": song["title"], "url": "", "webpage_url": song["url"],
                   "duration": 0, "thumbnail": "", "type": "single"})
        await ctx.send(embed=mk_embed("✅ Playlist Loaded", f"Queued **{len(pl['songs'])}** songs from `{name}`"))

    @playlist.command(name="list")
    async def playlist_list(self, ctx):
        guild_playlists = {k: v for k, v in self.playlists.items() if k.startswith(str(ctx.guild.id))}
        if not guild_playlists:
            return await ctx.send("❌ No playlists saved for this server.")
        desc = "\n".join([f"`{v['name']}` — {len(v['songs'])} songs" for v in guild_playlists.values()])
        await ctx.send(embed=mk_embed("📋 Playlists", desc))

    @playlist.command(name="delete")
    async def playlist_delete(self, ctx, *, name: str):
        key = f"{ctx.guild.id}_{name}"
        if key not in self.playlists:
            return await ctx.send(f"❌ Playlist `{name}` not found.")
        del self.playlists[key]
        save_playlists(self.playlists)
        await ctx.send(embed=mk_embed("🗑️ Deleted", f"Playlist `{name}` deleted."))

    # ── -equalizer ────────────────────────────────────────────────────────────
    @commands.command(name="equalizer", aliases=["eq", "effect"])
    async def equalizer(self, ctx, effect: str = None):
        """Apply audio effects: bassboost, nightcore, vaporwave, normal"""
        if not effect or effect.lower() not in EFFECTS:
            opts = ", ".join(f"`{e}`" for e in EFFECTS)
            return await ctx.send(embed=mk_embed("🎚️ Equalizer", f"Available effects: {opts}\nUsage: `-eq bassboost`"))
        effect = effect.lower()
        self.current_effect[ctx.guild.id] = effect
        icons = {"bassboost": "🔊", "nightcore": "⚡", "vaporwave": "🌊", "normal": "🎵"}
        await ctx.send(embed=mk_embed(f"{icons[effect]} Effect: {effect.title()}", "Effect will apply on next song. Use `-skip` to restart current song with effect."))

    # ── -radio <genre> ────────────────────────────────────────────────────────
    @commands.command(name="radio")
    async def radio(self, ctx, genre: str = None):
        """Play non-stop internet radio. Genres: pop, hiphop, rock, lofi, jazz, classical, bollywood"""
        if not genre or genre.lower() not in RADIO_STATIONS:
            genres = ", ".join(f"`{g}`" for g in RADIO_STATIONS)
            return await ctx.send(embed=mk_embed("📻 Radio", f"Available genres:\n{genres}\n\nUsage: `-radio lofi`"))

        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first!")

        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect(timeout=8.0, reconnect=True, self_deaf=True)
        elif vc.channel != ctx.author.voice.channel:
            await vc.move_to(ctx.author.voice.channel)

        if vc.is_playing():
            vc.stop()

        url = RADIO_STATIONS[genre.lower()]
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=0.5)
        vc.play(source)

        await ctx.send(embed=mk_embed("📻 Radio", f"Now streaming **{genre.upper()}** radio!\nUse `-stop` to stop."))

    # ── -musictrivia ──────────────────────────────────────────────────────────
    @commands.command(name="musictrivia", aliases=["mt", "trivia"])
    async def musictrivia(self, ctx):
        """Guess the song! Bot plays a clip and you guess the title."""
        if self.trivia_active.get(ctx.guild.id):
            return await ctx.send("❌ A trivia is already running! Finish it first.")

        songs = [
            {"title": "Shape of You", "artist": "Ed Sheeran", "query": "shape of you ed sheeran"},
            {"title": "Blinding Lights", "artist": "The Weeknd", "query": "blinding lights weeknd"},
            {"title": "Dance Monkey", "artist": "Tones and I", "query": "dance monkey tones and i"},
            {"title": "Rockstar", "artist": "Post Malone", "query": "rockstar post malone"},
            {"title": "Despacito", "artist": "Luis Fonsi", "query": "despacito luis fonsi"},
            {"title": "Happier", "artist": "Marshmello", "query": "happier marshmello"},
            {"title": "Sunflower", "artist": "Post Malone", "query": "sunflower post malone"},
            {"title": "Levitating", "artist": "Dua Lipa", "query": "levitating dua lipa"},
        ]

        song = random.choice(songs)
        self.trivia_active[ctx.guild.id] = True

        await ctx.send(embed=mk_embed("🎵 Music Trivia!", (
            "A song will play for **15 seconds**.\n"
            "Type the **song title** in chat to win!\n"
            "Starting in 3 seconds..."
        ), color=0xFFAA00))

        await asyncio.sleep(3)

        if not ctx.author.voice:
            self.trivia_active[ctx.guild.id] = False
            return await ctx.send("❌ Join a voice channel to play!")

        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect(timeout=8.0, reconnect=True, self_deaf=True)

        # Fetch and play the song
        try:
            ytdl_opts = {"format": "bestaudio/best", "quiet": True, "noplaylist": True}
            ytdl = yt_dlp.YoutubeDL(ytdl_opts)
            data = await self.bot.loop.run_in_executor(
                _executor, lambda: ytdl.extract_info(f"ytsearch1:{song['query']}", download=False)
            )
            if "entries" in data:
                data = data["entries"][0]
            source = discord.FFmpegPCMAudio(data["url"], **FFMPEG_OPTIONS)
            vc.play(source)
        except Exception as e:
            self.trivia_active[ctx.guild.id] = False
            return await ctx.send(f"❌ Error loading song: {e}")

        await ctx.send(embed=mk_embed("🎵 Guess the Song!", "**15 seconds** to guess! Type the song title!", color=0x9B59B6))

        def check(m):
            return m.channel == ctx.channel and not m.author.bot

        winner = None
        end_time = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < end_time:
            try:
                remaining = end_time - asyncio.get_event_loop().time()
                msg = await self.bot.wait_for("message", check=check, timeout=remaining)
                if song["title"].lower() in msg.content.lower():
                    winner = msg.author
                    break
            except asyncio.TimeoutError:
                break

        if vc.is_playing():
            vc.stop()
        self.trivia_active[ctx.guild.id] = False

        if winner:
            await ctx.send(embed=mk_embed("🎉 Correct!", f"**{winner.mention}** guessed it!\nSong: **{song['title']}** by **{song['artist']}**", color=0x2ECC71))
        else:
            await ctx.send(embed=mk_embed("⏱️ Time's Up!", f"Nobody guessed it!\nSong was: **{song['title']}** by **{song['artist']}**", color=0xFF0000))

async def setup(bot):
    await bot.add_cog(MusicExtras(bot))
