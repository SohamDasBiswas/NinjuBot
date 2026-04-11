"""
cogs/voice_utils.py — Shared voice connection helper for NinjuBot

Root cause of 4006 + TimeoutError loop:
  - reconnect=True  → discord.py retries internally forever → TimeoutError
  - reconnect=False → discord.py raises 4006 immediately
  - Both fail when the gateway session_id is stale from a previous run

Real fix:
  The main gateway WebSocket holds a session_id. Voice connections use this
  session_id to authenticate. After a bot restart, the OLD session_id is
  still cached in bot.ws until Discord sends a READY or RESUMED event that
  updates it. If we connect to voice before that refresh happens, we get 4006.

  Solution: after sending op4 leave, wait for Discord to send a fresh
  VOICE_STATE_UPDATE back (confirming we left), THEN connect. This ensures
  the gateway session is fully settled before we try to join.

  We also kill any existing VoiceClient first (critical — the music cog's
  old VC must die before TTS can connect, and vice versa).
"""

import asyncio
import discord
from discord.ext import commands

_connect_locks: dict[int, asyncio.Lock] = {}

def _get_lock(guild_id: int) -> asyncio.Lock:
    if guild_id not in _connect_locks:
        _connect_locks[guild_id] = asyncio.Lock()
    return _connect_locks[guild_id]


async def _kill_existing_vc(guild: discord.Guild) -> None:
    vc = guild.voice_client
    if vc:
        try:
            vc.stop()
        except Exception:
            pass
        try:
            await vc.disconnect(force=True)
        except Exception:
            pass
        await asyncio.sleep(0.5)


async def _send_op4_leave(bot: commands.Bot, guild_id: int) -> None:
    """Send raw op4 VOICE_STATE_UPDATE(channel=null) through the gateway WS."""
    try:
        await bot.ws.send_as_json({
            "op": 4,
            "d": {
                "guild_id":   str(guild_id),
                "channel_id": None,
                "self_mute":  False,
                "self_deaf":  False,
            }
        })
    except Exception as e:
        print(f"[VoiceUtils] op4 leave error (non-fatal): {e}", flush=True)


async def safe_connect(
    bot: commands.Bot,
    channel: discord.VoiceChannel,
    *,
    self_deaf: bool = True,
    timeout: float = 30.0,
) -> discord.VoiceClient:
    """
    Connect to a voice channel safely. Used by both music and TTS cogs.
    Per-guild lock prevents the two cogs racing each other.
    """
    guild = channel.guild
    lock  = _get_lock(guild.id)

    async with lock:
        # Already in the right channel — return immediately
        existing = guild.voice_client
        if existing and existing.is_connected() and existing.channel == channel:
            return existing

        # Step 1: kill any existing VC (music, TTS, or anything else)
        await _kill_existing_vc(guild)

        # Step 2: tell Discord's backend we left voice completely
        await _send_op4_leave(bot, guild.id)

        # Step 3: wait for Discord to acknowledge the leave by sending back
        # a VOICE_STATE_UPDATE with channel_id=null for our bot user.
        # This confirms the old session is fully dead before we reconnect.
        def _is_our_leave(member, before, after):
            return (
                member.id == bot.user.id
                and member.guild.id == guild.id
                and after.channel is None
            )

        try:
            await bot.wait_for(
                "voice_state_update",
                check=_is_our_leave,
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            # If we weren't in voice before, no leave event comes — that's fine
            pass

        # Small buffer after the leave ACK
        await asyncio.sleep(1.0)

        # Step 4: single connect attempt, no retry loop
        try:
            vc = await channel.connect(
                timeout=timeout,
                reconnect=False,
                self_deaf=self_deaf,
            )
            print(f"[VoiceUtils] ✅ Connected to {channel.name} in {guild.name}", flush=True)
            return vc
        except Exception as e:
            print(f"[VoiceUtils] ❌ connect failed: {type(e).__name__}: {e}", flush=True)
            raise
