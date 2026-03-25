"""
backup.py — NinjuBot Server Backup System
Allows server owners to create full server snapshots and restore them.

Place in: cogs/backup.py
Add to COGS in bot.py: "cogs.backup"

Features:
  - Full backup: roles, channels (with permission overwrites), server settings, emojis
  - Restore: applies backup back to the server (with confirmation)
  - Dashboard-controlled via /backup API endpoints
  - Only server owners can access
  - Backups stored in MongoDB 'server_backups' collection
"""

import discord
from discord.ext import commands
import datetime
import asyncio

from database import get_db


# ── Helpers ──────────────────────────────────────────────────

def mk_embed(title, desc, color=0x4eff91):
    e = discord.Embed(title=title, description=desc, color=color)
    e.timestamp = datetime.datetime.now(datetime.timezone.utc)
    e.set_footer(text="💾 NinjuBot Backup System")
    return e


def _serialize_overwrites(overwrites: dict) -> list:
    """Convert permission overwrites to JSON-serializable list."""
    result = []
    for target, overwrite in overwrites.items():
        allow, deny = overwrite.pair()
        result.append({
            'id':    str(target.id),
            'type':  'role' if isinstance(target, discord.Role) else 'member',
            'allow': allow.value,
            'deny':  deny.value,
        })
    return result


def _capture_guild(guild: discord.Guild) -> dict:
    """Capture full server state as a dict."""
    # ── Roles (sorted by position, skip @everyone) ──
    roles = []
    for role in sorted(guild.roles, key=lambda r: r.position):
        if role.is_default():
            continue
        roles.append({
            'id':          str(role.id),
            'name':        role.name,
            'color':       role.color.value,
            'hoist':       role.hoist,
            'mentionable': role.mentionable,
            'permissions': role.permissions.value,
            'position':    role.position,
            'managed':     role.managed,
        })

    # ── Categories ──
    categories = []
    for cat in guild.categories:
        categories.append({
            'id':         str(cat.id),
            'name':       cat.name,
            'position':   cat.position,
            'overwrites': _serialize_overwrites(cat.overwrites),
        })

    # ── Text Channels ──
    text_channels = []
    for ch in guild.text_channels:
        text_channels.append({
            'id':          str(ch.id),
            'name':        ch.name,
            'topic':       ch.topic or '',
            'position':    ch.position,
            'nsfw':        ch.is_nsfw(),
            'slowmode':    ch.slowmode_delay,
            'category_id': str(ch.category_id) if ch.category_id else None,
            'overwrites':  _serialize_overwrites(ch.overwrites),
        })

    # ── Voice Channels ──
    voice_channels = []
    for ch in guild.voice_channels:
        voice_channels.append({
            'id':          str(ch.id),
            'name':        ch.name,
            'position':    ch.position,
            'bitrate':     ch.bitrate,
            'user_limit':  ch.user_limit,
            'category_id': str(ch.category_id) if ch.category_id else None,
            'overwrites':  _serialize_overwrites(ch.overwrites),
        })

    # ── Emojis ──
    emojis = [{'name': e.name, 'animated': e.animated, 'url': str(e.url)} for e in guild.emojis]

    return {
        'guild_id':          str(guild.id),
        'guild_name':        guild.name,
        'icon_url':          str(guild.icon.url) if guild.icon else None,
        'member_count':      guild.member_count,
        'verification_level': str(guild.verification_level),
        'default_notifications': str(guild.default_notifications),
        'afk_timeout':       guild.afk_timeout,
        'roles':             roles,
        'categories':        categories,
        'text_channels':     text_channels,
        'voice_channels':    voice_channels,
        'emojis':            emojis,
        'created_at':        datetime.datetime.utcnow().isoformat(),
    }


