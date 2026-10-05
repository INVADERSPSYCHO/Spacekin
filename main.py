import os
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer

# ────────────────────────────────────────────
#  CONFIG
# ────────────────────────────────────────────
TOKEN       = os.getenv("TOKEN")
SERVER_NAME = "SPACEKIN"
SERVER_IP   = "Spacekin.play.hosting"          # apna IP daal
CHANNEL_ID  = 1556704884248674314
ROLE_ID     = 1486650779824689264
REFRESH_SEC = 15

FOOTER        = "psychopathmc"
COLOR_ONLINE  = 0x57F287
COLOR_OFFLINE = 0xED4245

# ────────────────────────────────────────────
#  BOT
# ────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

_state = {"message": None, "was_online": None}


# ────────────────────────────────────────────
#  SERVER QUERY
# ────────────────────────────────────────────
async def query_server():
    try:
        server = JavaServer.lookup(SERVER_IP)
        try:
            s = await asyncio.wait_for(server.async_status(), timeout=6)
            names = [p.name for p in (s.players.sample or [])]
            return {
                "online": True,
                "count":  s.players.online,
                "max":    s.players.max,
                "ping":   round(s.latency),
                "names":  names,
                "source": "direct",
            }
        except Exception:
            ping = await asyncio.wait_for(server.async_ping(), timeout=6)
            return {
                "online": True,
                "count":  0,
                "max":    0,
                "ping":   round(ping),
                "names":  [],
                "source": "ping-only",
            }
    except Exception:
        pass

    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                f"https://api.mcsrvstat.us/2/{SERVER_IP}",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                data = await r.json()

        if data.get("online"):
            p = data.get("players", {})
            return {
                "online": True,
                "count":  p.get("online", 0),
                "max":    p.get("max", 0),
                "ping":   None,
                "names":  p.get("list", []),
                "source": "api",
            }
    except Exception:
        pass

    return {"online": False, "count": 0, "max": 0, "ping": None, "names": [], "source": "none"}


# ────────────────────────────────────────────
#  EMBEDS
# ────────────────────────────────────────────
def status_embed(s):
    online = s["online"]

    embed = discord.Embed(
        title=f"🌲 {SERVER_NAME} • Status",
        color=COLOR_ONLINE if online else COLOR_OFFLINE,
        timestamp=discord.utils.utcnow(),
    )

    if not online:
        embed.description = "🔴 **Server is currently offline**\nTry again in a few minutes."
        embed.set_footer(text=FOOTER)
        return embed

    count_txt = f"`{s['count']}` / `{s['max']}`" if s["max"] else f"`{s['count']}`"
    ping_txt  = f"`{s['ping']} ms`" if s["ping"] is not None else "`—`"

    embed.add_field(name="🟢 Status",  value="```Online```",   inline=True)
    embed.add_field(name="👥 Players", value=count_txt,        inline=True)
    embed.add_field(name="📡 Ping",    value=ping_txt,         inline=True)
    embed.add_field(name="🌐 Address", value=f"```{SERVER_IP}```", inline=False)

    embed.set_footer(text=FOOTER, icon_url=bot.user.display_avatar.url if bot.user else None)
    return embed


def players_embed(s):
    embed = discord.Embed(
        title=f"👥 {SERVER_NAME} • Players",
        color=COLOR_ONLINE if s["online"] else COLOR_OFFLINE,
        timestamp=discord.utils.utcnow(),
    )

    if not s["online"]:
        embed.description = "🔴 **Server is offline**"
        embed.set_footer(text=FOOTER)
        return embed

    count, mx = s["count"], s["max"]
    embed.description = (
        f"🟢 **{count}** player(s) online"
        + (f" • cap `{mx}`" if mx else "")
    )

    names = s["names"]

    if names:
        lines = [f"`{i:>2}.` {n}" for i, n in enumerate(names, 1)]
        body = "\n".join(lines)

        if len(body) > 1020:
            kept, total = [], 0
            for line in lines:
                if total + len(line) + 1 > 1000:
                    break
                kept.append(line)
                total += len(line) + 1
            body = "\n".join(kept) + f"\n*… and {len(names) - len(kept)} more*"

        embed.add_field(name="Online now", value=body, inline=False)
    else:
        embed.add_field(
            name="Online now",
            value="*No players visible — server may hide its list.*",
            inline=False,
        )

    embed.set_footer(text=FOOTER, icon_url=bot.user.display_avatar.url if bot.user else None)
    return embed


# ────────────────────────────────────────────
#  VIEW
# ────────────────────────────────────────────
class RefreshView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.success, emoji="🔄")
    async def _refresh(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        s = await query_server()
        await interaction.message.edit(embed=status_embed(s), view=self)


# ────────────────────────────────────────────
#  COMMANDS
# ────────────────────────────────────────────
@bot.command(name="status", aliases=["s"])
async def cmd_status(ctx):
    async with ctx.typing():
        s = await query_server()
    await ctx.send(embed=status_embed(s), view=RefreshView())


@bot.command(name="players", aliases=["pl", "online"])
async def cmd_players(ctx):
    async with ctx.typing():
        s = await query_server()
    await ctx.send(embed=players_embed(s))


@bot.tree.command(name="status", description="Live SPACEKIN server status")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.defer()
    s = await query_server()
    await interaction.followup.send(embed=status_embed(s), view=RefreshView())


@bot.tree.command(name="players", description="List players online on SPACEKIN")
async def slash_players(interaction: discord.Interaction):
    await interaction.response.defer()
    s = await query_server()
    await interaction.followup.send(embed=players_embed(s))


# ────────────────────────────────────────────
#  AUTO UPDATE
# ────────────────────────────────────────────
@tasks.loop(seconds=REFRESH_SEC)
async def updater():
    ch = bot.get_channel(CHANNEL_ID)
    if not ch:
        return

    s = await query_server()
    online = s["online"]

    prev = _state["was_online"]
    if prev is True and not online:
        try:
            await ch.send(f"<@&{ROLE_ID}> 🔴 **SPACEKIN is down.**")
        except Exception:
            pass
    elif prev is False and online:
        try:
            await ch.send("🟢 **SPACEKIN is back online.**")
        except Exception:
            pass

    _state["was_online"] = online

    msg = _state["message"]
    if msg is None:
        try:
            _state["message"] = await ch.send(embed=status_embed(s), view=RefreshView())
        except Exception:
            pass
    else:
        try:
            await msg.edit(embed=status_embed(s), view=RefreshView())
        except discord.NotFound:
            _state["message"] = None
        except Exception:
            pass


@updater.before_loop
async def _before():
    await bot.wait_until_ready()


# ────────────────────────────────────────────
#  READY
# ────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[+] {bot.user} — {SERVER_NAME} monitor online")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=SERVER_IP)
    )
    try:
        synced = await bot.tree.sync()
        print(f"[+] synced {len(synced)} slash commands")
    except Exception as e:
        print(f"[!] sync failed: {e}")

    if not updater.is_running():
        updater.start()


if not TOKEN:
    raise SystemExit("TOKEN env variable missing")

bot.run(TOKEN)
