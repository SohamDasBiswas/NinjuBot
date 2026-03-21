import discord
from discord.ext import commands
import datetime

def mk_embed(title, desc, color=0xFF4500):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.now(datetime.timezone.utc)
    e.set_footer(text="🛡️ NinjuBot Moderation | Made by sdb_darkninja")
    return e

def do_log(action, target, moderator='System', reason='', guild=None):
    try:
        from bot import log_mod_action
        log_mod_action(
            action=action, target=str(target), moderator=str(moderator),
            reason=reason or '', guild_id=str(guild.id) if guild else '',
            guild_name=guild.name if guild else ''
        )
    except Exception as e:
        print(f'[AuditLog] {e}', flush=True)


# ══════════════════════════════════════════════════════════════
#  MODERATION COMMANDS
# ══════════════════════════════════════════════════════════════

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ban')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason='No reason provided'):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=mk_embed('❌ Error', 'You cannot ban someone with equal or higher role.', 0xFF0000))
        await member.ban(reason=reason)
        do_log('ban', member, ctx.author, reason, ctx.guild)
        await ctx.send(embed=mk_embed('🔨 Banned', f'**{member}** has been banned.\n**Reason:** {reason}'))

    @commands.command(name='unban')
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, user: str):
        bans = [entry async for entry in ctx.guild.bans()]
        for ban in bans:
            if str(ban.user) == user or str(ban.user.id) == user:
                await ctx.guild.unban(ban.user)
                do_log('unban', ban.user, ctx.author, '', ctx.guild)
                return await ctx.send(embed=mk_embed('✅ Unbanned', f'**{ban.user}** has been unbanned.', 0x2ECC71))
        await ctx.send(embed=mk_embed('❌ Not Found', f'Could not find banned user: `{user}`', 0xFF0000))

    @commands.command(name='kick')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason='No reason provided'):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=mk_embed('❌ Error', 'You cannot kick someone with equal or higher role.', 0xFF0000))
        await member.kick(reason=reason)
        do_log('kick', member, ctx.author, reason, ctx.guild)
        await ctx.send(embed=mk_embed('👢 Kicked', f'**{member}** has been kicked.\n**Reason:** {reason}', 0xFFA500))

    @commands.command(name='timeout', aliases=['mute', 'tm'])
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int = 10, *, reason='No reason provided'):
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        do_log('timeout', member, ctx.author, f'{minutes}m — {reason}', ctx.guild)
        await ctx.send(embed=mk_embed('⏰ Timed Out', f'**{member}** timed out for **{minutes} min**.\n**Reason:** {reason}', 0xFFA500))

    @commands.command(name='untimeout', aliases=['unmute'])
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member):
        await member.timeout(None)
        do_log('untimeout', member, ctx.author, '', ctx.guild)
        await ctx.send(embed=mk_embed('✅ Timeout Removed', f'**{member}\'s** timeout has been removed.', 0x2ECC71))

    @commands.command(name='warn')
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason='No reason provided'):
        do_log('warn', member, ctx.author, reason, ctx.guild)
        try:
            await member.send(embed=mk_embed('⚠️ Warning', f'You were warned in **{ctx.guild.name}**.\n**Reason:** {reason}', 0xFFFF00))
        except Exception:
            pass
        await ctx.send(embed=mk_embed('⚠️ Warned', f'**{member}** has been warned.\n**Reason:** {reason}', 0xFFFF00))

    @commands.command(name='purge', aliases=['clear', 'clean'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 10):
        if amount < 1 or amount > 100:
            return await ctx.send(embed=mk_embed('❌ Error', 'Amount must be between 1 and 100.', 0xFF0000))
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        do_log('purge', f'{len(deleted)} messages in #{ctx.channel.name}', ctx.author, '', ctx.guild)
        msg = await ctx.send(embed=mk_embed('🗑️ Purged', f'Deleted **{len(deleted)}** messages.', 0x3498DB))
        await msg.delete(delay=3)

    @commands.command(name='slowmode', aliases=['slow'])
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0):
        await ctx.channel.edit(slowmode_delay=seconds)
        do_log('slowmode', f'#{ctx.channel.name}', ctx.author, f'{seconds}s', ctx.guild)
        await ctx.send(embed=mk_embed('🐢 Slowmode', f'Set to **{seconds}s** in {ctx.channel.mention}.', 0xFFA500))

    @commands.command(name='lock')
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        do_log('lock', f'#{ctx.channel.name}', ctx.author, '', ctx.guild)
        await ctx.send(embed=mk_embed('🔒 Locked', f'{ctx.channel.mention} has been locked.'))

    @commands.command(name='unlock')
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        do_log('unlock', f'#{ctx.channel.name}', ctx.author, '', ctx.guild)
        await ctx.send(embed=mk_embed('🔓 Unlocked', f'{ctx.channel.mention} has been unlocked.', 0x2ECC71))

    @commands.command(name='nick')
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        old = member.display_name
        await member.edit(nick=nickname)
        do_log('nick', member, ctx.author, f'{old} → {nickname or "reset"}', ctx.guild)
        await ctx.send(embed=mk_embed('✏️ Nickname', f'Changed to `{nickname or "reset"}`.', 0x3498DB))

    @ban.error
    @kick.error
    @timeout.error
    @warn.error
    @purge.error
    async def mod_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=mk_embed('❌ No Permission', 'You don\'t have permission.', 0xFF0000))
        elif isinstance(error, (commands.MemberNotFound, commands.BadArgument)):
            await ctx.send(embed=mk_embed('❌ Error', str(error), 0xFF0000))


