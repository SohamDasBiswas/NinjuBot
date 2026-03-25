"""
cogs/tts.py  —  Text-to-Speech for Discord Voice Channels
──────────────────────────────────────────────────────────
Commands
  -tts on      : Activate TTS in the current VC — bot joins & starts reading
                 every message sent in the linked text channel aloud.
  -tts off     : Deactivate TTS and disconnect.
  -tts channel : Set / show the text channel to listen to.
  -tts skip    : Skip the current TTS message being spoken.
  -tts status  : Show TTS status for this server.

How it works
  • Uses gTTS (Google Text-to-Speech, free, no API key) to synthesise speech.
  • Saves each line as a temp .mp3, plays it with FFmpegPCMAudio, then deletes.
  • Only works while the invoking user is in a VC.
  • TTS is per-guild; multiple guilds are fully independent.
"""

import asyncio
import os
import tempfile
import discord
from discord.ext import commands
from gtts import gTTS

# ── Per-guild TTS state ────────────────────────────────────────────────────────

class TTSState:
    def __init__(self):
        self.enabled      : bool                       = False
        self.voice_client : discord.VoiceClient | None = None
        self.text_channel : discord.TextChannel | None = None
        self.queue        : asyncio.Queue               = asyncio.Queue()
        self.task         : asyncio.Task | None         = None

    def is_alive(self) -> bool:
        """True only if TTS is enabled AND the voice client is still connected."""
        return (
            self.enabled
            and self.voice_client is not None
            and self.voice_client.is_connected()
        )

    def reset(self):
        """Clear all state back to defaults (called on stop or stale cleanup)."""
        self.enabled      = False
        self.voice_client = None
        self.text_channel = None
        self.queue        = asyncio.Queue()
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None


_states: dict[int, TTSState] = {}   # guild_id → TTSState

def get_state(guild_id: int) -> TTSState:
    if guild_id not in _states:
        _states[guild_id] = TTSState()
    return _states[guild_id]


def mk_embed(title: str, description: str = "", color: int = 0x7289DA) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="NinjuBot TTS")
    return e


# ── TTS worker coroutine ───────────────────────────────────────────────────────

