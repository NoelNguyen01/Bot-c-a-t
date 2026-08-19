# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from typing import Optional
from cogs.database import load_db, save_db, get_user

COIN = "💵"

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["hdsd", "nekohelp"])
    async def cmd_help(self, ctx):
        embed = discord.Embed(
            title="🐱 CẨM NANG HƯỚNG DẪN NEKO BOT 🌸",
            description="Chào mừng bạn đến với **Neko Bot** — Hệ thống Kinh Tế, Nuôi Pet, Kết Hôn & Sòng Bạc Mini!\n*Tiền tố lệnh:* `!` hoặc `n!`",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_thumbnail(url="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png")

        embed.add_field(
            name="🪙 1. Kinh Tế & Ngân Hàng",
            value="`!bal` / `!vi` : Xem ví tiền & ngân hàng\n"
                  "`!dep <all/tiền>` : Gửi tiền vào ngân hàng chống cướp\n"
                  "`!with <all/tiền>` : Rút tiền ra ví\n"
                  "`!daily` : Điểm danh nhận tiền hằng ngày + streak\n"
                  "`!work` : Đi làm kiếm lương mỗi 30 phút\n"
                  "`!beg` : Ăn xin tiền lẻ\n"
                  "`!rob @user` : Trộm ví tiền người khác\n"
                  "`!pay @user <tiền>` : Chuyển khoản\n"
                  "`!top` : Bảng xếp hạng đại gia",
            inline=False
        )

        embed.add_field(
            name="🎰 2. Sòng Bạc Mini (Casino)",
            value="`!tx <tiền> <t/x>` : Đổ xúc xắc Tài Xỉu (Bão x3)\n"
                  "`!bj <tiền>` : Đánh bài Xì Dách Blackjack (Nút bấm 🃏 Rút/Dằn)\n"
                  "`!cf <tiền> <s/n>` : Tung đồng xu may rủi\n"
                  "`!slot <tiền>` : Quay hũ máy xèng hoa quả\n"
                  "`!baucua <tiền> <con>` : Bầu cua tôm cá (bau, cua, tom, ca, ga, nai)",
            inline=False
        )

        embed.add_field(
            name="🐾 3. Nuôi Thú Cưng (Pet System)",
            value="`!pet` : Xem thông số thú cưng của bạn\n"
                  "`!pet shop` : Danh sách thú cưng để mua (Mèo, Chó, Rồng, Hamster)\n"
                  "`!pet buy <loại>` : Mua thú cưng\n"
                  "`!pet feed` : Cho thú cưng ăn tăng độ no\n"
                  "`!pet train` : Luyện tập tăng cấp & lực chiến\n"
                  "`!pet fight @user <cược>` : Solo đấu pet cược tiền",
            inline=False
        )

        embed.add_field(
            name="💍 4. Cửa Hàng, Kết Hôn & Roleplay",
            value="`!shop` / `!buy <item>` : Mua nhẫn cưới, khiên bảo vệ 24h, vé số\n"
                  "`!inv` / `!use <item>` : Xem túi đồ balo / sử dụng vật phẩm\n"
                  "`!marry @user` : Cầu hôn bằng nhẫn cưới\n"
                  "`!divorce` : Ly hôn\n"
                  "`!profile` : Thẻ căn cước công dân ảo\n"
                  "`!ship @u1 @u2` : Bói tình duyên độ hợp nhau\n"
                  "`!hug`, `!kiss`, `!slap`, `!pat`, `!punch @user` : Hành động GIF",
            inline=False
        )

        embed.add_field(
            name="👑 5. Lệnh Admin Quản Trị",
            value="`!buffme <tiền>` : Bơm tiền cho chính Admin\n"
                  "`!setmoney @user <tiền>` : Đặt số dư cho ai đó\n"
                  "`!addmoney @user <tiền>` : Thưởng tiền cho ai đó\n"
                  "`!trutien @user <tiền>` : Phạt trừ tiền của ai đó",
            inline=False
        )

        embed.set_footer(text="Neko Bot • Hoạt động 24/7 không giới hạn thành viên!")
        await ctx.send(embed=embed)

    @commands.command(name="buffme")
    @commands.has_permissions(administrator=True)
    async def cmd_buffme(self, ctx, amount: int = 1000000):
        data = load_db()
        u = get_user(data, ctx.author.id)
        u["wallet"] = u.get("wallet", 0) + amount
        save_db(data)
        await ctx.send(f"👑 Admin {ctx.author.mention} đã tự bơm **+{amount:,}** {COIN}! (Ví: **{u['wallet']:,}** {COIN})")

    @commands.command(name="setmoney")
    @commands.has_permissions(administrator=True)
    async def cmd_setmoney(self, ctx, target: discord.Member, amount: int):
        data = load_db()
        u = get_user(data, target.id)
        u["wallet"] = max(0, amount)
        save_db(data)
        await ctx.send(f"👑 Đã đặt số dư ví của {target.mention} thành **{amount:,}** {COIN}!")

    @commands.command(name="addmoney")
    @commands.has_permissions(administrator=True)
    async def cmd_addmoney(self, ctx, target: discord.Member, amount: int):
        data = load_db()
        u = get_user(data, target.id)
        u["wallet"] = max(0, u.get("wallet", 0) + amount)
        save_db(data)
        await ctx.send(f"✨ Đã cộng **+{amount:,}** {COIN} cho {target.mention}! (Ví: **{u['wallet']:,}** {COIN})")

    @commands.command(name="trutien")
    @commands.has_permissions(administrator=True)
    async def cmd_trutien(self, ctx, target: discord.Member, amount: int):
        data = load_db()
        u = get_user(data, target.id)
        u["wallet"] = max(0, u.get("wallet", 0) - amount)
        save_db(data)
        await ctx.send(f"⚠️ Đã trừ **-{amount:,}** {COIN} của {target.mention}! (Ví còn: **{u['wallet']:,}** {COIN})")


async def setup(bot):
    await bot.add_cog(Admin(bot))
