"""
antinuke.py — NinjuBot Anti-Nuke System
Protects servers from raids, mass bans, mass channel deletes, webhook spams, etc.

How it works:
  - Tracks how many dangerous actions each user performs per time window
  - If a user exceeds the threshold → immediately punish (ban/kick/strip roles)
  - Whitelist trusted users/bots so they are never punished
  - Owner is always immune

Add to COGS list in bot.py:
    "cogs.antinuke",

Commands:
    -antinuke              Show current settings
    -antinuke on/off       Enable or disable
    -antinuke whitelist @user  Add to whitelist
    -antinuke unwhitelist @user
    -antinuke threshold <action> <count>  Set threshold
    -antinuke punishment ban/kick/strip   Set punishment type
    -antinuke logchannel #channel         Set alert channel
"""

import discord
from discord.ext import commands
import datetime
import asyncio
from collections import defaultdict
from database import get_db

# ── Default thresholds (actions allowed per 10 seconds before trigger) ──
DEFAULTS = {
    'ban':            2,   # max bans in 10s
    'kick':           3,
    'channel_delete': 2,
    'channel_create': 5,
    'role_delete':    2,
    'role_create':    5,
    'webhook_create': 3,
    'member_prune':   1,
    'everyone_ping':  2,
}

WINDOW = 10   # seconds
ROLLBACK_LIMIT = 10  # max actions to undo during rollback


def mk_embed(title, desc, color=0xFF0000):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.now(datetime.timezone.utc)
    e.set_footer(text="🛡️ NinjuBot Anti-Nuke")
    return e


def get_cfg(guild_id: int) -> dict:
    """Load anti-nuke config from MongoDB."""
    doc = get_db().antinuke.find_one({'guild_id': str(guild_id)})
    if not doc:
        return {
            'guild_id':   str(guild_id),
            'enabled':    False,
            'punishment': 'ban',       # ban | kick | strip
            'whitelist':  [],
            'thresholds': dict(DEFAULTS),
            'log_channel': None,
        }
    doc.setdefault('thresholds', dict(DEFAULTS))
    doc.setdefault('punishment', 'ban')
    doc.setdefault('whitelist',  [])
    doc.setdefault('log_channel', None)
    return doc


def save_cfg(cfg: dict):
    get_db().antinuke.update_one(
        {'guild_id': cfg['guild_id']},
        {'$set': cfg},
        upsert=True
    )