async def _restore_guild(guild: discord.Guild, snapshot: dict, progress_cb=None) -> list:
    """
    Restore a guild from snapshot. Returns list of log messages.
    Skips managed/integrated roles (bots) since they can't be recreated.
    """
    logs = []

    def log(msg):
        logs.append(msg)
        print(f'[Restore] {msg}', flush=True)

    # ── Role ID map: old_id → new_role ──
    role_map = {}

    # ── 1. Restore roles ──
    if progress_cb: await progress_cb('Restoring roles…')
    existing_roles = {r.name: r for r in guild.roles}

    for rdata in sorted(snapshot.get('roles', []), key=lambda r: r['position']):
        if rdata.get('managed'):
            log(f'Skipped managed role @{rdata["name"]}')
            continue
        perms = discord.Permissions(rdata['permissions'])
        color = discord.Color(rdata['color'])
        try:
            if rdata['name'] in existing_roles:
                role = existing_roles[rdata['name']]
                await role.edit(
                    permissions=perms, color=color,
                    hoist=rdata['hoist'], mentionable=rdata['mentionable'],
                    reason='[Backup Restore]'
                )
                log(f'Updated role @{rdata["name"]}')
            else:
                role = await guild.create_role(
                    name=rdata['name'], permissions=perms, color=color,
                    hoist=rdata['hoist'], mentionable=rdata['mentionable'],
                    reason='[Backup Restore]'
                )
                log(f'Created role @{rdata["name"]}')
            role_map[rdata['id']] = role
        except Exception as ex:
            log(f'Failed role @{rdata["name"]}: {ex}')
        await asyncio.sleep(0.3)

    # ── Helper: build overwrites from stored data ──
    def build_overwrites(ow_list):
        overwrites = {}
        for ow in ow_list:
            if ow['type'] == 'role':
                target = role_map.get(ow['id']) or discord.utils.get(guild.roles, id=int(ow['id']))
            else:
                target = guild.get_member(int(ow['id']))
            if not target:
                continue
            allow = discord.Permissions(ow['allow'])
            deny  = discord.Permissions(ow['deny'])
            overwrites[target] = discord.PermissionOverwrite.from_pair(allow, deny)
        return overwrites

    # ── 2. Restore categories ──
    if progress_cb: await progress_cb('Restoring categories…')
    cat_map = {}
    existing_cats = {c.name: c for c in guild.categories}

    for cdata in sorted(snapshot.get('categories', []), key=lambda c: c['position']):
        ow = build_overwrites(cdata.get('overwrites', []))
        try:
            if cdata['name'] in existing_cats:
                cat = existing_cats[cdata['name']]
                await cat.edit(position=cdata['position'], overwrites=ow, reason='[Backup Restore]')
                log(f'Updated category [{cdata["name"]}]')
            else:
                cat = await guild.create_category(
                    name=cdata['name'], position=cdata['position'],
                    overwrites=ow, reason='[Backup Restore]'
                )
                log(f'Created category [{cdata["name"]}]')
            cat_map[cdata['id']] = cat
        except Exception as ex:
            log(f'Failed category [{cdata["name"]}]: {ex}')
        await asyncio.sleep(0.3)

    # ── 3. Restore text channels ──
    if progress_cb: await progress_cb('Restoring text channels…')
    existing_text = {c.name: c for c in guild.text_channels}

    for chdata in sorted(snapshot.get('text_channels', []), key=lambda c: c['position']):
        ow  = build_overwrites(chdata.get('overwrites', []))
        cat = cat_map.get(chdata.get('category_id'))
        try:
            if chdata['name'] in existing_text:
                ch = existing_text[chdata['name']]
                await ch.edit(
                    topic=chdata.get('topic') or None,
                    nsfw=chdata.get('nsfw', False),
                    slowmode_delay=chdata.get('slowmode', 0),
                    category=cat, overwrites=ow,
                    reason='[Backup Restore]'
                )
                log(f'Updated #text {chdata["name"]}')
            else:
                await guild.create_text_channel(
                    name=chdata['name'],
                    topic=chdata.get('topic') or None,
                    nsfw=chdata.get('nsfw', False),
                    slowmode_delay=chdata.get('slowmode', 0),
                    category=cat, overwrites=ow,
                    reason='[Backup Restore]'
                )
                log(f'Created #text {chdata["name"]}')
        except Exception as ex:
            log(f'Failed text channel {chdata["name"]}: {ex}')
        await asyncio.sleep(0.3)

    # ── 4. Restore voice channels ──
    if progress_cb: await progress_cb('Restoring voice channels…')
    existing_voice = {c.name: c for c in guild.voice_channels}

    for chdata in sorted(snapshot.get('voice_channels', []), key=lambda c: c['position']):
        ow  = build_overwrites(chdata.get('overwrites', []))
        cat = cat_map.get(chdata.get('category_id'))
        try:
            if chdata['name'] in existing_voice:
                ch = existing_voice[chdata['name']]
                await ch.edit(
                    bitrate=min(chdata.get('bitrate', 64000), guild.bitrate_limit),
                    user_limit=chdata.get('user_limit', 0),
                    category=cat, overwrites=ow,
                    reason='[Backup Restore]'
                )
                log(f'Updated 🔊 {chdata["name"]}')
            else:
                await guild.create_voice_channel(
                    name=chdata['name'],
                    bitrate=min(chdata.get('bitrate', 64000), guild.bitrate_limit),
                    user_limit=chdata.get('user_limit', 0),
                    category=cat, overwrites=ow,
                    reason='[Backup Restore]'
                )
                log(f'Created 🔊 {chdata["name"]}')
        except Exception as ex:
            log(f'Failed voice channel {chdata["name"]}: {ex}')
        await asyncio.sleep(0.3)

    if progress_cb: await progress_cb('Restore complete ✅')
    return logs


