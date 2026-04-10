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

_executor = ThreadPoolExecutor(max_workers=4)
_cache: dict = {}
CACHE_TTL = 3600

def cache_get(key):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None

def cache_set(key, value):
    _cache[key] = (value, time.time())

# ── yt-dlp: try multiple formats in order ──────────────────
def make_ytdl(cookiefile=None):
    import shutil
    opts = {
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "socket_timeout": 15,
        "retries": 5,
        "fragment_retries": 5,
        "skip_download": True,
        "noplaylist": False,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "extractor_retries": 3,
        "format": "bestaudio/best",
    }
    # Use Node.js runtime for yt-dlp (fixes YouTube JS extraction)
    node_path = shutil.which("node")
    if node_path:
        opts["js_runtimes"] = {"node": {"path": node_path}}
        opts["remote_components"] = {"ejs": {"url": "github"}}
    if cookiefile and os.path.exists(cookiefile):
        opts["cookiefile"] = cookiefile
    return yt_dlp.YoutubeDL(opts)

ytdl = make_ytdl("cookies.txt")

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 32 -analyzeduration 0",
    "options": "-vn -bufsize 512k",
}

_sp = None
def get_spotify():
    global _sp
    if _sp: return _sp
    cid = os.getenv("SPOTIFY_CLIENT_ID")
    cs  = os.getenv("SPOTIFY_CLIENT_SECRET")
    if cid and cs:
        _sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=cs))
    return _sp

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

def _ytdl_extract(query):
    url = query if query.startswith("http") else f"ytsearch1:{query}"
    try:
        data = ytdl.extract_info(url, download=False)
    except Exception as e:
        # If format fails, retry with most permissive options
        print(f"[yt-dlp] Retrying with fallback format: {e}")
        fallback = make_ytdl("cookies.txt")
        fallback.params["format"] = "best"
        data = fallback.extract_info(url, download=False)
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
    if cached: return cached
    sp = get_spotify()
    if "spotify.com/track" in query and sp:
        track = sp.track(query)
        query = f"{track['name']} {track['artists'][0]['name']}"
    elif "spotify.com/playlist" in query and sp:
        results = sp.playlist_tracks(query, limit=50)
        tracks = [f"{i['track']['name']} {i['track']['artists'][0]['name']}" for i in results["items"] if i.get("track")]
        return {"type": "playlist", "tracks": tracks}
    elif "jiosaavn.com" in query or query.startswith("jio:"):
        q = query.replace("jio:", "").replace("jiosaavn.com", "").strip()
        result = await search_jiosaavn(session, q)
        if result: query = result
    result = await loop.run_in_executor(_executor, functools.partial(_ytdl_extract, query))
    cache_set(cache_key, result)
    return result

async def prefetch_song(query, loop, session):
    try: await resolve_source(query, loop, session)
    except: pass

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
    if gid not in _queues: _queues[gid] = GuildQueue()
    return _queues[gid]

def fmt_dur(secs):
    mins, s = divmod(int(secs), 60)
    hrs, m = divmod(mins, 60)
    return f"{hrs}:{m:02d}:{s:02d}" if hrs else f"{m}:{s:02d}"

def mk_embed(title, desc, color=0x4ade80, thumb=None):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="🎵 NinjuBot | Made by sdb_darkninja")
    if thumb: e.set_thumbnail(url=thumb)
    return e

