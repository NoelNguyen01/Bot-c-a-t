# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from typing import Optional
from cogs.database import load_db, save_db, get_user, calculate_loan_debt

COIN = "💵"


# ================= VIEW TƯƠNG TÁC MENU ẨN NHÀ CÁI !NHACAI =================
class NhaCaiSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⚖️ Chế Độ Mặc Định (8% - 48%)", value="default", description="Tỷ lệ thắng tự động giảm khi cược tiền to", emoji="⚖️"),
            discord.SelectOption(label="🎰 Chế Độ Mồi Chài (60% Win)", value="generous", description="Tỷ lệ thắng cao cho cả server hưng phấn", emoji="🎰"),
            discord.SelectOption(label="💀 Chế Độ Hút Máu (Max 25% Win)", value="hardcore", description="Khó ăn tiền nhà cái, tỷ lệ thua 75%", emoji="💀"),
            discord.SelectOption(label="🩸 Chế Độ Tận Thu (Max 10% Win)", value="drain", description="Gần như 90% người chơi bị nuốt tiền cược", emoji="🩸")
        ]
        super().__init__(placeholder="Chọn Chế Độ Tỷ Lệ Toàn Server...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        data = load_db()
        if "cheat_config" not in data:
            data["cheat_config"] = {"global_mode": "default", "user_overrides": {}}
        data["cheat_config"]["global_mode"] = self.values[0]
        save_db(data)

        mode_names = {
            "default": "⚖️ Mặc định (Tự động theo mức cược 8% - 48%)",
            "generous": "🎰 Mồi chài (60% Win Rate)",
            "hardcore": "💀 Hút máu (Max 25% Win Rate)",
            "drain": "🩸 Tận thu (Max 10% Win Rate)"
        }
        await interaction.response.send_message(f"✅ Đã chuyển tỷ lệ thắng toàn Server sang: **{mode_names[self.values[0]]}**!", ephemeral=True)


class NhaCaiView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120.0)
        self.add_item(NhaCaiSelect())

    @discord.ui.button(label="📋 Xem Danh Sách Can Thiệp", style=discord.ButtonStyle.primary, row=1)
    async def view_rigged(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_db()
        overrides = data.get("cheat_config", {}).get("user_overrides", {})
        if not overrides:
            await interaction.response.send_message("Hiện tại không có thành viên nào bị can thiệp tỷ lệ riêng.", ephemeral=True)
            return

        desc = "**🎯 Danh sách can thiệp riêng từng User:**\n"
        for uid, rate in overrides.items():
            tag = "👑 [HACK THẮNG]" if rate >= 90 else ("💀 [ÉP THUA]" if rate <= 10 else f"[{rate}%]")
            desc += f"• <@{uid}>: **{rate}% Win Rate** {tag}\n"
        await interaction.response.send_message(desc, ephemeral=True)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================= 1. CẨM NANG THÀNH VIÊN THƯỜNG (ẨN HẾT LỆNH ADMIN) =================
    @commands.command(name="help", aliases=["hdsd", "nekohelp"])
    async def cmd_help(self, ctx):
        embed = discord.Embed(
            title="🐱 CẨM NANG HƯỚNG DẪN NEKO BOT 🌸",
            description="Chào mừng bạn đến với **Neko Bot** — Kinh Tế, Vay Vốn Ngân Hàng, Sòng Bạc & Lì Xì Server!\n*Tiền tố lệnh:* `!` hoặc `n!`",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_thumbnail(url="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png")

        embed.add_field(
            name="🪙 1. Kinh Tế & Ngân Hàng & Vay Vốn",
            value="• `!bal` / `!vi` : Xem ví tiền, bank & nợ vay\n"
                  "• `!dep <all/tiền>` : Gửi tiền vào ngân hàng\n"
                  "• `!with <all/tiền>` : Rút tiền ra ví\n"
                  "• `!vay <tiền>` : Vay ngân hàng (Tối đa 30M - 100M, lãi 2%/phút)\n"
                  "• `!trano <all/tiền>` : Trả nợ ngân hàng\n"
                  "• `!topno` : Bảng phong thần Chúa Chổm ngập nợ\n"
                  "• `!daily` : Điểm danh nhận tiền hằng ngày + streak\n"
                  "• `!work` : Đi làm kiếm lương mỗi 30 phút\n"
                  "• `!beg` : Ăn xin tiền lẻ\n"
                  "• `!rob @user` : Trộm ví tiền người khác\n"
                  "• `!pay @user <tiền>` : Chuyển khoản (Phí chiết khấu 20%)\n"
                  "• `!top` : Bảng xếp hạng đại gia",
            inline=False
        )

        embed.add_field(
            name="💸 2. Sổ Đòi Nợ Dân Gian",
            value="• `!doino @user <tiền> <lý do>` : Lập sổ đòi nợ kèm nút bấm đòi tiền\n"
                  "• `!sono` / `!bangno` : Bảng phong thần nợ dai giữa các thành viên",
            inline=False
        )

        embed.add_field(
            name="🎰 3. Sòng Bạc Mini (Casino)",
            value="• `!tx <tiền> <t/x>` : Đổ xúc xắc Tài Xỉu (Bão nhà cái ăn sạch)\n"
                  "• `!bj <tiền>` : Đánh bài Xì Dách Blackjack (Nút bấm 🃏 Rút/Dằn)\n"
                  "• `!cf <tiền> <s/n>` : Tung đồng xu may rủi\n"
                  "• `!slot <tiền>` : Quay hũ máy xèng hoa quả trúng Jackpot\n"
                  "• `!baucua <tiền> <con>` : Bầu cua tôm cá (bau, cua, tom, ca, ga, nai)\n"
                  "*(Tất cả ván thắng cờ bạc chịu 10% thuế nộp Kho Bạc Bot)*",
            inline=False
        )

        embed.add_field(
            name="🧧 4. Đấu Solo PvP & Lì Xì",
            value="• `!rps @user <cược>` : Kéo búa bao solo 1v1\n"
                  "• `!dice @user <cược>` : Đổ xúc xắc solo 1v1\n"
                  "• `!lixi <tiền> <người> [lời chúc]` : Phát bao lì xì cho cả làng giật\n"
                  "• `!lixirieng @user <tiền> [lời chúc]` : Gửi phong bao đỏ riêng cho 1 người\n"
                  "• `!txopen <giây>` : Mở bàn Tài Xỉu cho cả server cùng đặt cược",
            inline=False
        )

        embed.set_footer(text="Neko Bot • Hoạt động 24/7 không giới hạn thành viên!")
        await ctx.send(embed=embed)

    # ================= 2. LỆNH TỔNG HỢP ADMIN DUY NHẤT: !hien =================
    @commands.command(name="hien", aliases=["adminhelp", "secret", "lenhan"])
    @commands.has_permissions(administrator=True)
    async def cmd_hien(self, ctx):
        embed = discord.Embed(
            title="👑 BẢNG TRA CỨU QUYỀN LỰC VIP DÀNH CHO ADMIN 🔒",
            description="Dưới đây là toàn bộ công cụ quản trị, lệnh ẩn cheat và kiểm soát ngân khố của bạn:",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png")

        embed.add_field(
            name="🎲 1. Bảng Điều Khiển Nhà Cái & Hack Tỷ Lệ Thắng",
            value="• `!nhacai` : Mở Menu giao diện điều khiển tỷ lệ thắng toàn server\n"
                  "• `!setwin @user <0-100>` : Ép tỷ lệ thắng của @user (VD: `!setwin @user 100` là Hack Win 100%, `0` là Ép Thua 100%)\n"
                  "• `!resetwin @user` : Xóa can thiệp, trả @user về tỷ lệ bình thường",
            inline=False
        )

        embed.add_field(
            name="🏦 2. Quản Lý Ngân Hàng & Nợ Nần Thành Viên",
            value="• `!setbank @user <tiền>` : Đặt thẳng số dư ngân hàng\n"
                  "• `!addbank @user <tiền>` : Cộng thêm tiền vào ngân hàng\n"
                  "• `!trubank @user <tiền>` : Trừ bớt tiền trong ngân hàng\n"
                  "• `!checkmoney @user` : Soi toàn bộ tài sản (Ví, Bank, Nợ vay, Lãi suất)\n"
                  "• `!xoano_bank @user` : Xóa nợ vay ngân hàng cho thành viên\n"
                  "• `!xoano @user` : Xóa nợ trong sổ đòi nợ dân gian P2P\n"
                  "• `!clear_so_no` : Xóa sạch toàn bộ sổ nợ của Server",
            inline=False
        )

        embed.add_field(
            name="🏛️ 3. Quản Lý Tiền Mặt & Kho Bạc Bot",
            value="• `!khobac` : Xem tổng số tiền thuế bot đã thu thập được\n"
                  "• `!rutkhobac <tiền / all>` : Admin rút tiền từ Kho Bạc Bot về ví để tiêu xài!\n"
                  "• `!admin_lixi <tổng_tiền> <số_người>` : Lấy tiền Kho Bạc phát lì xì cả server\n"
                  "• `!buffme <tiền>` : Bơm tiền mặt vào ví Admin\n"
                  "• `!setmoney @user <tiền>` / `!addmoney` / `!trutien` : Can thiệp ví tiền mặt",
            inline=False
        )

        embed.set_footer(text="Bảo mật tuyệt đối • Chỉ hiển thị cho Admin!")
        await ctx.send(embed=embed)

    # ================= 3. LỆNH ẨN NHÀ CÁI !nhacai =================
    @commands.command(name="nhacai", aliases=["matrix", "godmode"])
    @commands.has_permissions(administrator=True)
    async def cmd_nhacai(self, ctx):
        embed = discord.Embed(
            title="🕵️‍♂️ BẢNG ĐIỀU KHIỂN NHÀ CÁI ẨN 🎰",
            description="Chọn chế độ tỷ lệ thắng toàn Server hoặc kiểm tra danh sách thành viên bị can thiệp:",
            color=discord.Color.dark_purple()
        )
        view = NhaCaiView()
        await ctx.send(embed=embed, view=view)

    @commands.command(name="setwin")
    @commands.has_permissions(administrator=True)
    async def cmd_setwin(self, ctx, target: discord.Member, rate: int):
        rate = max(0, min(rate, 100))
        data = load_db()
        if "cheat_config" not in data:
            data["cheat_config"] = {"global_mode": "default", "user_overrides": {}}
        data["cheat_config"]["user_overrides"][str(target.id)] = rate
        save_db(data)

        tag = "👑 [HACK THẮNG 100%]" if rate == 100 else ("💀 [ÉP THUA 0%]" if rate == 0 else f"[{rate}%]")
        await ctx.send(f"✅ Đã thiết lập tỷ lệ thắng của {target.mention} thành **{rate}%** {tag}!")

    @commands.command(name="resetwin")
    @commands.has_permissions(administrator=True)
    async def cmd_resetwin(self, ctx, target: discord.Member):
        data = load_db()
        overrides = data.get("cheat_config", {}).get("user_overrides", {})
        if str(target.id) in overrides:
            del overrides[str(target.id)]
            save_db(data)
            await ctx.send(f"🔄 Đã xóa can thiệp tỷ lệ của {target.mention}, trả về ngẫu nhiên bình thường!")
        else:
            await ctx.send(f"{target.mention} hiện đang ở tỷ lệ bình thường.")

    # ================= 4. QUẢN LÝ BANK ADMIN =================
    @commands.command(name="setbank")
    @commands.has_permissions(administrator=True)
    async def cmd_setbank(self, ctx, target: discord.Member, amount: int):
        data = load_db()
        u = get_user(data, target.id)
        u["bank"] = max(0, amount)
        save_db(data)
        await ctx.send(f"👑 Đã đặt số dư Ngân Hàng của {target.mention} thành **{amount:,}** {COIN}!")

    @commands.command(name="addbank")
    @commands.has_permissions(administrator=True)
    async def cmd_addbank(self, ctx, target: discord.Member, amount: int):
        data = load_db()
        u = get_user(data, target.id)
        u["bank"] = max(0, u.get("bank", 0) + amount)
        save_db(data)
        await ctx.send(f"✨ Đã cộng **+{amount:,}** {COIN} vào Ngân Hàng của {target.mention}! (Bank: **{u['bank']:,}** {COIN})")

    @commands.command(name="trubank")
    @commands.has_permissions(administrator=True)
    async def cmd_trubank(self, ctx, target: discord.Member, amount: int):
        data = load_db()
        u = get_user(data, target.id)
        u["bank"] = max(0, u.get("bank", 0) - amount)
        save_db(data)
        await ctx.send(f"⚠️ Đã trừ **-{amount:,}** {COIN} trong Ngân Hàng của {target.mention}! (Bank còn: **{u['bank']:,}** {COIN})")

    @commands.command(name="checkmoney", aliases=["soitaikhoan", "checkbal"])
    @commands.has_permissions(administrator=True)
    async def cmd_checkmoney(self, ctx, target: discord.Member):
        data = load_db()
        u = get_user(data, target.id)
        wallet = u.get("wallet", 0)
        bank = u.get("bank", 0)
        tot_debt, princ, inter, overdue = calculate_loan_debt(data, target.id)

        overrides = data.get("cheat_config", {}).get("user_overrides", {})
        user_cheat = overrides.get(str(target.id), "Mặc định")

        embed = discord.Embed(
            title=f"🔍 SOI HỒ SƠ TÀI CHÍNH — {target.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💵 Tiền Mặt (Ví):", value=f"**{wallet:,}** {COIN}", inline=True)
        embed.add_field(name="🏦 Ngân Hàng:", value=f"**{bank:,}** {COIN}", inline=True)
        embed.add_field(name="💰 Tổng Tài Sản:", value=f"**{wallet + bank:,}** {COIN}", inline=False)
        embed.add_field(name="💳 Nợ Ngân Hàng:", value=f"**{tot_debt:,}** {COIN} *(Gốc: {princ:,}, Lãi: {inter:,})*", inline=True)
        embed.add_field(name="🎯 Trạng Thái Can Thiệp:", value=f"**{user_cheat}**", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="xoano_bank")
    @commands.has_permissions(administrator=True)
    async def cmd_xoano_bank(self, ctx, target: discord.Member):
        data = load_db()
        uid = str(target.id)
        if uid in data.get("loans", {}):
            del data["loans"][uid]
            save_db(data)
            await ctx.send(f"✅ Admin đã xóa sạch toàn bộ nợ vay ngân hàng cho {target.mention}!")
        else:
            await ctx.send(f"{target.mention} không có khoản nợ ngân hàng nào.")

    @commands.command(name="xoano")
    @commands.has_permissions(administrator=True)
    async def cmd_xoano(self, ctx, con_no: discord.Member):
        data = load_db()
        debtor_id = str(con_no.id)
        if debtor_id in data.get("debts", {}):
            del data["debts"][debtor_id]
            save_db(data)
            await ctx.send(f"✅ Admin đã xóa toàn bộ nợ dân gian P2P cho {con_no.mention}!")
        else:
            await ctx.send(f"{con_no.mention} không có khoản nợ dân gian nào.")

    @commands.command(name="clear_so_no")
    @commands.has_permissions(administrator=True)
    async def cmd_clear_so_no(self, ctx):
        data = load_db()
        data["debts"] = {}
        save_db(data)
        await ctx.send("🧹 Admin đã xé toàn bộ sổ nợ dân gian của Server!")

    # ================= 5. KHO BẠC THUẾ BOT =================
    @commands.command(name="khobac", aliases=["treasury", "ngankho"])
    @commands.has_permissions(administrator=True)
    async def cmd_khobac(self, ctx):
        data = load_db()
        balance = data.get("treasury", {}).get("balance", 0)
        embed = discord.Embed(
            title="🏛️ KHO BẠC THUẾ NEKO BOT 💰",
            description=f"Tổng số tiền thuế & lãi tích lũy hiện tại:\n\n"
                        f"💎 **{balance:,}** {COIN}\n\n"
                        f"*(Nguồn thu: 10% thuế thắng cược, 5% thuế bank/5h, 20% thuế chuyển tiền, lãi vay ngân hàng)*",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Gõ !rutkhobac <tiền / all> để rút tiền về ví Admin!")
        await ctx.send(embed=embed)

    @commands.command(name="rutkhobac", aliases=["withdraw_treasury"])
    @commands.has_permissions(administrator=True)
    async def cmd_rutkhobac(self, ctx, amount: str):
        data = load_db()
        balance = data.get("treasury", {}).get("balance", 0)

        if amount.lower() == "all":
            withdraw_amt = balance
        else:
            try:
                withdraw_amt = int(amount)
            except ValueError:
                await ctx.send("❌ Nhập số tiền hợp lệ hoặc gõ `!rutkhobac all`!")
                return

        if withdraw_amt <= 0 or withdraw_amt > balance:
            await ctx.send(f"❌ Kho Bạc không đủ tiền! Hiện có: **{balance:,}** {COIN}")
            return

        data["treasury"]["balance"] -= withdraw_amt
        u = get_user(data, ctx.author.id)
        u["wallet"] = u.get("wallet", 0) + withdraw_amt
        save_db(data)

        await ctx.send(f"👑 Admin {ctx.author.mention} đã rút **+{withdraw_amt:,}** {COIN} từ Kho Bạc về ví! (Ví: **{u['wallet']:,}** {COIN})")

    @commands.command(name="buffme")
    @commands.has_permissions(administrator=True)
    async def cmd_buffme(self, ctx, amount: int = 10000000):
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
