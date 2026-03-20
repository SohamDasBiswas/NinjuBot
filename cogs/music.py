import discord
from discord.ext import commands
import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import aiohttp
import os
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import functools
import time

# ─── THREAD POOL (parallel yt-dlp extractions) ───────────────────────────────
_executor = ThreadPoolExecutor(max_workers=4)

# ─── SONG INFO CACHE (avoid re-fetching same songs) ──────────────────────────
_cache: dict = {}
CACHE_TTL = 3600  # 1 hour

def cache_get(key):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None

def cache_set(key, value):
    _cache[key] = (value, time.time())

# ─── YT-DLP OPTIONS (tuned for speed) ────────────────────────────────────────
YTDL_OPTIONS = {
    "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "socket_timeout": 10,
    "retries": 3,
    "fragment_retries": 3,
    "skip_download": True,
    "extract_flat": False,
    "geo_bypass": True,
    "nocheckcertificate": True,
}
if os.path.exists("cookies.txt"):
    YTDL_OPTIONS["cookiefile"] = "cookies.txt"

# ─── FFMPEG OPTIONS (low-latency, fast start) ─────────────────────────────────
FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
        "-probesize 32 "
        "-analyzeduration 0"
    ),
    "options": "-vn -bufsize 512k",
}

# ─── SINGLE YT-DLP INSTANCE (reused) ─────────────────────────────────────────
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# ─── SPOTIFY CLIENT ───────────────────────────────────────────────────────────
_sp = None
def get_spotify():
    global _sp
    if _sp:
        return _sp
    cid = os.getenv("SPOTIFY_CLIENT_ID")
    cs  = os.getenv("SPOTIFY_CLIENT_SECRET")
    if cid and cs:
        _sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=cs))
    return _sp

# ─── JIOSAAVN (async) ────────────────────────────────────────────────────────
async def search_jiosaavn(session, query):
    try:
        async with session.get(
            "https://saavn.dev/api/search/songs",
            params={"query": query, "limit": 1},
            timeout=aiohttp.ClientTimeout(total=4)
        ) as r:
            data = await r.json()
            results = data.get("data", {}).get("results", [])
            if results:
                song = results[0]
                artists = " ".join(a["name"] for a in song.get("artists", {}).get("primary", [])[:2])
                return f"{song.get('name', '')} {artists}"
    except Exception as e:
        print(f"[JioSaavn] {e}")
    return None

# ─── FAST YTDL EXTRACT ───────────────────────────────────────────────────────
def _ytdl_extract(query):
    url = query if query.startswith("http") else f"ytsearch1:{query}"
    data = ytdl.extract_info(url, download=False)
    if "entries" in data:
        data = data["entries"][0]
    return {
        "type": "single",
        "url": data["url"],
        "title": data.get("title", "Unknown"),
        "duration": data.get("duration", 0),
        "webpage_url": data.get("webpage_url", ""),
        "thumbnail": data.get("thumbnail", ""),
    }

async def resolve_source(query, loop, session):
    cache_key = query.strip().lower()
    cached = cache_get(cache_key)
    if cached:
        return cached

    sp = get_spotify()

    if "spotify.com/track" in query and sp:
        track = sp.track(query)
        query = f"{track['name']} {track['artists'][0]['name']}"

    elif "spotify.com/playlist" in query and sp:
        results = sp.playlist_tracks(query, limit=50)
        tracks = [
            f"{i['track']['name']} {i['track']['artists'][0]['name']}"
            for i in results["items"] if i.get("track")
        ]
        return {"type": "playlist", "tracks": tracks}

    elif "jiosaavn.com" in query or query.startswith("jio:"):
        q = query.replace("jio:", "").replace("jiosaavn.com", "").strip()
        result = await search_jiosaavn(session, q)
        if result:
            query = result

    result = await loop.run_in_executor(_executor, functools.partial(_ytdl_extract, query))
    cache_set(cache_key, result)
    return result

async def prefetch_song(query, loop, session):
    try:
        await resolve_source(query, loop, session)
    except:
        pass

# ─── PER-GUILD QUEUE ─────────────────────────────────────────────────────────
class GuildQueue:
    def __init__(self):
        self.queue = deque()
        self.current = None
        self.loop_mode = "none"
        self.volume = 0.5

    def add(self, song): self.queue.append(song)
    def next(self): return self.queue.popleft() if self.queue else None
    def clear(self): self.queue.clear(); self.current = None
    def peek(self): return self.queue[0] if self.queue else None

_queues = {}
def get_queue(gid):
    if gid not in _queues:
        _queues[gid] = GuildQueue()
    return _queues[gid]

def mk_embed(title, desc, color=0x1DB954, thumb=None):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="🎵 NinjaBot | Made by sdb_darkninja")
    if thumb:
        e.set_thumbnail(url=thumb)
    return e

