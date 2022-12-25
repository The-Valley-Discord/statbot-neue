import json
import re
import sqlite3
import time
import typing
from datetime import timedelta, datetime

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from discord.ext import commands

from .customizations import Bot, Since, paged_send

config = {}
with open("settings.json", "r", encoding="utf-8") as f:
    config = json.load(f)
intents = discord.Intents.all()
bot = Bot(config, command_prefix="sb ", intents=intents, help_command=None)
bot.add_check(
    lambda ctx: ctx.author.guild_permissions.manage_messages
    or ctx.channel.name == "bot-stuff"
)

database = sqlite3.connect(config["database"], isolation_level=None, timeout=10.0)
database.row_factory = sqlite3.Row


def main():
    "the function."
    bot.run(config["token"])


def select(sql: str, params: dict) -> typing.List[sqlite3.Row]:
    "Do a SELECT statement and print it"

    now = time.monotonic()
    rows = database.execute(sql, params).fetchall()
    delta = timedelta(seconds=(time.monotonic() - now))

    print(re.sub(r"\s+", " ", sql), params, delta, sep="\n")
    return rows


@bot.command(name="help")
async def _help(ctx: commands.Context):
    "Print this message."

    def signature(cmd: commands.Command) -> str:
        out = f"`sb {cmd.qualified_name}"
        if cmd.signature:
            out += " " + cmd.signature
        out += "`"
        return out

    output = "__Welcome to Big Sister’s **now-slightly-less-creepy** surveillance interface!__\n"
    output += "Please express time in the format `000[mo/w/d/h/m/s]`, "
    output += "or type `all` to get all-time results.\n\n"
    for command in sorted(bot.walk_commands(), key=lambda c: c.qualified_name):
        output += f"{signature(command)}\n{command.short_doc}\n\n"

    await ctx.send(output)


@bot.event
async def on_ready():
    "say hello"
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    "process message for database and commands"
    if not message.guild or not str(message.guild.id) in bot.config.keys():
        return

    if message.author.bot and not any(
        r.id == bot.config[str(message.guild.id)]["not_a_bot_role"]
        for r in message.author.roles
    ):
        return

    message_data = {
        "message_id": message.id,
        "guild_id": message.guild.id,
        "channel_id": message.channel.id,
        "category_id": message.channel.category_id,
        "thread_id": None,
        "content_length": len(message.content),
        "content_words": 0 if not message.content else len(message.content.split(" ")),
        "content_has_attachments": len(message.attachments) > 0,
        "user_hours_on_server": None,
        "user_demographic": 0,
    }

    if isinstance(message.channel, discord.Thread):
        message_data |= {
            "channel_id": message.channel.parent_id,
            "thread_id": message.channel.id,
        }

    if message.author.joined_at:
        delta = message.created_at - message.author.joined_at
        message_data["user_hours_on_server"] = int(delta.total_seconds() // (60 * 60))

    user_roles = [r.id for r in message.author.roles]
    for i, role in enumerate(bot.config[str(message.guild.id)]["demographics_roles"]):
        if role in user_roles:
            message_data["user_demographic"] += 1 << i

    database.execute(
        """INSERT INTO messages
        (message_id, guild_id, channel_id, category_id, thread_id, content_length, content_words,
        content_has_attachments, user_hours_on_server, user_demographic)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        list(message_data.values()),
    )

    await bot.process_commands(message)


@bot.command()
async def server(ctx: commands.Context, since: Since):
    "How active has the server been?"

    row = select(
        "SELECT count(*) FROM messages WHERE message_id >= :since AND guild_id = :gid",
        {"since": since, "gid": ctx.guild.id},
    )[0]
    await ctx.send(f"{ctx.guild.name}: {row[0]:n} messages")


@bot.command()
async def cat(
    ctx: commands.Context,
    since: Since,
    look_at: typing.Optional[typing.Union[discord.CategoryChannel, str]],
):
    "What are the most active channels in these categories?"

    selector = look_at
    look_at = []
    if not selector:
        look_at = ctx.channel.category.channels
    elif isinstance(selector, discord.CategoryChannel):
        look_at = selector.channels
    elif isinstance(selector, str):
        look_at = [
            channel
            for channel in ctx.guild.channels
            if channel.category and selector in channel.category.name.casefold()
        ]

    look_at = [
        channel
        for channel in look_at
        if channel.permissions_for(ctx.author).read_messages
    ]

    if not look_at:
        ctx.send(f"No channels found for '{selector}'")
        return

    channels = []

    for channel in look_at:
        row = select(
            "SELECT count(*) FROM messages WHERE channel_id=:cid AND message_id >= :since",
            {"cid": channel.id, "since": since},
        )[0]
        channels.append((channel.mention, row[0]))

    reply = ""

    for channel in sorted(channels, key=lambda tup: tup[1], reverse=True):
        reply += f"{channel[0]}: {channel[1]} messages\n"

    await paged_send(ctx, reply)


@bot.command(name="channel")
async def _channel(
    ctx: commands.Context,
    since: Since,
    look_at: commands.Greedy[discord.TextChannel],
):
    "How active have these channels been?"

    channels = []
    reply = ""

    look_at = [
        channel
        for channel in look_at
        if channel.permissions_for(ctx.author).read_messages
    ]

    for channel in look_at:
        row = select(
            "SELECT count(*)FROM messages WHERE channel_id=:cid AND message_id >= :since",
            {"cid": channel.id, "since": since},
        )[0]

        channels.append((channel.name, row[0]))

    for channel in sorted(channels, key=lambda tup: tup[1], reverse=True):
        reply += f"{channel[0]}: {channel[1]} messages\n"

    await paged_send(ctx, reply)


@bot.command()
async def graph(ctx: commands.Context, look_at: commands.Greedy[discord.TextChannel]):
    "How active have these channels been, but as a graph?"

    look_at = [
        channel
        for channel in look_at
        if channel.permissions_for(ctx.author).read_messages
    ]

    for channel in look_at:
        postdates = []
        postcounts = []

        rows = select(
            """SELECT date((message_id >> 22) / 1000 + 1420070400, 'unixepoch') as day,
            count(message_id) as postcount
            FROM messages WHERE channel_id = :cid AND message_id >= :since
            GROUP BY day
            ORDER BY message_id
            """,
            {"cid": channel.id, "since": await Since.convert(ctx, "1 month")},
        )
        for row in rows:
            postdates.append(datetime.strptime(row[0], "%Y-%m-%d").date())
            postcounts.append(row[1])

        print(postdates, postcounts)

        fig, axes = plt.subplots()
        axes.bar(postdates, postcounts)
        axes.set(xlabel="date", ylabel="postcount", title=channel.name)
        locator = mdates.AutoDateLocator(minticks=10, maxticks=30)
        formatter = mdates.ConciseDateFormatter(locator)
        axes.xaxis.set_major_locator(locator)
        axes.xaxis.set_major_formatter(formatter)
        axes.grid(color="b", ls="-.", lw=0.25)
        fig.autofmt_xdate(bottom=0.2, rotation=45, ha="right", which="major")
        fig.savefig("chart.png")
        await ctx.send(file=discord.File("chart.png"))


if __name__ == "__main__":
    main()