class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # action_counts[guild_id][user_id][action] = [(timestamp), ...]
        self._counts: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        # Track recently created channels for rollback
        self._recent_channels: dict = defaultdict(list)   # guild_id → [(channel_id, name, type, category_id)]
        self._recent_roles:    dict = defaultdict(list)   # guild_id → [(role_id, name, color, perms)]

    # ──────────────────────────────────────────────────────────────
    #  CORE: check if an action by a user crosses the threshold
    # ──────────────────────────────────────────────────────────────
    async def _check(self, guild: discord.Guild, user: discord.Member | discord.User | None, action: str):
        if user is None:
            return
        cfg = get_cfg(guild.id)
        if not cfg['enabled']:
            return

        # Owner and whitelisted users are immune
        if user.id == guild.owner_id:
            return
        if str(user.id) in cfg['whitelist']:
            return
        # Bots on the whitelist (like the bot itself)
        if isinstance(user, discord.Member) and user.bot and str(user.id) in cfg['whitelist']:
            return

        now = datetime.datetime.utcnow().timestamp()
        threshold = cfg['thresholds'].get(action, DEFAULTS.get(action, 5))

        # Keep only events within the time window
        window_start = now - WINDOW
        self._counts[guild.id][user.id][action] = [
            t for t in self._counts[guild.id][user.id][action] if t > window_start
        ]
        self._counts[guild.id][user.id][action].append(now)

        count = len(self._counts[guild.id][user.id][action])
        if count >= threshold:
            # Clear count so we don't trigger multiple times
            self._counts[guild.id][user.id][action] = []
            await self._punish(guild, user, action, count, cfg)

    # ──────────────────────────────────────────────────────────────
    #  PUNISH: ban / kick / strip roles
    # ──────────────────────────────────────────────────────────────
    async def _punish(self, guild: discord.Guild, user, action: str, count: int, cfg: dict):
        punishment = cfg.get('punishment', 'ban')
        reason = f'[AntiNuke] Triggered {action} × {count} in {WINDOW}s'

        member = guild.get_member(user.id) if isinstance(user, discord.User) else user

        try:
            if punishment == 'ban':
                await guild.ban(user, reason=reason, delete_message_days=0)
            elif punishment == 'kick' and member:
                await member.kick(reason=reason)
            elif punishment == 'strip' and member:
                # Remove all roles except @everyone
                safe_roles = [r for r in member.roles if r.is_default()]
                await member.edit(roles=safe_roles, reason=reason)
        except discord.Forbidden:
            punishment = 'strip (no permission to ban/kick)'
        except Exception as ex:
            print(f'[AntiNuke] Punish error: {ex}', flush=True)

        # Log the event
        await self._log(guild, user, action, count, punishment, cfg)

        # Write to audit log DB
        try:
            from bot import log_mod_action
            log_mod_action(
                action=f'antinuke_{punishment}',
                target=str(user),
                moderator='AntiNuke',
                reason=reason,
                guild_id=str(guild.id),
                guild_name=guild.name,
            )
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    #  LOG: send alert to log channel
    # ──────────────────────────────────────────────────────────────
    async def _log(self, guild, user, action, count, punishment, cfg):
        log_ch_id = cfg.get('log_channel')
        if not log_ch_id:
            return
        ch = guild.get_channel(int(log_ch_id))
        if not ch:
            return
        action_icons = {
            'ban':'🔨','kick':'👢','channel_delete':'🗑️','channel_create':'📢',
            'role_delete':'🗑️','role_create':'🎭','webhook_create':'🔗',
            'member_prune':'🚪','everyone_ping':'📣',
        }
        icon = action_icons.get(action, '⚠️')
        e = discord.Embed(
            title='🚨 ANTI-NUKE TRIGGERED',
            color=0xFF0000,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        e.add_field(name='User',       value=f'{user.mention} (`{user}` / `{user.id}`)', inline=False)
        e.add_field(name='Action',     value=f'{icon} `{action}` × **{count}** in {WINDOW}s',     inline=True)
        e.add_field(name='Punishment', value=f'`{punishment}`',                                    inline=True)
        e.set_footer(text='🛡️ NinjuBot Anti-Nuke')
        if hasattr(user, 'display_avatar'):
            e.set_thumbnail(url=user.display_avatar.url)
        try:
            await ch.send(embed=e)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    #  DISCORD EVENT LISTENERS
    # ══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        # Identify who did the ban
        await asyncio.sleep(0.5)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    await self._check(guild, entry.user, 'ban')
                    return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await asyncio.sleep(0.5)
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    await self._check(member.guild, entry.user, 'kick')
                    return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await asyncio.sleep(0.5)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    await self._check(channel.guild, entry.user, 'channel_delete')
                    return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        # Track for potential rollback
        self._recent_channels[channel.guild.id].append({
            'id': channel.id, 'name': channel.name,
            'type': channel.type, 'category_id': channel.category_id,
        })
        if len(self._recent_channels[channel.guild.id]) > ROLLBACK_LIMIT:
            self._recent_channels[channel.guild.id].pop(0)
        await asyncio.sleep(0.5)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    await self._check(channel.guild, entry.user, 'channel_create')
                    return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await asyncio.sleep(0.5)
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    await self._check(role.guild, entry.user, 'role_delete')
                    return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        self._recent_roles[role.guild.id].append({
            'id': role.id, 'name': role.name,
            'color': role.color, 'permissions': role.permissions,
        })
        if len(self._recent_roles[role.guild.id]) > ROLLBACK_LIMIT:
            self._recent_roles[role.guild.id].pop(0)
        await asyncio.sleep(0.5)
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    await self._check(role.guild, entry.user, 'role_create')
                    return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        await asyncio.sleep(0.5)
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                await self._check(channel.guild, entry.user, 'webhook_create')
                return
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        # Detect @everyone / @here pings
        if message.mention_everyone and not message.author.bot:
            await self._check(message.guild, message.author, 'everyone_ping')

    # ══════════════════════════════════════════════════════════════
    #  COMMANDS
    # ══════════════════════════════════════════════════════════════

    @commands.group(name='antinuke', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke(self, ctx):
        """Show anti-nuke settings."""
        cfg = get_cfg(ctx.guild.id)
        status = '🟢 ENABLED' if cfg['enabled'] else '🔴 DISABLED'
        wl = ', '.join(f'<@{uid}>' for uid in cfg['whitelist']) or 'None'
        log_ch = f'<#{cfg["log_channel"]}>' if cfg.get('log_channel') else 'Not set'
        thresholds = '\n'.join(
            f'`{k}` — **{v}** per {WINDOW}s' for k, v in cfg['thresholds'].items()
        )
        e = discord.Embed(title='🛡️ Anti-Nuke Settings', color=0x4eff91 if cfg['enabled'] else 0xFF4444)
        e.add_field(name='Status',     value=status,              inline=True)
        e.add_field(name='Punishment', value=f'`{cfg["punishment"]}`', inline=True)
        e.add_field(name='Log Channel',value=log_ch,              inline=True)
        e.add_field(name='Whitelist',  value=wl,                  inline=False)
        e.add_field(name='Thresholds', value=thresholds,          inline=False)
        e.set_footer(text='Use -antinuke on/off | -antinuke help for all commands')
        await ctx.send(embed=e)

    @antinuke.command(name='on')
    @commands.has_permissions(administrator=True)
    async def antinuke_on(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        cfg['enabled'] = True
        save_cfg(cfg)
        await ctx.send(embed=mk_embed('✅ Anti-Nuke Enabled', 'Server is now protected.', 0x2ECC71))

    @antinuke.command(name='off')
    @commands.has_permissions(administrator=True)
    async def antinuke_off(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        cfg['enabled'] = False
        save_cfg(cfg)
        await ctx.send(embed=mk_embed('⛔ Anti-Nuke Disabled', 'Server protection is OFF.', 0xFFA500))

    @antinuke.command(name='whitelist')
    @commands.has_permissions(administrator=True)
    async def antinuke_whitelist(self, ctx, member: discord.Member):
        cfg = get_cfg(ctx.guild.id)
        uid = str(member.id)
        if uid not in cfg['whitelist']:
            cfg['whitelist'].append(uid)
            save_cfg(cfg)
        await ctx.send(embed=mk_embed('✅ Whitelisted', f'{member.mention} is now trusted.', 0x2ECC71))

    @antinuke.command(name='unwhitelist')
    @commands.has_permissions(administrator=True)
    async def antinuke_unwhitelist(self, ctx, member: discord.Member):
        cfg = get_cfg(ctx.guild.id)
        uid = str(member.id)
        if uid in cfg['whitelist']:
            cfg['whitelist'].remove(uid)
            save_cfg(cfg)
        await ctx.send(embed=mk_embed('🗑️ Removed', f'{member.mention} removed from whitelist.', 0xFFA500))

    @antinuke.command(name='punishment')
    @commands.has_permissions(administrator=True)
    async def antinuke_punishment(self, ctx, mode: str):
        if mode not in ('ban', 'kick', 'strip'):
            return await ctx.send(embed=mk_embed('❌ Invalid', 'Choose: `ban`, `kick`, or `strip`'))
        cfg = get_cfg(ctx.guild.id)
        cfg['punishment'] = mode
        save_cfg(cfg)
        await ctx.send(embed=mk_embed('✅ Punishment Set', f'Punishment is now `{mode}`.', 0x2ECC71))

    @antinuke.command(name='threshold')
    @commands.has_permissions(administrator=True)
    async def antinuke_threshold(self, ctx, action: str, count: int):
        if action not in DEFAULTS:
            actions_list = ', '.join(f'`{k}`' for k in DEFAULTS)
            return await ctx.send(embed=mk_embed('❌ Invalid Action', f'Valid actions: {actions_list}'))
        if not 1 <= count <= 20:
            return await ctx.send(embed=mk_embed('❌ Invalid Count', 'Count must be 1–20.'))
        cfg = get_cfg(ctx.guild.id)
        cfg['thresholds'][action] = count
        save_cfg(cfg)
        await ctx.send(embed=mk_embed('✅ Threshold Updated',
            f'`{action}` threshold set to **{count}** per {WINDOW}s.', 0x2ECC71))

    @antinuke.command(name='logchannel')
    @commands.has_permissions(administrator=True)
    async def antinuke_logchannel(self, ctx, channel: discord.TextChannel):
        cfg = get_cfg(ctx.guild.id)
        cfg['log_channel'] = str(channel.id)
        save_cfg(cfg)
        await ctx.send(embed=mk_embed('✅ Log Channel Set',
            f'Anti-nuke alerts will be sent to {channel.mention}.', 0x2ECC71))

    @antinuke.command(name='help')
    async def antinuke_help(self, ctx):
        cmds = [
            ('-antinuke',                         'Show current settings'),
            ('-antinuke on/off',                  'Enable/disable protection'),
            ('-antinuke whitelist @user',          'Trust a user (never punish)'),
            ('-antinuke unwhitelist @user',        'Remove from whitelist'),
            ('-antinuke punishment ban/kick/strip','Set punishment type'),
            ('-antinuke threshold <action> <n>',  'Set max actions per 10s'),
            ('-antinuke logchannel #channel',      'Set alert log channel'),
        ]
        desc = '\n'.join(f'`{c}` — {d}' for c, d in cmds)
        e = discord.Embed(title='🛡️ Anti-Nuke Commands', description=desc, color=0x4eff91)
        e.add_field(name='Monitored Actions',
            value=', '.join(f'`{k}`' for k in DEFAULTS), inline=False)
        await ctx.send(embed=e)

    @antinuke.error
    async def antinuke_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=mk_embed('❌ No Permission', 'You need Administrator permission.'))


async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