# ─── MUSIC COG ────────────────────────────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._session = None

    async def cog_load(self):
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        self._session = aiohttp.ClientSession(connector=connector)

    async def cog_unload(self):
        if self._session:
            await self._session.close()

    @property
    def session(self):
        if not self._session or self._session.closed:
            connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def play_next(self, ctx):
        q = get_queue(ctx.guild.id)
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return

        if q.loop_mode == "song" and q.current:
            song = q.current
        else:
            if q.loop_mode == "queue" and q.current:
                q.add(q.current)
            song = q.next()

        if not song:
            await ctx.send(embed=mk_embed("✅ Queue Ended", "No more songs!"))
            return

        q.current = song

        # Prefetch next song in background
        if q.peek() and q.peek().get("webpage_url"):
            asyncio.create_task(prefetch_song(q.peek()["webpage_url"], self.bot.loop, self.session))

        try:
            source = discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=q.volume)

            def after_play(err):
                if err:
                    print(f"[Player] {err}")
                asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)

            vc.play(source, after=after_play)
            mins, secs = divmod(song["duration"], 60)
            await ctx.send(embed=mk_embed(
                "🎵 Now Playing",
                f"**[{song['title']}]({song['webpage_url']})**\n⏱ `{mins}:{secs:02d}` | 🔊 {int(q.volume*100)}% | 🔁 {q.loop_mode}",
                thumb=song.get("thumbnail")
            ))
        except Exception as e:
            await ctx.send(embed=mk_embed("❌ Error", str(e), color=0xFF0000))
            await self.play_next(ctx)

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("❌ Join a voice channel first!")
            return False
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect(timeout=8.0, reconnect=True, self_deaf=True)
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        return True

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, query: str):
        """Play from YouTube, Spotify, JioSaavn, SoundCloud."""
        if not await self.ensure_voice(ctx):
            return
        q = get_queue(ctx.guild.id)
        msg = await ctx.send(embed=mk_embed("🔍 Searching...", f"`{query}`", color=0xFFAA00))
        try:
            result = await asyncio.wait_for(
                resolve_source(query, self.bot.loop, self.session), timeout=15.0
            )
        except asyncio.TimeoutError:
            return await msg.edit(embed=mk_embed("❌ Timeout", "Search timed out. Try again.", color=0xFF0000))
        except Exception as e:
            return await msg.edit(embed=mk_embed("❌ Error", str(e), color=0xFF0000))

        if result["type"] == "playlist":
            await msg.edit(embed=mk_embed("📋 Loading Playlist", f"Fetching songs..."))
            first_batch = result["tracks"][:3]
            rest = result["tracks"][3:]
            tasks = [resolve_source(t, self.bot.loop, self.session) for t in first_batch]
            songs = await asyncio.gather(*tasks, return_exceptions=True)
            added = 0
            for s in songs:
                if isinstance(s, dict) and s.get("type") == "single":
                    q.add(s); added += 1
            for t in rest:
                q.add({"type": "lazy", "query": t, "title": t, "duration": 0,
                       "url": "", "webpage_url": "", "thumbnail": ""})
                added += 1
            await msg.edit(embed=mk_embed("📋 Playlist Added", f"Queued **{added}** songs."))
            if not ctx.voice_client.is_playing():
                await self.play_next(ctx)
            return

        q.add(result)
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            mins, secs = divmod(result["duration"], 60)
            await msg.edit(embed=mk_embed(
                "➕ Added to Queue",
                f"**[{result['title']}]({result['webpage_url']})**\n⏱ `{mins}:{secs:02d}` | Position `#{len(q.queue)}`",
                thumb=result.get("thumbnail")
            ))
        else:
            await msg.delete()
            await self.play_next(ctx)

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx):
        vc = ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.send(embed=mk_embed("⏭ Skipped", "Playing next..."))
        else:
            await ctx.send("❌ Nothing is playing!")

    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send(embed=mk_embed("⏸ Paused", "Use `!resume` to continue."))

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send(embed=mk_embed("▶️ Resumed", "Music is back!"))

    @commands.command(name="stop")
    async def stop(self, ctx):
        get_queue(ctx.guild.id).clear()
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send(embed=mk_embed("⏹ Stopped", "Queue cleared."))

    @commands.command(name="queue", aliases=["q"])
    async def queue_list(self, ctx):
        q = get_queue(ctx.guild.id)
        if not q.current and not q.queue:
            return await ctx.send(embed=mk_embed("📋 Queue", "Empty! Use `!play`."))
        desc = ""
        if q.current:
            desc += f"**▶️ Now Playing:**\n🎵 {q.current['title']}\n\n"
        if q.queue:
            desc += "**Up Next:**\n"
            for i, s in enumerate(list(q.queue)[:10], 1):
                desc += f"`{i}.` {s['title']}\n"
            if len(q.queue) > 10:
                desc += f"\n*...and {len(q.queue)-10} more*"
        await ctx.send(embed=mk_embed("📋 Queue", desc))

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        q = get_queue(ctx.guild.id)
        if not q.current:
            return await ctx.send("❌ Nothing is playing!")
        s = q.current
        mins, secs = divmod(s["duration"], 60)
        await ctx.send(embed=mk_embed(
            "🎵 Now Playing",
            f"**[{s['title']}]({s['webpage_url']})**\n⏱ `{mins}:{secs:02d}`",
            thumb=s.get("thumbnail")
        ))

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, vol: int):
        if not 1 <= vol <= 100:
            return await ctx.send("❌ Volume must be 1–100.")
        q = get_queue(ctx.guild.id)
        q.volume = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = q.volume
        await ctx.send(embed=mk_embed("🔊 Volume", f"Set to **{vol}%**"))

    @commands.command(name="loop")
    async def loop(self, ctx, mode: str = "song"):
        mode = mode.lower()
        if mode not in ("song", "queue", "none"):
            return await ctx.send("❌ Use `song`, `queue`, or `none`.")
        get_queue(ctx.guild.id).loop_mode = mode
        icons = {"song": "🔂", "queue": "🔁", "none": "➡️"}
        await ctx.send(embed=mk_embed(f"{icons[mode]} Loop", f"Mode → **{mode}**"))

    @commands.command(name="join", aliases=["connect"])
    async def join(self, ctx):
        if await self.ensure_voice(ctx):
            await ctx.send(embed=mk_embed("✅ Joined", f"Connected to **{ctx.author.voice.channel.name}**"))

    @commands.command(name="leave", aliases=["dc", "disconnect"])
    async def leave(self, ctx):
        if ctx.voice_client:
            get_queue(ctx.guild.id).clear()
            await ctx.voice_client.disconnect()
            await ctx.send(embed=mk_embed("👋 Left", "Disconnected."))

    @commands.command(name="search")
    async def search(self, ctx, *, query: str):
        """Search YouTube and pick from top 5 results."""
        msg = await ctx.send(embed=mk_embed("🔍 Searching...", f"`{query}`", color=0xFFAA00))
        try:
            data = await self.bot.loop.run_in_executor(
                _executor, lambda: ytdl.extract_info(f"ytsearch5:{query}", download=False)
            )
            results = data.get("entries", [])[:5]
        except Exception as e:
            return await msg.edit(embed=mk_embed("❌ Error", str(e), color=0xFF0000))

        desc = ""
        for i, r in enumerate(results, 1):
            mins, secs = divmod(r.get("duration", 0), 60)
            desc += f"`{i}.` [{r['title']}]({r['webpage_url']}) — `{mins}:{secs:02d}`\n"
        desc += "\nReply with a number `1–5` to play."
        await msg.edit(embed=mk_embed("🔍 Results", desc))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=20)
            idx = int(reply.content) - 1
            if 0 <= idx < len(results):
                await self.play(ctx, query=results[idx]["webpage_url"])
        except asyncio.TimeoutError:
            await ctx.send("⏱ Search timed out.")


    # ── /play slash command with live autocomplete ────────────────────────────
    @discord.app_commands.command(name="play", description="Search and play a song with live suggestions")
    @discord.app_commands.describe(query="Type a song name to see live suggestions")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)

        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect(timeout=8.0, reconnect=True, self_deaf=True)
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        await interaction.response.send_message(embed=mk_embed("🔍 Loading...", f"`{query}`", color=0xFFAA00))
        q = get_queue(interaction.guild.id)

        try:
            result = await asyncio.wait_for(
                resolve_source(query, self.bot.loop, self.session), timeout=15.0
            )
        except Exception as e:
            return await interaction.edit_original_response(embed=mk_embed("❌ Error", str(e), color=0xFF0000))

        q.add(result)

        class FakeCtx:
            def __init__(self, guild, voice_client, channel, bot):
                self.guild = guild
                self.voice_client = voice_client
                self.channel = channel
                self.bot = bot
            async def send(self, **kwargs):
                await interaction.channel.send(**kwargs)

        fake_ctx = FakeCtx(interaction.guild, vc, interaction.channel, self.bot)

        if vc.is_playing() or vc.is_paused():
            mins, secs = divmod(result["duration"], 60)
            await interaction.edit_original_response(embed=mk_embed(
                "➕ Added to Queue",
                f"**[{result['title']}]({result['webpage_url']})**\n⏱ `{mins}:{secs:02d}`",
                thumb=result.get("thumbnail")
            ))
        else:
            await interaction.edit_original_response(embed=mk_embed("✅ Found", f"**{result['title']}**\nStarting...", color=0x1DB954))
            await self.play_next(fake_ctx)


    @slash_play.autocomplete("query")
    async def play_autocomplete(self, interaction: discord.Interaction, current: str):
        if len(current) < 1:
            return []
        import json

        # Try YouTube suggest API first (fastest, <100ms)
        try:
            async with self.session.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "ds": "yt", "q": current},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                data = await resp.json(content_type=None)
                suggestions = data[1][:8]
                if suggestions:
                    return [
                        discord.app_commands.Choice(name=s[:100], value=s[:100])
                        for s in suggestions if isinstance(s, str)
                    ]
        except Exception as e:
            print(f"[Autocomplete] Google suggest failed: {e}")

        # Fallback: return current query as only option
        return [discord.app_commands.Choice(name=current[:100], value=current[:100])]

async def setup(bot):
    await bot.add_cog(Music(bot))