class PlayerView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("❌ Not in VC!", ephemeral=True)
        if vc.is_playing(): vc.pause(); button.emoji = "▶️"; button.style = discord.ButtonStyle.success
        elif vc.is_paused(): vc.resume(); button.emoji = "⏸️"; button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()): vc.stop(); await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)
        else: await interaction.response.send_message("❌ Nothing playing!", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        get_queue(interaction.guild.id).clear()
        vc = interaction.guild.voice_client
        if vc: vc.stop()
        await interaction.response.send_message("⏹️ Stopped.", ephemeral=True)

    @discord.ui.button(emoji="🔂", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(interaction.guild.id)
        modes = ["none", "song", "queue"]
        q.loop_mode = modes[(modes.index(q.loop_mode) + 1) % 3]
        icons = {"none": "➡️", "song": "🔂", "queue": "🔁"}
        button.emoji = icons[q.loop_mode]
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"{icons[q.loop_mode]} Loop: **{q.loop_mode}**", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def volume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VolumeModal())

    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        q = get_queue(interaction.guild.id)
        if not q.current and not q.queue:
            return await interaction.response.send_message("📋 Queue is empty!", ephemeral=True)
        desc = f"▶️ **{q.current['title']}** `{fmt_dur(q.current['duration'])}`\n\n" if q.current else ""
        for i, s in enumerate(list(q.queue)[:10], 1): desc += f"`{i}.` {s['title']} `{fmt_dur(s['duration'])}`\n"
        if len(q.queue) > 10: desc += f"\n*...and {len(q.queue)-10} more*"
        embed = discord.Embed(title="📋 Queue", description=desc, color=0x4ade80)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class VolumeModal(discord.ui.Modal, title="🔊 Set Volume"):
    volume = discord.ui.TextInput(label="Volume (1-100)", placeholder="50", min_length=1, max_length=3)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            vol = int(self.volume.value)
            if not 1 <= vol <= 100: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Enter 1-100!", ephemeral=True)
        q = get_queue(interaction.guild.id)
        q.volume = vol / 100
        vc = interaction.guild.voice_client
        if vc and vc.source: vc.source.volume = q.volume
        await interaction.response.send_message(f"🔊 Volume → **{vol}%**", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._session = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=20, ttl_dns_cache=300))

    async def cog_unload(self):
        if self._session: await self._session.close()

    @property
    def session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=20, ttl_dns_cache=300))
        return self._session

    async def play_next(self, ctx):
        q = get_queue(ctx.guild.id)
        vc = ctx.voice_client
        if not vc or not vc.is_connected(): return
        if q.loop_mode == "song" and q.current: song = q.current
        else:
            if q.loop_mode == "queue" and q.current: q.add(q.current)
            song = q.next()
        if not song:
            await ctx.send(embed=mk_embed("✅ Queue Finished", "Use `-play` to add more songs.")); return
        q.current = song
        if q.peek() and q.peek().get("webpage_url"):
            asyncio.create_task(prefetch_song(q.peek()["webpage_url"], self.bot.loop, self.session))
        try:
            source = discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=q.volume)
            def after_play(err):
                if err: print(f"[Player] {err}")
                asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
            vc.play(source, after=after_play)
            embed = discord.Embed(title="🎵 Now Playing", color=0x4ade80)
            embed.add_field(name="Track", value=f"**[{song['title']}]({song['webpage_url']})**", inline=False)
            embed.add_field(name="⏱ Duration", value=f"`{fmt_dur(song['duration'])}`", inline=True)
            embed.add_field(name="🔊 Volume", value=f"`{int(q.volume*100)}%`", inline=True)
            embed.add_field(name="🔁 Loop", value=f"`{q.loop_mode}`", inline=True)
            embed.add_field(name="📋 Queue", value=f"`{len(q.queue)} songs`", inline=True)
            if song.get("thumbnail"): embed.set_thumbnail(url=song["thumbnail"])
            embed.set_footer(text="🎵 NinjuBot | Made by sdb_darkninja")
            await ctx.send(embed=embed, view=PlayerView(ctx))
        except Exception as e:
            await ctx.send(embed=mk_embed("❌ Playback Error", str(e), color=0xFF0000))
            await self.play_next(ctx)

    async def _connect_with_retry(self, channel) -> discord.VoiceClient:
        """Connect to a voice channel, retrying once on 4006 stale-session."""
        # Tell Discord's gateway we're leaving any voice channel first,
        # clearing stale sessions that cause 4006 on reconnect
        try:
            await channel.guild.change_voice_state(channel=None)
            await asyncio.sleep(1.0)
        except Exception:
            pass

        last_err: Exception = RuntimeError("unknown")
        for attempt in range(3):
            try:
                return await channel.connect(timeout=12.0, reconnect=False, self_deaf=True)
            except discord.errors.ConnectionClosed as e:
                last_err = e
                if getattr(e, 'code', None) == 4006 and attempt < 2:
                    await asyncio.sleep(4 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_err = e
                break
        raise last_err

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send(embed=mk_embed("❌ No Voice Channel", "Join a voice channel first!", color=0xFF0000)); return False
        if not ctx.voice_client:
            try:
                await self._connect_with_retry(ctx.author.voice.channel)
            except Exception as e:
                await ctx.send(embed=mk_embed("❌ Connect Failed", f"Could not join voice channel: {e}", color=0xFF0000))
                return False
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        return True

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, query: str):
        if not await self.ensure_voice(ctx): return
        q = get_queue(ctx.guild.id)
        embed = discord.Embed(title="🔍 Searching...", description=f"```{query[:100]}```", color=0xf59e0b)
        embed.set_footer(text="🎵 NinjuBot | Made by sdb_darkninja")
        msg = await ctx.send(embed=embed)
        try:
            result = await asyncio.wait_for(resolve_source(query, self.bot.loop, self.session), timeout=20.0)
        except asyncio.TimeoutError:
            return await msg.edit(embed=mk_embed("❌ Timeout", "Search timed out. Try again.", color=0xFF0000))
        except Exception as e:
            return await msg.edit(embed=mk_embed("❌ Error", str(e)[:300], color=0xFF0000))

        if result["type"] == "playlist":
            await msg.edit(embed=mk_embed("📋 Loading Playlist", "Fetching songs..."))
            first = result["tracks"][:3]; rest = result["tracks"][3:]
            songs = await asyncio.gather(*[resolve_source(t, self.bot.loop, self.session) for t in first], return_exceptions=True)
            added = 0
            for s in songs:
                if isinstance(s, dict) and s.get("type") == "single": q.add(s); added += 1
            for t in rest: q.add({"type":"lazy","query":t,"title":t,"duration":0,"url":"","webpage_url":"","thumbnail":""}); added += 1
            await msg.edit(embed=mk_embed("📋 Playlist Added", f"Queued **{added} songs**!"))
            if not ctx.voice_client.is_playing(): await self.play_next(ctx)
            return

        q.add(result)
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            embed = discord.Embed(title="➕ Added to Queue", color=0x4ade80)
            embed.add_field(name="Track", value=f"**[{result['title']}]({result['webpage_url']})**", inline=False)
            embed.add_field(name="⏱ Duration", value=f"`{fmt_dur(result['duration'])}`", inline=True)
            embed.add_field(name="📋 Position", value=f"`#{len(q.queue)}`", inline=True)
            if result.get("thumbnail"): embed.set_thumbnail(url=result["thumbnail"])
            embed.set_footer(text="🎵 NinjuBot | Made by sdb_darkninja")
            await msg.edit(embed=embed)
        else:
            await msg.delete(); await self.play_next(ctx)

    @commands.command(name="skip", aliases=["s","next"])
    async def skip(self, ctx):
        vc = ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()): vc.stop(); await ctx.send(embed=mk_embed("⏭️ Skipped", "Playing next song..."))
        else: await ctx.send(embed=mk_embed("❌ Nothing Playing", "No audio is currently playing.", color=0xFF0000))

    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause(); await ctx.send(embed=mk_embed("⏸️ Paused", "Use `-resume` to continue."))

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume(); await ctx.send(embed=mk_embed("▶️ Resumed", "Music is back!"))

    @commands.command(name="stop")
    async def stop(self, ctx):
        get_queue(ctx.guild.id).clear()
        if ctx.voice_client: ctx.voice_client.stop()
        await ctx.send(embed=mk_embed("⏹️ Stopped", "Queue cleared."))

    @commands.command(name="queue", aliases=["q"])
    async def queue_list(self, ctx):
        q = get_queue(ctx.guild.id)
        if not q.current and not q.queue:
            return await ctx.send(embed=mk_embed("📋 Empty Queue", "Use `-play` to add songs."))
        embed = discord.Embed(title="📋 Music Queue", color=0x4ade80)
        if q.current:
            embed.add_field(name="▶️ Now Playing", value=f"[{q.current['title']}]({q.current['webpage_url']}) `{fmt_dur(q.current['duration'])}`", inline=False)
        if q.queue:
            up = "\n".join([f"`{i}.` [{s['title']}]({s.get('webpage_url','')}) `{fmt_dur(s['duration'])}`" for i, s in enumerate(list(q.queue)[:10], 1)])
            if len(q.queue) > 10: up += f"\n*...and {len(q.queue)-10} more*"
            embed.add_field(name="⏭️ Up Next", value=up, inline=False)
        embed.set_footer(text=f"🔁 Loop: {q.loop_mode} | 🔊 Vol: {int(q.volume*100)}% | 📋 {len(q.queue)} queued")
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        q = get_queue(ctx.guild.id)
        if not q.current: return await ctx.send(embed=mk_embed("❌ Nothing Playing", "No song is playing."))
        s = q.current
        embed = discord.Embed(title="🎵 Now Playing", color=0x4ade80)
        embed.add_field(name="Track", value=f"**[{s['title']}]({s['webpage_url']})**", inline=False)
        embed.add_field(name="⏱ Duration", value=f"`{fmt_dur(s['duration'])}`", inline=True)
        embed.add_field(name="🔊 Volume", value=f"`{int(q.volume*100)}%`", inline=True)
        embed.add_field(name="🔁 Loop", value=f"`{q.loop_mode}`", inline=True)
        if s.get("thumbnail"): embed.set_thumbnail(url=s["thumbnail"])
        embed.set_footer(text="🎵 NinjuBot | Made by sdb_darkninja")
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, vol: int):
        if not 1 <= vol <= 100: return await ctx.send(embed=mk_embed("❌ Invalid", "Use 1-100.", color=0xFF0000))
        q = get_queue(ctx.guild.id); q.volume = vol / 100
        if ctx.voice_client and ctx.voice_client.source: ctx.voice_client.source.volume = q.volume
        await ctx.send(embed=mk_embed("🔊 Volume", f"Set to **{vol}%**"))

    @commands.command(name="loop")
    async def loop(self, ctx, mode: str = "song"):
        mode = mode.lower()
        if mode not in ("song","queue","none"): return await ctx.send(embed=mk_embed("❌ Invalid", "Use `song`, `queue`, or `none`.", color=0xFF0000))
        get_queue(ctx.guild.id).loop_mode = mode
        icons = {"song":"🔂","queue":"🔁","none":"➡️"}
        await ctx.send(embed=mk_embed(f"{icons[mode]} Loop", f"Mode → **{mode}**"))

    @commands.command(name="join", aliases=["connect"])
    async def join(self, ctx):
        if await self.ensure_voice(ctx): await ctx.send(embed=mk_embed("✅ Connected", f"Joined **{ctx.author.voice.channel.name}**"))

    @commands.command(name="leave", aliases=["dc","disconnect"])
    async def leave(self, ctx):
        if ctx.voice_client: get_queue(ctx.guild.id).clear(); await ctx.voice_client.disconnect(); await ctx.send(embed=mk_embed("👋 Disconnected", "Left the voice channel."))

    @commands.command(name="search")
    async def search(self, ctx, *, query: str):
        msg = await ctx.send(embed=discord.Embed(title="🔍 Searching...", description=f"```{query[:100]}```", color=0xf59e0b))
        try:
            data = await self.bot.loop.run_in_executor(_executor, lambda: ytdl.extract_info(f"ytsearch5:{query}", download=False))
            results = data.get("entries", [])[:5]
        except Exception as e:
            return await msg.edit(embed=mk_embed("❌ Error", str(e)[:300], color=0xFF0000))
        embed = discord.Embed(title="🔍 Results", color=0x4ade80)
        for i, r in enumerate(results, 1):
            embed.add_field(name=f"{i}. {r['title'][:50]}", value=f"⏱ `{fmt_dur(r.get('duration',0))}` | [Watch]({r['webpage_url']})", inline=False)
        embed.set_footer(text="Reply with a number 1-5 to play")
        await msg.edit(embed=embed)
        def check(m): return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        try:
            reply = await self.bot.wait_for("message", check=check, timeout=20)
            idx = int(reply.content) - 1
            if 0 <= idx < len(results): await self.play(ctx, query=results[idx]["webpage_url"])
        except asyncio.TimeoutError:
            await ctx.send(embed=mk_embed("⏱ Timed Out", "Search timed out."))

    @discord.app_commands.command(name="play", description="Play a song with live suggestions")
    @discord.app_commands.describe(query="Song name or URL")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        # Defer immediately — gives us 15 minutes instead of 3 seconds
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send(embed=mk_embed("❌ No Voice Channel", "Join a voice channel first!", color=0xFF0000), ephemeral=True)

        # Connect to voice
        vc = interaction.guild.voice_client
        try:
            if not vc:
                vc = await self._connect_with_retry(interaction.user.voice.channel)
            elif vc.channel != interaction.user.voice.channel:
                await vc.move_to(interaction.user.voice.channel)
        except Exception as e:
            return await interaction.followup.send(embed=mk_embed("❌ Connect Failed", f"Could not join voice channel: {e}", color=0xFF0000))

        await interaction.followup.send(embed=discord.Embed(
            title="🔍 Searching...", description=f"```{query[:100]}```", color=0xf59e0b
        ).set_footer(text="🎵 NinjuBot | Made by sdb_darkninja"))

        q = get_queue(interaction.guild.id)
        try:
            result = await asyncio.wait_for(resolve_source(query, self.bot.loop, self.session), timeout=20.0)
        except Exception as e:
            return await interaction.edit_original_response(embed=mk_embed("❌ Error", str(e)[:300], color=0xFF0000))

        q.add(result)
        class FakeCtx:
            def __init__(s, guild, voice_client, channel, bot): s.guild=guild; s.voice_client=voice_client; s.channel=channel; s.bot=bot
            async def send(s, **kwargs): await interaction.channel.send(**kwargs)
        fake = FakeCtx(interaction.guild, vc, interaction.channel, self.bot)
        if vc.is_playing() or vc.is_paused():
            embed = discord.Embed(title="➕ Added to Queue", color=0x4ade80)
            embed.add_field(name="Track", value=f"**[{result['title']}]({result['webpage_url']})**", inline=False)
            embed.add_field(name="⏱ Duration", value=f"`{fmt_dur(result['duration'])}`", inline=True)
            embed.add_field(name="📋 Position", value=f"`#{len(q.queue)}`", inline=True)
            if result.get("thumbnail"): embed.set_thumbnail(url=result["thumbnail"])
            embed.set_footer(text="🎵 NinjuBot | Made by sdb_darkninja")
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.edit_original_response(embed=mk_embed("✅ Found", f"**{result['title']}**\nStarting...", color=0x4ade80))
            await self.play_next(fake)

    @slash_play.autocomplete("query")
    async def play_autocomplete(self, interaction: discord.Interaction, current: str):
        if len(current) < 1: return []
        try:
            async with self.session.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client":"firefox","ds":"yt","q":current},
                headers={"User-Agent":"Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                data = await resp.json(content_type=None)
                return [discord.app_commands.Choice(name=s[:100], value=s[:100]) for s in data[1][:8] if isinstance(s,str)]
        except: pass
        return [discord.app_commands.Choice(name=current[:100], value=current[:100])]

async def setup(bot):
    await bot.add_cog(Music(bot))
