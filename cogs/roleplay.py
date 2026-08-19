# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import random

GIFS = {
    "hug": [
        "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
        "https://media.giphy.com/media/l2QDM9Jnim1YV5bxC/giphy.gif",
        "https://media.giphy.com/media/u9BxQbM5bxvwY/giphy.gif"
    ],
    "pat": [
        "https://media.giphy.com/media/5tmRHwTlHAA9WkVxTU/giphy.gif",
        "https://media.giphy.com/media/109ltuoSQT212w/giphy.gif",
        "https://media.giphy.com/media/osYdfUptPqV0s/giphy.gif"
    ],
    "kiss": [
        "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif",
        "https://media.giphy.com/media/bm2O3nXTcKJeU/giphy.gif",
        "https://media.giphy.com/media/FqBTvSNjNzeZG/giphy.gif"
    ],
    "slap": [
        "https://media.giphy.com/media/jLeyZWgtwWP2U/giphy.gif",
        "https://media.giphy.com/media/Zau0yrl15oqdK480Av/giphy.gif",
        "https://media.giphy.com/media/xUO4t2gkWBxDi/giphy.gif"
    ],
    "punch": [
        "https://media.giphy.com/media/arbHBoiCWUgmc/giphy.gif",
        "https://media.giphy.com/media/Dfk5q64stLdRu/giphy.gif",
        "https://media.giphy.com/media/GoN89WuFFqb2U/giphy.gif"
    ]
}

class Roleplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_rp(self, ctx, target: discord.Member, action: str, text: str):
        if target.id == ctx.author.id:
            await ctx.send("❌ Bạn không thể tự làm hành động này với chính mình!")
            return

        gif = random.choice(GIFS.get(action, []))
        embed = discord.Embed(
            description=f"✨ {ctx.author.mention} {text} {target.mention}!",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.command(name="hug", aliases=["om"])
    async def cmd_hug(self, ctx, target: discord.Member):
        await self.send_rp(ctx, target, "hug", "đã ôm thật chặt")

    @commands.command(name="pat", aliases=["xoadau"])
    async def cmd_pat(self, ctx, target: discord.Member):
        await self.send_rp(ctx, target, "pat", "đã xoa đầu cưng nựng")

    @commands.command(name="kiss", aliases=["hon"])
    async def cmd_kiss(self, ctx, target: discord.Member):
        await self.send_rp(ctx, target, "kiss", "đã hôn ngọt ngào lên má")

    @commands.command(name="slap", aliases=["tat"])
    async def cmd_slap(self, ctx, target: discord.Member):
        await self.send_rp(ctx, target, "slap", "đã tát một phát lệch mặt")

    @commands.command(name="punch", aliases=["dam"])
    async def cmd_punch(self, ctx, target: discord.Member):
        await self.send_rp(ctx, target, "punch", "đã tung một cú đấm ngàn cân vào")


async def setup(bot):
    await bot.add_cog(Roleplay(bot))
