# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import time
import random
from typing import Optional
from cogs.database import load_db, save_db, get_user

COIN = "💵"

class MarryView(discord.ui.View):
    def __init__(self, proposer: discord.Member, target: discord.Member):
        super().__init__(timeout=60.0)
        self.proposer = proposer
        self.target = target
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Lời cầu hôn này không dành cho bạn!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="💖 Đồng Ý Cưới", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            return
        self.finished = True
        for child in self.children:
            child.disabled = True

        data = load_db()
        p = get_user(data, self.proposer.id)
        t = get_user(data, self.target.id)

        now = time.time()
        p["married_to"] = self.target.id
        p["married_date"] = now
        t["married_to"] = self.proposer.id
        t["married_date"] = now

        # Trừ nhẫn cưới của người cầu hôn
        inv = p.get("inventory", {})
        if inv.get("nhan_cuoi", 0) > 0:
            inv["nhan_cuoi"] -= 1

        save_db(data)

        embed = discord.Embed(
            title="💒 LỄ THÀNH HÔN CHÍNH THỨC 💍✨",
            description=f"🎉 Xin chúc mừng đôi tân lang tân nương {self.proposer.mention} và {self.target.mention} đã chính thức về chung một nhà!\n\n"
                        f"💑 Chúc hai bạn trăm năm hạnh phúc, đầu bạc răng long!",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💔 Từ Chối", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            return
        self.finished = True
        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="💔 CẦU HÔN THẤT BẠI",
            description=f"😭 {self.target.mention} đã từ chối lời cầu hôn của {self.proposer.mention}!\n"
                        f"Gió tầng nào gặp mây tầng đó, đừng buồn người anh em!",
            color=discord.Color.dark_grey()
        )
        await interaction.response.edit_message(embed=embed, view=self)


class Marriage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="marry", aliases=["kethon", "cuoi"])
    async def cmd_marry(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot:
            await ctx.send("❌ Đối tượng cầu hôn không hợp lệ!")
            return

        data = load_db()
        p = get_user(data, ctx.author.id)
        t = get_user(data, target.id)

        if p.get("married_to"):
            await ctx.send("❌ Bạn đã kết hôn rồi! Muốn cưới người mới thì hãy ly hôn trước bằng `!divorce`.")
            return
        if t.get("married_to"):
            await ctx.send(f"❌ {target.mention} đã là hoa có chủ rồi!")
            return

        inv = p.get("inventory", {})
        if inv.get("nhan_cuoi", 0) <= 0:
            await ctx.send("❌ Bạn cần sở hữu **Nhẫn Kim Cương 💍** để cầu hôn! Ghé `!shop` để mua với giá 10,000$.")
            return

        embed = discord.Embed(
            title="💍 LỜI CẦU HÔN LÃNG MẠN 💖",
            description=f"{ctx.author.mention} vừa quỳ gối trao nhẫn kim cương cầu hôn {target.mention}!\n\n"
                        f"{target.mention}, bạn có đồng ý làm bạn đời của {ctx.author.display_name} không?",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        view = MarryView(ctx.author, target)
        await ctx.send(content=target.mention, embed=embed, view=view)

    @commands.command(name="divorce", aliases=["lyhon"])
    async def cmd_divorce(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        spouse_id = u.get("married_to")

        if not spouse_id:
            await ctx.send("❌ Bạn đang độc thân, ly hôn với ai?")
            return

        spouse = get_user(data, spouse_id)
        u["married_to"] = None
        u["married_date"] = None
        spouse["married_to"] = None
        spouse["married_date"] = None
        save_db(data)

        await ctx.send(f"💔 {ctx.author.mention} đã chính thức ly hôn với <@{spouse_id}>! Chúc hai bạn tìm được bến đỗ mới.")

    @commands.command(name="profile", aliases=["hoso", "me"])
    async def cmd_profile(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author
        data = load_db()
        u = get_user(data, target.id)

        wallet = u.get("wallet", 0)
        bank = u.get("bank", 0)
        spouse_id = u.get("married_to")
        married_date = u.get("married_date")
        pet = u.get("pet")

        if spouse_id and married_date:
            days = int((time.time() - married_date) // 86400)
            spouse_str = f"💍 Đã kết hôn với <@{spouse_id}> ({days} ngày bên nhau)"
        else:
            spouse_str = "💔 Độc thân vui tính"

        pet_str = f"{pet['name']} {pet['icon']} (Lv.{pet.get('level', 1)})" if pet else "Chưa có"

        embed = discord.Embed(
            title=f"🌸 HỒ SƠ THÀNH VIÊN — {target.display_name}",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💞 Tình Trạng Hôn Nhân:", value=spouse_str, inline=False)
        embed.add_field(name="💵 Tiền Mặt:", value=f"**{wallet:,}** {COIN}", inline=True)
        embed.add_field(name="🏦 Ngân Hàng:", value=f"**{bank:,}** {COIN}", inline=True)
        embed.add_field(name="🐾 Thú Cưng:", value=pet_str, inline=True)
        embed.add_field(name="🔥 Chuỗi Daily:", value=f"**{u.get('streak', 0)} ngày**", inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="ship", aliases=["boitinhduyen"])
    async def cmd_ship(self, ctx, u1: discord.Member, u2: discord.Member):
        percent = random.randint(0, 100)
        bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))

        if percent >= 80:
            status = "💖 Cặp đôi trời sinh! Cưới ngay kẻo lỡ!"
        elif percent >= 50:
            status = "✨ Khá hợp nhau đấy, cùng cố gắng nhé!"
        elif percent >= 20:
            status = "💔 Hơi cấn cấn, thỉnh thoảng sẽ cãi nhau to!"
        else:
            status = "💀 Oan gia ngõ hẹp! Tránh xa nhau ra không toang!"

        embed = discord.Embed(
            title="🔮 BÓI TÌNH DUYÊN / SHIP CẶP ĐÔI 💘",
            description=f"**{u1.display_name}** ❤️ **{u2.display_name}**\n\n"
                        f"📊 **Độ Hợp Nhau: {percent}%**\n"
                        f"`[{bar}]`\n\n"
                        f"💡 **Đánh giá:** {status}",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Marriage(bot))