async def tts_worker(state: TTSState):
    """Drain the per-guild TTS queue and speak each item."""
    loop = asyncio.get_event_loop()

    while state.enabled:
        try:
            text: str = await asyncio.wait_for(state.queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
        except Exception:
            break

        vc = state.voice_client
        if not vc or not vc.is_connected():
            # VC dropped — clean up so next -tts on works correctly
            state.reset()
            break

        tmp_path = None
        try:
            # Generate speech in executor so it doesn't block the event loop
            tts_obj = gTTS(text=text[:300], lang="en")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name
            await loop.run_in_executor(None, tts_obj.save, tmp_path)

            # Wait for any currently-playing audio to finish
            while vc.is_playing():
                await asyncio.sleep(0.3)

            # FIX: use call_soon_threadsafe so the Event is set from the correct thread
            done_event = asyncio.Event()

            def after_playing(err):
                if err:
                    print(f"[TTS] Playback error: {err}", flush=True)
                loop.call_soon_threadsafe(done_event.set)

            source = discord.FFmpegPCMAudio(tmp_path)
            vc.play(source, after=after_playing)
            await done_event.wait()

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[TTS] Error speaking: {e}", flush=True)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            try:
                state.queue.task_done()
            except Exception:
                pass


# ── Cog ───────────────────────────────────────────────────────────────────────

class TTS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Command group: -tts <sub> ──────────────────────────────────────────────

    @commands.group(name="tts", invoke_without_command=True)
    async def tts_group(self, ctx: commands.Context):
        await ctx.send(embed=mk_embed(
            "🔊 TTS Help",
            "**Commands:**\n"
            "`-tts on` — Start TTS in your voice channel\n"
            "`-tts off` — Stop TTS and disconnect\n"
            "`-tts channel [#chan]` — Set listening channel (default: current)\n"
            "`-tts skip` — Skip current TTS message\n"
            "`-tts status` — Show TTS status\n\n"
            "**Note:** Only reads messages from Discord users while you're in a VC."
        ))

    # ── -tts on ────────────────────────────────────────────────────────────────

    @tts_group.command(name="on")
    async def tts_on(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(embed=mk_embed(
                "❌ Error", "You must be in a voice channel first!", 0xE74C3C))

        state = get_state(ctx.guild.id)

        # FIX: if state says enabled but VC is dead, clean it up silently first
        if state.enabled and not state.is_alive():
            state.reset()
            if ctx.voice_client:
                try:
                    await ctx.voice_client.disconnect(force=True)
                except Exception:
                    pass

        if state.enabled:
            return await ctx.send(embed=mk_embed(
                "⚠️ Already On",
                "TTS is already running. Use `-tts off` to stop.", 0xF39C12))

        vc_channel = ctx.author.voice.channel

        # Set state BEFORE connecting so nothing slips through the gap
        state.enabled      = True
        state.text_channel = ctx.channel
        state.queue        = asyncio.Queue()

        # Send embed FIRST — appears before the bot-join system notification
        await ctx.send(embed=mk_embed(
            "🔊 TTS Activated!",
            f"Now reading **#{ctx.channel.name}** aloud in **{vc_channel.name}**.\n"
            f"Use `-tts channel #otherchan` to change, or `-tts off` to stop.",
            0x2ECC71
        ))

        # Connect to VC
        try:
            if ctx.voice_client:
                await ctx.voice_client.move_to(vc_channel)
                state.voice_client = ctx.voice_client
            else:
                state.voice_client = await vc_channel.connect(timeout=10.0, reconnect=True)
        except Exception as e:
            state.reset()
            return await ctx.send(embed=mk_embed(
                "❌ Connect Failed", f"Could not join voice channel: {e}", 0xE74C3C))

        # Start worker AFTER VC is confirmed connected
        state.task = asyncio.create_task(tts_worker(state))

    # ── -tts off ───────────────────────────────────────────────────────────────

    @tts_group.command(name="off")
    async def tts_off(self, ctx: commands.Context):
        state = get_state(ctx.guild.id)

        if not state.enabled and not state.is_alive():
            return await ctx.send(embed=mk_embed(
                "⚠️ Not Running", "TTS is not currently active.", 0xF39C12))

        if state.voice_client and state.voice_client.is_connected():
            try:
                state.voice_client.stop()
                await state.voice_client.disconnect()
            except Exception:
                pass

        state.reset()
        await ctx.send(embed=mk_embed(
            "🔇 TTS Disabled", "Left voice channel and stopped TTS.", 0xE74C3C))

    # ── -tts channel ───────────────────────────────────────────────────────────

    @tts_group.command(name="channel")
    async def tts_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        state = get_state(ctx.guild.id)
        if channel:
            state.text_channel = channel
            await ctx.send(embed=mk_embed(
                "✅ TTS Channel Set", f"Now reading messages from {channel.mention}.", 0x2ECC71))
        else:
            ch_name = state.text_channel.mention if state.text_channel else "Not set"
            await ctx.send(embed=mk_embed("📢 TTS Channel", f"Currently reading: {ch_name}"))

    # ── -tts skip ──────────────────────────────────────────────────────────────

    @tts_group.command(name="skip")
    async def tts_skip(self, ctx: commands.Context):
        state = get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
            await ctx.send(embed=mk_embed("⏭️ Skipped", "Skipped the current TTS message."))
        else:
            await ctx.send(embed=mk_embed("⚠️ Nothing Playing", "No TTS message is playing right now."))

    # ── -tts status ────────────────────────────────────────────────────────────

    @tts_group.command(name="status")
    async def tts_status(self, ctx: commands.Context):
        state = get_state(ctx.guild.id)
        status  = "🟢 Active" if state.is_alive() else "🔴 Inactive"
        vc_name = state.voice_client.channel.name if state.is_alive() else "Not connected"
        ch_name = state.text_channel.mention if state.text_channel else "Not set"
        q_size  = state.queue.qsize() if state.queue else 0
        await ctx.send(embed=mk_embed(
            "📊 TTS Status",
            f"**Status:** {status}\n"
            f"**Voice Channel:** {vc_name}\n"
            f"**Text Channel:** {ch_name}\n"
            f"**Queue:** {q_size} message(s) pending"
        ))

    # ── Listen for messages and enqueue ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        state = get_state(message.guild.id)

        if not state.is_alive() or not state.text_channel:
            return
        if message.channel.id != state.text_channel.id:
            return

        # FIX: user must be in the SAME VC as the bot (not just any VC)
        member = message.guild.get_member(message.author.id)
        if not member or not member.voice or not member.voice.channel:
            return
        if member.voice.channel.id != state.voice_client.channel.id:
            return

        content = message.clean_content
        if not content or content.startswith(("-", "/", "!")):
            return

        speak_text = f"{member.display_name} says: {content}"
        await state.queue.put(speak_text)

    # ── Auto-cleanup when bot is kicked/disconnected from VC ──────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        # Only care when it's the bot being removed from a VC
        if member.id != self.bot.user.id:
            return
        if before.channel is None or after.channel is not None:
            return

        state = get_state(member.guild.id)
        if state.enabled:
            state.reset()


async def setup(bot: commands.Bot):
    try:
        import gtts  # noqa: F401
    except ImportError:
        print("[TTS] ⚠️  gTTS not installed — run: pip install gTTS", flush=True)
        return
    await bot.add_cog(TTS(bot))
    print("✅ TTS cog loaded", flush=True)