# ══════════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════════

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='backup', invoke_without_command=True)
    @commands.guild_only()
    async def backup(self, ctx):
        """Server backup system — owner only."""
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=mk_embed('❌ Denied', 'Only the server owner can use backups.', 0xFF0000))
        backups = list(get_db().server_backups.find(
            {'guild_id': str(ctx.guild.id)}, {'_id': 0, 'snapshot': 0}
        ).sort('created_at', -1).limit(10))
        if not backups:
            desc = 'No backups yet.\nUse `-backup create` to create one.'
        else:
            desc = '\n'.join(
                f'`{b["backup_id"]}` — {b.get("label","Backup")} — '
                f'{b["created_at"][:10]} ({b.get("role_count",0)} roles, {b.get("channel_count",0)} channels)'
                for b in backups
            )
        e = mk_embed('💾 Server Backups', desc)
        e.set_footer(text='-backup create | -backup restore <id> | -backup delete <id>')
        await ctx.send(embed=e)

    @backup.command(name='create')
    @commands.guild_only()
    async def backup_create(self, ctx, *, label: str = None):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=mk_embed('❌ Denied', 'Only the server owner can create backups.', 0xFF0000))
        msg = await ctx.send(embed=mk_embed('⏳ Creating Backup…', 'Capturing server state…', 0xFFA500))
        try:
            snapshot  = _capture_guild(ctx.guild)
            backup_id = f'{ctx.guild.id}_{int(datetime.datetime.utcnow().timestamp())}'
            doc = {
                'backup_id':     backup_id,
                'guild_id':      str(ctx.guild.id),
                'guild_name':    ctx.guild.name,
                'label':         label or f'Backup {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")}',
                'created_at':    datetime.datetime.utcnow().isoformat(),
                'role_count':    len(snapshot['roles']),
                'channel_count': len(snapshot['text_channels']) + len(snapshot['voice_channels']),
                'emoji_count':   len(snapshot['emojis']),
                'member_count':  snapshot['member_count'],
                'snapshot':      snapshot,
            }
            get_db().server_backups.insert_one(doc)
            await msg.edit(embed=mk_embed(
                '✅ Backup Created',
                f'**ID:** `{backup_id}`\n'
                f'**Roles:** {doc["role_count"]} | **Channels:** {doc["channel_count"]} | **Emojis:** {doc["emoji_count"]}\n\n'
                f'Use `-backup restore {backup_id}` to restore.',
                0x2ECC71
            ))
        except Exception as ex:
            await msg.edit(embed=mk_embed('❌ Backup Failed', str(ex), 0xFF0000))

    @backup.command(name='restore')
    @commands.guild_only()
    async def backup_restore(self, ctx, backup_id: str):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=mk_embed('❌ Denied', 'Only the server owner can restore backups.', 0xFF0000))
        doc = get_db().server_backups.find_one({'backup_id': backup_id, 'guild_id': str(ctx.guild.id)})
        if not doc:
            return await ctx.send(embed=mk_embed('❌ Not Found', f'No backup with ID `{backup_id}`.', 0xFF0000))

        # Confirmation
        conf_embed = mk_embed(
            '⚠️ Confirm Restore',
            f'This will restore **{doc["label"]}** ({doc["created_at"][:10]}) to this server.\n\n'
            f'• Existing roles/channels will be **updated** to match the backup\n'
            f'• Missing roles/channels will be **recreated**\n'
            f'• Nothing will be deleted\n\n'
            f'React ✅ to confirm or ❌ to cancel.',
            0xFFA500
        )
        msg = await ctx.send(embed=conf_embed)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')

        def check(r, u): return u == ctx.author and str(r.emoji) in ('✅','❌') and r.message.id == msg.id
        try:
            reaction, _ = await ctx.bot.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            return await msg.edit(embed=mk_embed('⏰ Timed Out', 'Restore cancelled.', 0xFF0000))

        if str(reaction.emoji) == '❌':
            return await msg.edit(embed=mk_embed('❌ Cancelled', 'Restore cancelled.', 0xFF0000))

        await msg.edit(embed=mk_embed('⏳ Restoring…', 'This may take a minute…', 0xFFA500))

        async def progress(text):
            await msg.edit(embed=mk_embed('⏳ Restoring…', text, 0xFFA500))

        try:
            logs = await _restore_guild(ctx.guild, doc['snapshot'], progress_cb=progress)
            summary = f'Restored **{len(logs)}** items.\n\n' + '\n'.join(f'• {l}' for l in logs[-10:])
            if len(logs) > 10:
                summary += f'\n_…and {len(logs)-10} more_'
            await msg.edit(embed=mk_embed('✅ Restore Complete', summary, 0x2ECC71))
        except Exception as ex:
            await msg.edit(embed=mk_embed('❌ Restore Failed', str(ex), 0xFF0000))

    @backup.command(name='delete')
    @commands.guild_only()
    async def backup_delete(self, ctx, backup_id: str):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=mk_embed('❌ Denied', 'Only the server owner can delete backups.', 0xFF0000))
        res = get_db().server_backups.delete_one({'backup_id': backup_id, 'guild_id': str(ctx.guild.id)})
        if res.deleted_count:
            await ctx.send(embed=mk_embed('🗑️ Deleted', f'Backup `{backup_id}` deleted.', 0x2ECC71))
        else:
            await ctx.send(embed=mk_embed('❌ Not Found', f'No backup with ID `{backup_id}`.', 0xFF0000))

    @backup.error
    async def backup_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=mk_embed('❌ Missing Argument', str(error), 0xFF0000))


async def setup(bot):
    await bot.add_cog(Backup(bot))