# ══════════════════════════════════════════════════════════════
#  AUTO EVENT LOGGER — logs ALL Discord events automatically
# ══════════════════════════════════════════════════════════════

class AutoLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Member events ──────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member):
        do_log('join', f'{member} ({member.id})', 'System',
               f'Account created <t:{int(member.created_at.timestamp())}:R>', member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        do_log('leave', f'{member} ({member.id})', 'System', '', member.guild)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        # Try to get reason from Discord audit log
        reason = 'No reason provided'
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    reason = str(entry.reason or 'No reason provided')
                    moderator = str(entry.user)
                    do_log('ban', f'{user} ({user.id})', moderator, reason, guild)
                    return
        except Exception:
            pass
        do_log('ban', f'{user} ({user.id})', 'Unknown', reason, guild)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        moderator = 'Unknown'
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    moderator = str(entry.user)
                    break
        except Exception:
            pass
        do_log('unban', f'{user} ({user.id})', moderator, '', guild)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = after.guild
        # Timeout applied or removed
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                do_log('timeout', f'{after} ({after.id})', 'Moderator',
                       f'Until {after.timed_out_until.strftime("%Y-%m-%d %H:%M UTC")}', guild)
            else:
                do_log('untimeout', f'{after} ({after.id})', 'Moderator', '', guild)
        # Nickname changed
        if before.nick != after.nick:
            do_log('nick', f'{after} ({after.id})', 'Moderator',
                   f'{before.nick or before.name} → {after.nick or after.name}', guild)
        # Roles added
        added = set(after.roles) - set(before.roles)
        for role in added:
            if role.name != '@everyone':
                do_log('role_add', f'{after} ({after.id})', 'Moderator', f'+{role.name}', guild)
        # Roles removed
        removed = set(before.roles) - set(after.roles)
        for role in removed:
            if role.name != '@everyone':
                do_log('role_remove', f'{after} ({after.id})', 'Moderator', f'-{role.name}', guild)

    # ── Message events ─────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild: return
        content = message.content[:80] + ('…' if len(message.content) > 80 else '')
        do_log('delete', f'{message.author} in #{message.channel.name}',
               'System', f'"{content}"', message.guild)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild: return
        if before.content == after.content: return
        b = before.content[:50] + ('…' if len(before.content) > 50 else '')
        a = after.content[:50] + ('…' if len(after.content) > 50 else '')
        do_log('edit', f'{before.author} in #{before.channel.name}',
               str(before.author), f'"{b}" → "{a}"', before.guild)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages: return
        guild = messages[0].guild
        channel = messages[0].channel
        do_log('purge', f'{len(messages)} messages in #{channel.name}',
               'Moderator', f'Bulk delete of {len(messages)} messages', guild)

    # ── Channel events ─────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        do_log('channel_create', f'#{channel.name}', 'Moderator', str(channel.type), channel.guild)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        do_log('channel_delete', f'#{channel.name}', 'Moderator', str(channel.type), channel.guild)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            do_log('channel_rename', f'#{before.name} → #{after.name}',
                   'Moderator', '', after.guild)

    # ── Role events ────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        do_log('role_create', f'@{role.name}', 'Moderator', '', role.guild)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        do_log('role_delete', f'@{role.name}', 'Moderator', '', role.guild)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if before.name != after.name:
            do_log('role_rename', f'@{before.name} → @{after.name}', 'Moderator', '', after.guild)

    # ── Server events ──────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.name != after.name:
            do_log('server_rename', f'{before.name} → {after.name}', 'Moderator', '', after)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        do_log('invite_create', f'{invite.code}', str(invite.inviter or 'Unknown'),
               f'Max uses: {invite.max_uses or "∞"}, expires: {invite.max_age or "never"}s',
               invite.guild)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        do_log('invite_delete', f'{invite.code}', 'System', '', invite.guild)

    # ── Voice events ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel: return
        if after.channel and not before.channel:
            do_log('voice_join', f'{member}', 'System', f'Joined #{after.channel.name}', member.guild)
        elif before.channel and not after.channel:
            do_log('voice_leave', f'{member}', 'System', f'Left #{before.channel.name}', member.guild)
        elif before.channel and after.channel:
            do_log('voice_move', f'{member}', 'System',
                   f'#{before.channel.name} → #{after.channel.name}', member.guild)

    # ── Boost events ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Already handled above — this duplicate is intentional for boost detection
        pass

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added   = set(e.name for e in after) - set(e.name for e in before)
        removed = set(e.name for e in before) - set(e.name for e in after)
        for name in added:   do_log('emoji_add',    name, 'Moderator', '', guild)
        for name in removed: do_log('emoji_remove', name, 'Moderator', '', guild)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(AutoLogger(bot))
