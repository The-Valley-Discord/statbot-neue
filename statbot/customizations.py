import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from typing import Optional

import discord
from discord.ext import commands


async def paged_send(ctx: commands.Context, text: str):
    "Reply and respect discord's length stuff"

    blocks = [""]
    for line in text.split("\n"):
        if len(line) + len(blocks[-1]) < 2000:
            blocks[-1] += "\n" + line
        else:
            blocks.append(line)

    for block in blocks:
        await ctx.send(block)


class Cog(commands.Cog):
    "A Cog with the bot reference attached to it."

    def __init__(self, bot):
        self.bot = bot


class Bot(commands.Bot):
    "A Bot with configuration."

    def __init__(self, config, **kwargs):
        self.config = config

        self.database = sqlite3.connect(config["database"], isolation_level=None)
        self.database.row_factory = sqlite3.Row

        super().__init__(**kwargs)

    @contextmanager
    def configure(self, guild: Optional[discord.Guild] = None):
        """
        This allows you to modify the bot's configuration and write it to disk in one statement:

            with bot.configure() as cfg:
                cfg["token"] = "this is a pretty bad idea"

            with bot.configure(guild=ctx.guild) as cfg:
                cfg["messagemin"] = 4000 # probably a bad idea too
        """

        if guild:
            yield self.config[str(guild.id)]
        else:
            yield self.config

        with open("settings.json", "w", encoding="utf-8") as file:
            json.dump(self.config, file, indent=2)

    async def log(
        self,
        guild: discord.Guild,
        text: str = "",
        ping: bool = False,
        embed: discord.Embed = None,
    ):
        "Send a message to the log channel."
        channel_id = self.config[str(guild.id)]["logs"]["channel"]
        role_id = self.config[str(guild.id)]["logs"]["ping_role"]
        channel = self.get_channel(channel_id)
        if ping:
            text = f"<@&{role_id}> " + text

        await channel.send(text, embed=embed)


class Since(int):
    @classmethod
    async def convert(cls, _ctx: commands.Context, argument: str):
        "convert a string in the form [NNNmo] [NNNw] [NNNd] [NNNh] [NNNm] [NNNs] into a snowflake"

        if argument == "all":
            return 0

        delta = timedelta()

        if monthsm := re.search(r"(\d+) ?mo(nths?)?", argument):
            delta += timedelta(days=int(28 * int(monthsm[1])))

        if weeksm := re.search(r"(\d+) ?w(eeks?)?", argument):
            delta += timedelta(days=int(7 * int(weeksm[1])))

        if daysm := re.search(r"(\d+) ?d(ays?)?", argument):
            delta += timedelta(days=int(daysm[1]))

        if hoursm := re.search(r"(\d+) ?h(ours?)?", argument):
            delta += timedelta(hours=int(hoursm[1]))

        if minsm := re.search(r"(\d+) ?m((inutes?)?|(ins?)?)?", argument):
            delta += timedelta(minutes=int(minsm[1]))

        if secsm := re.search(r"(\d+) ?s((econds?)?|(ecs?)?)?", argument):
            delta += timedelta(seconds=int(secsm[1]))

        return discord.utils.time_snowflake(discord.utils.utcnow() - delta)
