import discord
from discord.ext import commands
import datetime

def mk_embed(title, desc, color=0xFF4500):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.now(datetime.timezone.utc)
    e.set_footer(text="🛡️ NinjuBot Moderation | Made by sdb_darkninja")
    return e

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def log(self, action, target, moderator, reason='', guild=None):
        try:
            from bot import log_mod_action
            log_mod_action(
                action=action,
                target=str(target),
                moderator=str(moderator),
                reason=reason or 'No reason provided',
                guild_id=str(guild.id) if guild else '',
                guild_name=guild.name if guild else ''
            )
        except Exception as e:
            print(f'[ModLog] {e}', flush=True)

    # ── Ban ──────────────────────────────────────────────────────
    @commands.command(name='ban')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason='No reason provided'):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=mk_embed('❌ Error', 'You cannot ban someone with equal or higher role.', 0xFF0000))
        await member.ban(reason=reason)
        self.log('ban', member, ctx.author, reason, ctx.guild)
        await ctx.send(embed=mk_embed('🔨 Banned', f'**{member}** has been banned.\n**Reason:** {reason}', 0xFF4500))

    # ── Unban ────────────────────────────────────────────────────
    @commands.command(name='unban')
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, user: str):
        bans = [entry async for entry in ctx.guild.bans()]
        for ban in bans:
            if str(ban.user) == user or str(ban.user.id) == user:
                await ctx.guild.unban(ban.user)
                self.log('unban', ban.user, ctx.author, '', ctx.guild)
                return await ctx.send(embed=mk_embed('✅ Unbanned', f'**{ban.user}** has been unbanned.', 0x2ECC71))
        await ctx.send(embed=mk_embed('❌ Not Found', f'Could not find banned user: `{user}`', 0xFF0000))

    # ── Kick ─────────────────────────────────────────────────────
    @commands.command(name='kick')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason='No reason provided'):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=mk_embed('❌ Error', 'You cannot kick someone with equal or higher role.', 0xFF0000))
        await member.kick(reason=reason)
        self.log('kick', member, ctx.author, reason, ctx.guild)
        await ctx.send(embed=mk_embed('👢 Kicked', f'**{member}** has been kicked.\n**Reason:** {reason}', 0xFFA500))

    # ── Timeout ──────────────────────────────────────────────────
    @commands.command(name='timeout', aliases=['mute', 'tm'])
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int = 10, *, reason='No reason provided'):
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        self.log('timeout', member, ctx.author, f'{minutes}m — {reason}', ctx.guild)
        await ctx.send(embed=mk_embed('⏰ Timed Out', f'**{member}** timed out for **{minutes} min**.\n**Reason:** {reason}', 0xFFA500))

    # ── Untimeout ────────────────────────────────────────────────
    @commands.command(name='untimeout', aliases=['unmute'])
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member):
        await member.timeout(None)
        self.log('untimeout', member, ctx.author, '', ctx.guild)
        await ctx.send(embed=mk_embed('✅ Timeout Removed', f'**{member}**\'s timeout has been removed.', 0x2ECC71))

    # ── Warn ─────────────────────────────────────────────────────
    @commands.command(name='warn')
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason='No reason provided'):
        self.log('warn', member, ctx.author, reason, ctx.guild)
        try:
            await member.send(embed=mk_embed('⚠️ Warning', f'You were warned in **{ctx.guild.name}**.\n**Reason:** {reason}', 0xFFFF00))
        except Exception:
            pass
        await ctx.send(embed=mk_embed('⚠️ Warned', f'**{member}** has been warned.\n**Reason:** {reason}', 0xFFFF00))

    # ── Purge ────────────────────────────────────────────────────
    @commands.command(name='purge', aliases=['clear', 'clean'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 10):
        if amount < 1 or amount > 100:
            return await ctx.send(embed=mk_embed('❌ Error', 'Amount must be between 1 and 100.', 0xFF0000))
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        self.log('purge', f'{len(deleted)} messages in #{ctx.channel.name}', ctx.author, '', ctx.guild)
        msg = await ctx.send(embed=mk_embed('🗑️ Purged', f'Deleted **{len(deleted)}** messages.', 0x3498DB))
        await msg.delete(delay=3)

    # ── Slowmode ─────────────────────────────────────────────────
    @commands.command(name='slowmode', aliases=['slow'])
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0):
        await ctx.channel.edit(slowmode_delay=seconds)
        self.log('slowmode', f'#{ctx.channel.name}', ctx.author, f'{seconds}s', ctx.guild)
        if seconds == 0:
            await ctx.send(embed=mk_embed('✅ Slowmode Off', f'Slowmode disabled in {ctx.channel.mention}.', 0x2ECC71))
        else:
            await ctx.send(embed=mk_embed('🐢 Slowmode', f'Slowmode set to **{seconds}s** in {ctx.channel.mention}.', 0xFFA500))

    # ── Lock / Unlock ────────────────────────────────────────────
    @commands.command(name='lock')
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        self.log('lock', f'#{ctx.channel.name}', ctx.author, '', ctx.guild)
        await ctx.send(embed=mk_embed('🔒 Locked', f'{ctx.channel.mention} has been locked.', 0xFF4500))

    @commands.command(name='unlock')
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        self.log('unlock', f'#{ctx.channel.name}', ctx.author, '', ctx.guild)
        await ctx.send(embed=mk_embed('🔓 Unlocked', f'{ctx.channel.mention} has been unlocked.', 0x2ECC71))

    # ── Nick ─────────────────────────────────────────────────────
    @commands.command(name='nick')
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        old = member.display_name
        await member.edit(nick=nickname)
        self.log('nick', member, ctx.author, f'{old} → {nickname or "reset"}', ctx.guild)
        await ctx.send(embed=mk_embed('✏️ Nickname Changed', f'**{member}**\'s nickname changed to `{nickname or "reset"}`.', 0x3498DB))

    # ── Error handler ────────────────────────────────────────────
    @ban.error
    @kick.error
    @timeout.error
    @warn.error
    @purge.error
    async def mod_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=mk_embed('❌ No Permission', 'You don\'t have permission to do that.', 0xFF0000))
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=mk_embed('❌ Not Found', 'Could not find that member.', 0xFF0000))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=mk_embed('❌ Bad Argument', 'Please check your command arguments.', 0xFF0000))

async def setup(bot):
    await bot.add_cog(Moderation(bot))
