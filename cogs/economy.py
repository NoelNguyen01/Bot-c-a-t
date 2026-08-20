# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user, add_to_treasury, apply_bank_tax, calculate_loan_debt, deduct_loan_debt

COIN = "💵"


# ================= VIEW TƯƠNG TÁC ĐÒI NỢ THÀNH VIÊN P2P =================
class DebtView(discord.ui.View):
    def __init__(self, debtor: discord.Member, creditor: discord.Member, amount: int, reason: str, debt_id: str):
        super().__init__(timeout=None)
        self.debtor = debtor
        self.creditor = creditor
        self.amount = amount
        self.reason = reason
        self.debt_id = debt_id

    def remove_debt(self):
        data = load_db()
        debtor_id = str(self.debtor.id)
        if debtor_id in data.get("debts", {}):
            data["debts"][debtor_id] = [d for d in data["debts"][debtor_id] if d.get("id") != self.debt_id]
            if not data["debts"][debtor_id]:
                del data["debts"][debtor_id]
            save_db(data)

    @discord.ui.button(label="🟢 Tao chuyển khoản rồi", style=discord.ButtonStyle.success)
    async def paid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_admin = interaction.user.guild_permissions.administrator
        if interaction.user.id not in [self.debtor.id, self.creditor.id] and not is_admin:
            await interaction.response.send_message("❌ Mày không có quyền bấm nút này nha con!", ephemeral=True)
            return

        data = load_db()
        u_debtor = get_user(data, self.debtor.id)
        u_creditor = get_user(data, self.creditor.id)

        if u_debtor.get("wallet", 0) < self.amount:
            await interaction.response.send_message(f"❌ {self.debtor.mention} không đủ tiền mặt trong ví để trả **{self.amount:,}** {COIN}!", ephemeral=True)
            return

        u_debtor["wallet"] -= self.amount
        u_creditor["wallet"] = u_creditor.get("wallet", 0) + self.amount
        save_db(data)
        self.remove_debt()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"✅ **ĐÃ TRẢ NỢ THÀNH CÔNG!**\n{self.debtor.mention} đã thanh toán **{self.amount:,}** {COIN} tiền **{self.reason}** cho {self.creditor.mention}.",
            embed=None,
            view=self
        )

    @discord.ui.button(label="🔴 Chưa thấy tiền, đòi tiếp!", style=discord.ButtonStyle.danger)
    async def urge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_admin = interaction.user.guild_permissions.administrator
        if interaction.user.id != self.creditor.id and not is_admin:
            await interaction.response.send_message("❌ Chỉ chủ nợ hoặc Admin mới được đòi tiếp!", ephemeral=True)
            return

        roasts = [
            f"😡 Alo {self.debtor.mention}, mày định quỵt luôn à? Chuyển ngay **{self.amount:,}** {COIN} tiền **{self.reason}** mau!",
            f"⚡ {self.debtor.mention} hiện hồn về trả **{self.amount:,}** {COIN} tiền **{self.reason}** cho bố mày!",
            f"💀 Nợ dai như đỉa đói! {self.debtor.mention} trả **{self.amount:,}** {COIN} tiền **{self.reason}** đi con lợn!"
        ]
        msg = random.choice(roasts)
        try:
            if interaction.channel:
                await interaction.channel.send(msg)
            else:
                await interaction.followup.send(msg)
        except Exception:
            await interaction.followup.send(msg)
        await interaction.response.send_message("📢 Đã chửi và réo tên con nợ thành công!", ephemeral=True)

    @discord.ui.button(label="💀 Xóa nợ vì quá nghèo", style=discord.ButtonStyle.secondary)
    async def forgive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_admin = interaction.user.guild_permissions.administrator
        if interaction.user.id != self.creditor.id and not is_admin:
            await interaction.response.send_message("❌ Chỉ chủ nợ hoặc Admin mới được phép xóa nợ!", ephemeral=True)
            return

        self.remove_debt()
        for child in self.children:
            child.disabled = True

        actor = f"Admin {interaction.user.mention}" if (is_admin and interaction.user.id != self.creditor.id) else self.creditor.mention
        await interaction.response.edit_message(
            content=f"💀 Tội nghiệp {self.debtor.mention} quá nghèo rách mồng tơi, {actor} đã từ bi xóa khoản nợ **{self.amount:,}** {COIN} tiền **{self.reason}**.",
            embed=None,
            view=self
        )


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_bal_embed(self, target: discord.Member):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, target.id)
        wallet = u.get("wallet", 0)
        bank = u.get("bank", 0)
        total = wallet + bank

        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, target.id)

        embed = discord.Embed(
            title=f"👛 Tài Khoản Neko — {target.display_name}",
            color=discord.Color.red() if is_overdue else discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💵 Tiền Mặt (Ví):", value=f"**{wallet:,}** {COIN}", inline=True)
        embed.add_field(name="🏦 Ngân Hàng:", value=f"**{bank:,}** {COIN}", inline=True)
        embed.add_field(name="💰 Tổng Tài Sản:", value=f"**{total:,}** {COIN}", inline=False)

        if total_debt > 0:
            status_tag = "🚨 **[QUÁ HẠN - LÃI PHẠT 4%/P]**" if is_overdue else "⏳ **[ĐANG VAY - LÃI 2%/P]**"
            embed.add_field(
                name="💳 Nợ Vay Ngân Hàng:",
                value=f"{status_tag}\n• Nợ gốc: **{principal:,}** {COIN}\n• Lãi phát sinh: **+{interest:,}** {COIN}\n👉 **TỔNG CẦN TRẢ:** **{total_debt:,}** {COIN}\n*(Gõ `!trano all` hoặc `/trano` để thanh toán)*",
                inline=False
            )

        embed.set_footer(text="Thuế Bank 5% mỗi 5h • Giao dịch chuyển tiền phí 20%")
        return embed

    # ================= 1. XEM VÍ & NGÂN HÀNG =================
    @commands.command(name="bal", aliases=["balance", "vi", "money"])
    async def cmd_bal(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author
        embed = self._get_bal_embed(target)
        await ctx.send(embed=embed)

    @app_commands.command(name="bal", description="Xem số dư ví tiền mặt, ngân hàng và nợ vay")
    async def slash_bal(self, interaction: discord.Interaction, nguoi_dung: Optional[discord.Member] = None):
        target = nguoi_dung or interaction.user
        embed = self._get_bal_embed(target)
        await interaction.response.send_message(embed=embed)

    # ================= 2. GỬI & RÚT NGÂN HÀNG =================
    @commands.command(name="dep", aliases=["deposit"])
    async def cmd_dep(self, ctx, amount: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)
        wallet = u.get("wallet", 0)

        if amount.lower() == "all":
            dep_amt = wallet
        else:
            try:
                dep_amt = int(amount)
            except ValueError:
                await ctx.send("❌ Nhập số tiền hoặc gõ `!dep all`!")
                return

        if dep_amt <= 0 or dep_amt > wallet:
            await ctx.send(f"❌ Số tiền không hợp lệ! Ví hiện có: **{wallet:,}** {COIN}")
            return

        u["wallet"] -= dep_amt
        u["bank"] = u.get("bank", 0) + dep_amt
        save_db(data)
        await ctx.send(f"🏦 Bạn đã gửi **{dep_amt:,}** {COIN} vào Ngân Hàng an toàn! (Ngân hàng: **{u['bank']:,}** {COIN})")

    @app_commands.command(name="dep", description="Gửi tiền vào Ngân Hàng (chống bị cướp)")
    async def slash_dep(self, interaction: discord.Interaction, so_tien: int):
        if so_tien <= 0:
            await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)
        wallet = u.get("wallet", 0)

        if so_tien > wallet:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{wallet:,}** {COIN}", ephemeral=True)
            return

        u["wallet"] -= so_tien
        u["bank"] = u.get("bank", 0) + so_tien
        save_db(data)
        await interaction.response.send_message(f"🏦 Bạn đã gửi **{so_tien:,}** {COIN} vào Ngân Hàng! (Bank: **{u['bank']:,}** {COIN})")

    @commands.command(name="with", aliases=["withdraw"])
    async def cmd_with(self, ctx, amount: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)
        bank = u.get("bank", 0)

        if amount.lower() == "all":
            with_amt = bank
        else:
            try:
                with_amt = int(amount)
            except ValueError:
                await ctx.send("❌ Nhập số tiền hợp lệ!")
                return

        if with_amt <= 0 or with_amt > bank:
            await ctx.send(f"❌ Ngân hàng không đủ tiền! Hiện có: **{bank:,}** {COIN}")
            return

        u["bank"] -= with_amt
        u["wallet"] = u.get("wallet", 0) + with_amt
        save_db(data)
        await ctx.send(f"💵 Bạn đã rút **{with_amt:,}** {COIN} ra ví tiền mặt! (Ví: **{u['wallet']:,}** {COIN})")

    @app_commands.command(name="with", description="Rút tiền từ Ngân Hàng ra ví tiền mặt")
    async def slash_with(self, interaction: discord.Interaction, so_tien: int):
        if so_tien <= 0:
            await interaction.response.send_message("❌ Số tiền phải lớn hơn 0!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)
        bank = u.get("bank", 0)

        if so_tien > bank:
            await interaction.response.send_message(f"❌ Ngân hàng không đủ tiền! Hiện có: **{bank:,}** {COIN}", ephemeral=True)
            return

        u["bank"] -= so_tien
        u["wallet"] = u.get("wallet", 0) + so_tien
        save_db(data)
        await interaction.response.send_message(f"💵 Bạn đã rút **{so_tien:,}** {COIN} ra ví! (Ví: **{u['wallet']:,}** {COIN})")

    # ================= 3. HỆ THỐNG VAY NGÂN HÀNG =================
    @commands.command(name="vay", aliases=["loan", "vaytien"])
    async def cmd_vay(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Số tiền vay phải lớn hơn 0!")
            return

        data = load_db()
        uid = str(ctx.author.id)
        loans = data.get("loans", {})

        if uid in loans and loans[uid].get("principal", 0) > 0:
            total_debt, principal, interest, _ = calculate_loan_debt(data, ctx.author.id)
            await ctx.send(f"❌ Bạn đang có khoản nợ chưa trả (**{total_debt:,}** {COIN})! Vui lòng dùng `!trano` trả hết trước khi vay tiếp.")
            return

        u = get_user(data, ctx.author.id)
        total_assets = u.get("wallet", 0) + u.get("bank", 0)

        if total_assets >= 50000000:
            max_limit = 100000000
            tier_name = "VIP (Tài sản ≥ 50M)"
        else:
            max_limit = 30000000
            tier_name = "Thường (Tài sản < 50M)"

        if amount > max_limit:
            await ctx.send(f"❌ Hạn mức vay của bạn ({tier_name}) tối đa là **{max_limit:,}** {COIN}!")
            return

        u["wallet"] = u.get("wallet", 0) + amount
        if "loans" not in data:
            data["loans"] = {}
        data["loans"][uid] = {
            "principal": amount,
            "timestamp": time.time(),
            "tier": tier_name
        }
        save_db(data)

        embed = discord.Embed(
            title="💳 HỢP ĐỒNG VAY NGÂN HÀNG THÀNH CÔNG! 🏦",
            description=f"🎉 **{ctx.author.mention}** đã vay thành công **+{amount:,}** {COIN}!\n\n"
                        f"• **Hạn mức phân cấp:** {tier_name}\n"
                        f"• **Lãi suất:** `2% mỗi 1 phút` (Tính lãi kép theo phút)\n"
                        f"• **Thời hạn vay gốc:** `30 Phút`\n"
                        f"• **Quá hạn:** Tự động gia hạn thêm 18 phút (60%) với `lãi phạt 4%/phút`\n"
                        f"• **Trần nợ tối đa:** 300% gốc ({amount * 3:,} {COIN})\n\n"
                        f"💰 Tiền đã cộng vào ví! Gõ `!trano all` khi có tiền để thanh toán nợ.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="vay", description="Vay vốn Ngân Hàng (Lãi suất 2%/phút, hạn mức 30M - 100M)")
    async def slash_vay(self, interaction: discord.Interaction, so_tien: int):
        if so_tien <= 0:
            await interaction.response.send_message("❌ Số tiền vay phải lớn hơn 0!", ephemeral=True)
            return

        data = load_db()
        uid = str(interaction.user.id)
        loans = data.get("loans", {})

        if uid in loans and loans[uid].get("principal", 0) > 0:
            total_debt, _, _, _ = calculate_loan_debt(data, interaction.user.id)
            await interaction.response.send_message(f"❌ Bạn đang có nợ chưa trả (**{total_debt:,}** {COIN})! Hãy dùng `/trano` trước.", ephemeral=True)
            return

        u = get_user(data, interaction.user.id)
        total_assets = u.get("wallet", 0) + u.get("bank", 0)

        if total_assets >= 50000000:
            max_limit = 100000000
            tier_name = "VIP (Tài sản ≥ 50M)"
        else:
            max_limit = 30000000
            tier_name = "Thường (Tài sản < 50M)"

        if so_tien > max_limit:
            await interaction.response.send_message(f"❌ Hạn mức vay của bạn ({tier_name}) tối đa là **{max_limit:,}** {COIN}!", ephemeral=True)
            return

        u["wallet"] = u.get("wallet", 0) + so_tien
        if "loans" not in data:
            data["loans"] = {}
        data["loans"][uid] = {
            "principal": so_tien,
            "timestamp": time.time(),
            "tier": tier_name
        }
        save_db(data)

        embed = discord.Embed(
            title="💳 HỢP ĐỒNG VAY NGÂN HÀNG THÀNH CÔNG! 🏦",
            description=f"🎉 **{interaction.user.mention}** đã vay thành công **+{so_tien:,}** {COIN}!\n\n"
                        f"• **Hạn mức:** {tier_name}\n"
                        f"• **Lãi suất:** `2% mỗi 1 phút`\n"
                        f"• **Thời hạn:** `30 Phút` (Quá hạn phạt 4%/phút)\n\n"
                        f"💰 Tiền đã cộng vào ví! Gõ `/trano` để thanh toán nợ.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name="trano", aliases=["payloan", "traloi"])
    async def cmd_trano(self, ctx, amount: str = "all"):
        data = load_db()
        uid = str(ctx.author.id)
        loans = data.get("loans", {})

        if uid not in loans or loans[uid].get("principal", 0) <= 0:
            await ctx.send("🎉 Bạn không có khoản nợ ngân hàng nào cần trả!")
            return

        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, ctx.author.id)
        u = get_user(data, ctx.author.id)
        wallet = u.get("wallet", 0)

        if amount.lower() == "all":
            pay_amt = total_debt
        else:
            try:
                pay_amt = int(amount)
            except ValueError:
                await ctx.send("❌ Nhập số tiền hoặc gõ `!trano all`!")
                return

        if pay_amt <= 0:
            await ctx.send("❌ Số tiền trả phải lớn hơn 0!")
            return

        if wallet < pay_amt:
            await ctx.send(f"❌ Ví không đủ tiền! Cần **{pay_amt:,}** {COIN} (Ví hiện có: **{wallet:,}** {COIN})")
            return

        if pay_amt >= total_debt:
            actual_paid = total_debt
            u["wallet"] -= actual_paid
            add_to_treasury(data, interest)
            del data["loans"][uid]
            save_db(data)
            await ctx.send(f"🎉 **CHÚC MỪNG BẠN ĐÃ TRẢ SẠCH NỢ!** Đã thanh toán **{actual_paid:,}** {COIN} (Gốc: {principal:,} + Lãi: {interest:,})!")
        else:
            u["wallet"] -= pay_amt
            new_debt = total_debt - pay_amt
            data["loans"][uid]["principal"] = new_debt
            data["loans"][uid]["timestamp"] = time.time()
            save_db(data)
            await ctx.send(f"✅ Đã trả bớt **{pay_amt:,}** {COIN}! Số nợ còn lại: **{new_debt:,}** {COIN}.")

    @app_commands.command(name="trano", description="Trả nợ ngân hàng (gốc + lãi)")
    async def slash_trano(self, interaction: discord.Interaction, so_tien: Optional[int] = None):
        data = load_db()
        uid = str(interaction.user.id)
        loans = data.get("loans", {})

        if uid not in loans or loans[uid].get("principal", 0) <= 0:
            await interaction.response.send_message("🎉 Bạn không có khoản nợ ngân hàng nào cần trả!", ephemeral=True)
            return

        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
        u = get_user(data, interaction.user.id)
        wallet = u.get("wallet", 0)

        pay_amt = total_debt if so_tien is None else so_tien

        if pay_amt <= 0:
            await interaction.response.send_message("❌ Số tiền trả phải lớn hơn 0!", ephemeral=True)
            return

        if wallet < pay_amt:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Cần **{pay_amt:,}** {COIN} (Ví hiện có: **{wallet:,}** {COIN})", ephemeral=True)
            return

        if pay_amt >= total_debt:
            actual_paid = total_debt
            u["wallet"] -= actual_paid
            add_to_treasury(data, interest)
            del data["loans"][uid]
            save_db(data)
            await interaction.response.send_message(f"🎉 **BẠN ĐÃ TRẢ SẠCH NỢ!** Đã thanh toán **{actual_paid:,}** {COIN} (Gốc: {principal:,} + Lãi: {interest:,})!")
        else:
            u["wallet"] -= pay_amt
            new_debt = total_debt - pay_amt
            data["loans"][uid]["principal"] = new_debt
            data["loans"][uid]["timestamp"] = time.time()
            save_db(data)
            await interaction.response.send_message(f"✅ Đã trả bớt **{pay_amt:,}** {COIN}! Số nợ còn lại: **{new_debt:,}** {COIN}.")

    @commands.command(name="topno", aliases=["banno", "chuachom"])
    async def cmd_topno(self, ctx):
        data = load_db()
        loans = data.get("loans", {})
        if not loans:
            await ctx.send("🎉 Hiện tại server sạch bóng quân nợ ngân hàng!")
            return

        debt_list = []
        for uid in loans:
            tot, princ, inter, overdue = calculate_loan_debt(data, uid)
            if tot > 0:
                debt_list.append((uid, tot, princ, inter, overdue))

        debt_list.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="💀 BẢNG PHONG THẦN CHÚA CHỔM (TOP NỢ NGÂN HÀNG) 🏦",
            description="Vinh danh những gương mặt vàng trong làng ngập nợ ngân hàng:\n",
            color=discord.Color.dark_red()
        )
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        desc = ""
        for i, (uid, tot, princ, inter, overdue) in enumerate(debt_list[:10]):
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            tag = " 🚨 **[QUÁ HẠN]**" if overdue else ""
            desc += f"{medal} <@{uid}> — **{tot:,}** {COIN} *(Gốc: {princ:,} + Lãi: {inter:,})*{tag}\n"

        embed.description = desc
        embed.set_footer(text="Lãi suất 2%/phút • Quá hạn 30p phạt 4%/phút • Gõ !trano all để trả nợ!")
        await ctx.send(embed=embed)

    @app_commands.command(name="topno", description="Xem Bảng Phong Thần Top 10 con nợ ngân hàng")
    async def slash_topno(self, interaction: discord.Interaction):
        data = load_db()
        loans = data.get("loans", {})
        if not loans:
            await interaction.response.send_message("🎉 Hiện tại server sạch bóng quân nợ ngân hàng!")
            return

        debt_list = []
        for uid in loans:
            tot, princ, inter, overdue = calculate_loan_debt(data, uid)
            if tot > 0:
                debt_list.append((uid, tot, princ, inter, overdue))

        debt_list.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="💀 BẢNG PHONG THẦN CHÚA CHỔM (TOP NỢ NGÂN HÀNG) 🏦",
            color=discord.Color.dark_red()
        )
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        desc = ""
        for i, (uid, tot, princ, inter, overdue) in enumerate(debt_list[:10]):
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            tag = " 🚨 **[QUÁ HẠN]**" if overdue else ""
            desc += f"{medal} <@{uid}> — **{tot:,}** {COIN} *(Gốc: {princ:,} + Lãi: {inter:,})*{tag}\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

    # ================= 4. SỔ ĐÒI NỢ THÀNH VIÊN P2P =================
    @commands.command(name="doino", aliases=["doi"])
    async def cmd_doino(self, ctx, con_no: discord.Member, so_tien: int, *, ly_do: str = "Không lý do"):
        if con_no.id == ctx.author.id or con_no.bot:
            await ctx.send("❌ Bị khùng hả mà tự đòi nợ mình / đòi nợ bot?")
            return
        if so_tien <= 0:
            await ctx.send("❌ Số tiền đòi nợ phải lớn hơn 0!")
            return

        debt_id = str(time.time())
        data = load_db()
        if "debts" not in data:
            data["debts"] = {}

        debtor_id = str(con_no.id)
        if debtor_id not in data["debts"]:
            data["debts"][debtor_id] = []

        data["debts"][debtor_id].append({
            "id": debt_id,
            "creditor_id": ctx.author.id,
            "amount": so_tien,
            "reason": ly_do,
            "timestamp": time.time()
        })
        save_db(data)

        embed = discord.Embed(
            title="⚠️ CẢNH BÁO ĐÒI NỢ DÂN GIAN ⚠️",
            description=f"Alo {con_no.mention}, mày nợ **{ctx.author.mention}** số tiền **{so_tien:,}** {COIN} tiền **{ly_do}** bao lâu rồi? Mau trả tiền không bố đấm cho không trượt phát nào!",
            color=discord.Color.red()
        )
        embed.add_field(name="Chủ nợ", value=ctx.author.mention, inline=True)
        embed.add_field(name="Số tiền", value=f"**{so_tien:,}** {COIN}", inline=True)
        embed.add_field(name="Lý do", value=ly_do, inline=False)

        view = DebtView(debtor=con_no, creditor=ctx.author, amount=so_tien, reason=ly_do, debt_id=debt_id)
        await ctx.send(content=con_no.mention, embed=embed, view=view)

    @app_commands.command(name="doino", description="Lập sổ đòi nợ thành viên khác kèm 3 nút bấm tương tác")
    async def slash_doino(self, interaction: discord.Interaction, con_no: discord.Member, so_tien: int, ly_do: str = "Không lý do"):
        if con_no.id == interaction.user.id or con_no.bot:
            await interaction.response.send_message("❌ Không thể tự đòi nợ mình / đòi nợ bot!", ephemeral=True)
            return
        if so_tien <= 0:
            await interaction.response.send_message("❌ Số tiền đòi nợ phải lớn hơn 0!", ephemeral=True)
            return

        debt_id = str(time.time())
        data = load_db()
        if "debts" not in data:
            data["debts"] = {}

        debtor_id = str(con_no.id)
        if debtor_id not in data["debts"]:
            data["debts"][debtor_id] = []

        data["debts"][debtor_id].append({
            "id": debt_id,
            "creditor_id": interaction.user.id,
            "amount": so_tien,
            "reason": ly_do,
            "timestamp": time.time()
        })
        save_db(data)

        embed = discord.Embed(
            title="⚠️ CẢNH BÁO ĐÒI NỢ DÂN GIAN ⚠️",
            description=f"Alo {con_no.mention}, mày nợ **{interaction.user.mention}** số tiền **{so_tien:,}** {COIN} tiền **{ly_do}** bao lâu rồi? Mau trả tiền đi!",
            color=discord.Color.red()
        )
        embed.add_field(name="Chủ nợ", value=interaction.user.mention, inline=True)
        embed.add_field(name="Số tiền", value=f"**{so_tien:,}** {COIN}", inline=True)
        embed.add_field(name="Lý do", value=ly_do, inline=False)

        view = DebtView(debtor=con_no, creditor=interaction.user, amount=so_tien, reason=ly_do, debt_id=debt_id)
        await interaction.response.send_message(content=con_no.mention, embed=embed, view=view)

    @commands.command(name="sono", aliases=["bangno", "danhsachno"])
    async def cmd_sono(self, ctx):
        data = load_db()
        debts = data.get("debts", {})
        if not debts:
            await ctx.send("🎉 Hiện tại server thái bình, không ai nợ tiền ai!")
            return

        leaderboard = []
        for debtor_id, debt_list in debts.items():
            total = sum(d.get("amount", 0) for d in debt_list)
            if total > 0:
                leaderboard.append((debtor_id, total, len(debt_list)))

        leaderboard.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="🏆 BẢNG PHONG THẦN NỢ DAI MẶT DÀY P2P 💸",
            description="Danh sách những con nợ bị réo tên đòi tiền nhiều nhất:\n",
            color=discord.Color.gold()
        )
        desc = ""
        for i, (debtor_id, total, count) in enumerate(leaderboard[:10], 1):
            desc += f"**#{i}** <@{debtor_id}> — Tổng nợ: **{total:,}** {COIN} *({count} khoản nợ)*\n"

        embed.description = desc
        embed.set_footer(text="Dùng !doino @user <tiền> <lý do> để lập sổ đòi nợ!")
        await ctx.send(embed=embed)

    @app_commands.command(name="sono", description="Xem Bảng Phong Thần Nợ Dai giữa các thành viên")
    async def slash_sono(self, interaction: discord.Interaction):
        data = load_db()
        debts = data.get("debts", {})
        if not debts:
            await interaction.response.send_message("🎉 Hiện tại server thái bình, không ai nợ tiền ai!")
            return

        leaderboard = []
        for debtor_id, debt_list in debts.items():
            total = sum(d.get("amount", 0) for d in debt_list)
            if total > 0:
                leaderboard.append((debtor_id, total, len(debt_list)))

        leaderboard.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="🏆 BẢNG PHONG THẦN NỢ DAI MẶT DÀY P2P 💸",
            color=discord.Color.gold()
        )
        desc = ""
        for i, (debtor_id, total, count) in enumerate(leaderboard[:10], 1):
            desc += f"**#{i}** <@{debtor_id}> — Tổng nợ: **{total:,}** {COIN} *({count} khoản nợ)*\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

    # ================= 5. ĐIỂM DANH DAILY =================
    @commands.command(name="daily", aliases=["diemdanh"])
    async def cmd_daily(self, ctx):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_daily", 0)
        streak = u.get("streak", 0)

        diff = now - last
        if diff < 86400:
            rem = int(86400 - diff)
            h = rem // 3600
            m = (rem % 3600) // 60
            await ctx.send(f"⏳ Bạn đã điểm danh hôm nay rồi! Quay lại sau **{h}h {m}p** nữa nhé.")
            return

        streak = streak + 1 if diff < 172800 else 1
        base = random.randint(500, 1000)
        bonus = min(streak * 50, 500)
        earned = base + bonus

        # 🚨 CƠ CHẾ XIẾT NỢ TỰ ĐỘNG (50%)
        debt_msg = ""
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, ctx.author.id)
        if total_debt > 0:
            seize = int(earned * 0.5)
            paid, rem_debt, cleared = deduct_loan_debt(data, ctx.author.id, seize)
            earned -= paid
            if cleared:
                debt_msg = f"\n💸 **CƯỠNG CHẾ XIẾT NỢ (50%):** Thu **-{paid:,}** {COIN}!\n🎉 **BẠN ĐÃ TRẢ HẾT SẠCH NỢ NGÂN HÀNG!**"
            else:
                debt_msg = f"\n💸 **CƯỠNG CHẾ XIẾT NỢ (50%):** Thu **-{paid:,}** {COIN} để trả nợ! (Nợ còn: **{rem_debt:,}** {COIN})"

        u["last_daily"] = now
        u["streak"] = streak
        u["wallet"] = u.get("wallet", 0) + earned
        save_db(data)

        embed = discord.Embed(
            title="🎁 PHẦN THƯỞNG ĐIỂM DANH HẰNG NGÀY",
            description=f"🎉 Thực nhận vào ví: **+{earned:,}** {COIN}!\n"
                        f"• Thưởng gốc: **{base:,}** {COIN}\n"
                        f"• Thưởng chuỗi (Streak {streak} ngày): **+{bonus:,}** {COIN}{debt_msg}\n"
                        f"• Số dư ví: **{u['wallet']:,}** {COIN}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="daily", description="Điểm danh nhận tiền mỗi ngày + chuỗi streak")
    async def slash_daily(self, interaction: discord.Interaction):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)
        now = time.time()
        last = u.get("last_daily", 0)
        streak = u.get("streak", 0)

        diff = now - last
        if diff < 86400:
            rem = int(86400 - diff)
            h = rem // 3600
            m = (rem % 3600) // 60
            await interaction.response.send_message(f"⏳ Bạn đã điểm danh hôm nay rồi! Quay lại sau **{h}h {m}p** nữa nhé.", ephemeral=True)
            return

        streak = streak + 1 if diff < 172800 else 1
        base = random.randint(500, 1000)
        bonus = min(streak * 50, 500)
        earned = base + bonus

        # 🚨 CƠ CHẾ XIẾT NỢ TỰ ĐỘNG (50%)
        debt_msg = ""
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
        if total_debt > 0:
            seize = int(earned * 0.5)
            paid, rem_debt, cleared = deduct_loan_debt(data, interaction.user.id, seize)
            earned -= paid
            if cleared:
                debt_msg = f"\n💸 **CƯỠNG CHẾ XIẾT NỢ (50%):** Thu **-{paid:,}** {COIN}!\n🎉 **BẠN ĐÃ TRẢ HẾT SẠCH NỢ NGÂN HÀNG!**"
            else:
                debt_msg = f"\n💸 **CƯỠNG CHẾ XIẾT NỢ (50%):** Thu **-{paid:,}** {COIN} để trả nợ! (Nợ còn: **{rem_debt:,}** {COIN})"

        u["last_daily"] = now
        u["streak"] = streak
        u["wallet"] = u.get("wallet", 0) + earned
        save_db(data)

        embed = discord.Embed(
            title="🎁 PHẦN THƯỞNG ĐIỂM DANH HẰNG NGÀY",
            description=f"🎉 Thực nhận vào ví: **+{earned:,}** {COIN}!\n"
                        f"• Thưởng gốc: **{base:,}** {COIN}\n"
                        f"• Thưởng chuỗi (Streak {streak} ngày): **+{bonus:,}** {COIN}{debt_msg}\n"
                        f"• Số dư ví: **{u['wallet']:,}** {COIN}",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

    # ================= 6. ĐI LÀM WORK =================
    @commands.command(name="work", aliases=["lam"])
    async def cmd_work(self, ctx):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_work", 0)

        if now - last < 1800:
            rem = int(1800 - (now - last))
            await ctx.send(f"😴 Bạn vừa làm việc mệt rồi, nghỉ ngơi **{rem // 60}p {rem % 60}s** nữa nhé!")
            return

        jobs = [
            ("Lập trình bot Discord", random.randint(300, 600)),
            ("Phục vụ quán Cà Phê Mèo Neko", random.randint(250, 500)),
            ("Giao đồ ăn nhanh buổi tối", random.randint(200, 450)),
            ("Bán trà sữa trân châu đường đen", random.randint(220, 480)),
            ("Chăm sóc thú cưng", random.randint(250, 450))
        ]
        job, wage = random.choice(jobs)

        # 🚨 CƠ CHẾ XIẾT NỢ TỰ ĐỘNG (50%)
        debt_msg = ""
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, ctx.author.id)
        if total_debt > 0:
            seize = int(wage * 0.5)
            paid, rem_debt, cleared = deduct_loan_debt(data, ctx.author.id, seize)
            wage -= paid
            if cleared:
                debt_msg = f" *(Ngân hàng đã trích thu -{paid:,} {COIN} để tất toán hết nợ!)*"
            else:
                debt_msg = f" *(Đã trích thu -{paid:,} {COIN} trừ nợ, nợ còn: {rem_debt:,} {COIN})*"

        u["last_work"] = now
        u["wallet"] = u.get("wallet", 0) + wage
        save_db(data)
        await ctx.send(f"💼 Bạn vừa làm **{job}** và nhận được **+{wage:,}** {COIN}!{debt_msg} (Ví: **{u['wallet']:,}** {COIN})")

    @app_commands.command(name="work", description="Đi làm việc kiếm lương mỗi 30 phút")
    async def slash_work(self, interaction: discord.Interaction):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)
        now = time.time()
        last = u.get("last_work", 0)

        if now - last < 1800:
            rem = int(1800 - (now - last))
            await interaction.response.send_message(f"😴 Bạn vừa làm việc mệt rồi, nghỉ ngơi **{rem // 60}p {rem % 60}s** nữa nhé!", ephemeral=True)
            return

        jobs = [
            ("Lập trình bot Discord", random.randint(300, 600)),
            ("Phục vụ quán Cà Phê Mèo Neko", random.randint(250, 500)),
            ("Giao đồ ăn nhanh buổi tối", random.randint(200, 450)),
            ("Bán trà sữa trân châu đường đen", random.randint(220, 480))
        ]
        job, wage = random.choice(jobs)

        # 🚨 CƠ CHẾ XIẾT NỢ TỰ ĐỘNG (50%)
        debt_msg = ""
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
        if total_debt > 0:
            seize = int(wage * 0.5)
            paid, rem_debt, cleared = deduct_loan_debt(data, interaction.user.id, seize)
            wage -= paid
            if cleared:
                debt_msg = f" *(Ngân hàng đã trích thu -{paid:,} {COIN} để tất toán hết nợ!)*"
            else:
                debt_msg = f" *(Đã trích thu -{paid:,} {COIN} trừ nợ, nợ còn: {rem_debt:,} {COIN})*"

        u["last_work"] = now
        u["wallet"] = u.get("wallet", 0) + wage
        save_db(data)
        await interaction.response.send_message(f"💼 Bạn vừa làm **{job}** và nhận được **+{wage:,}** {COIN}!{debt_msg} (Ví: **{u['wallet']:,}** {COIN})")

    # ================= 7. ĂN XIN BEG =================
    @commands.command(name="beg", aliases=["anxin"])
    async def cmd_beg(self, ctx):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_beg", 0)

        if now - last < 600:
            rem = int(600 - (now - last))
            await ctx.send(f"⏳ Vừa xin xong mỏi mồm chưa? Đợi **{rem // 60}p {rem % 60}s** nữa nhé!")
            return

        u["last_beg"] = now
        if random.random() < 0.75:
            amt = random.randint(50, 200)
            
            debt_msg = ""
            total_debt, principal, interest, is_overdue = calculate_loan_debt(data, ctx.author.id)
            if total_debt > 0:
                seize = int(amt * 0.5)
                paid, rem_debt, cleared = deduct_loan_debt(data, ctx.author.id, seize)
                amt -= paid
                debt_msg = f" *(Ngân hàng xiết nợ -{paid:,} {COIN})*"

            u["wallet"] = u.get("wallet", 0) + amt
            save_db(data)
            await ctx.send(f"🥺 Bạn được người tốt bố thí cho **+{amt:,}** {COIN}!{debt_msg} (Ví: **{u['wallet']:,}** {COIN})")
        else:
            await ctx.send("💀 Bạn chìa nón ra nhưng bị bảo vệ đuổi chạy té khói!")

    @app_commands.command(name="beg", description="Vác nón đi ăn xin tiền lẻ mỗi 10 phút")
    async def slash_beg(self, interaction: discord.Interaction):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)
        now = time.time()
        last = u.get("last_beg", 0)

        if now - last < 600:
            rem = int(600 - (now - last))
            await interaction.response.send_message(f"⏳ Vừa xin xong mỏi mồm chưa? Đợi **{rem // 60}p {rem % 60}s** nữa nhé!", ephemeral=True)
            return

        u["last_beg"] = now
        if random.random() < 0.75:
            amt = random.randint(50, 200)

            debt_msg = ""
            total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
            if total_debt > 0:
                seize = int(amt * 0.5)
                paid, rem_debt, cleared = deduct_loan_debt(data, interaction.user.id, seize)
                amt -= paid
                debt_msg = f" *(Ngân hàng xiết nợ -{paid:,} {COIN})*"

            u["wallet"] = u.get("wallet", 0) + amt
            save_db(data)
            await interaction.response.send_message(f"🥺 Bạn được người tốt bố thí cho **+{amt:,}** {COIN}!{debt_msg} (Ví: **{u['wallet']:,}** {COIN})")
        else:
            await interaction.response.send_message("💀 Bạn chìa nón ra nhưng bị bảo vệ đuổi chạy té khói!")

    # ================= 8. CƯỚP TIỀN ROB =================
    @commands.command(name="rob", aliases=["cuop"])
    async def cmd_rob(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot:
            await ctx.send("❌ Đối tượng cướp không hợp lệ!")
            return

        data = load_db()
        apply_bank_tax(data)
        robber = get_user(data, ctx.author.id)
        victim = get_user(data, target.id)
        now = time.time()

        if now - robber.get("last_rob", 0) < 3600:
            rem = int(3600 - (now - robber.get("last_rob", 0)))
            await ctx.send(f"🚔 Cảnh sát đang tuần tra, đợi **{rem // 60} phút** nữa nhé!")
            return

        v_wallet = victim.get("wallet", 0)
        r_wallet = robber.get("wallet", 0)

        if r_wallet < 500:
            await ctx.send("❌ Bạn cần ít nhất **500** tiền trong ví để nộp phạt nếu bị bắt!")
            return
        if v_wallet < 500:
            await ctx.send(f"❌ Ví của {target.mention} quá nghèo (dưới 500 tiền), tha cho nó đi!")
            return

        robber["last_rob"] = now
        if random.random() < 0.5:
            stolen = max(100, int(v_wallet * random.uniform(0.15, 0.35)))
            victim["wallet"] -= stolen
            robber["wallet"] += stolen
            save_db(data)
            await ctx.send(f"🥷 Thành công! Bạn vừa móc trộm được **+{stolen:,}** {COIN} từ ví của {target.mention}!")
        else:
            fine = min(r_wallet, random.randint(300, 600))
            robber["wallet"] -= fine
            victim["wallet"] += fine
            save_db(data)
            await ctx.send(f"🚨 Bị bắt quả tang tại trận! Bạn bị đền **-{fine:,}** {COIN} cho {target.mention}!")

    @app_commands.command(name="rob", description="Móc túi trộm tiền từ ví của người khác")
    async def slash_rob(self, interaction: discord.Interaction, nan_nhan: discord.Member):
        if nan_nhan.id == interaction.user.id or nan_nhan.bot:
            await interaction.response.send_message("❌ Không thể tự cướp mình / cướp bot!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        robber = get_user(data, interaction.user.id)
        victim = get_user(data, nan_nhan.id)
        now = time.time()

        if now - robber.get("last_rob", 0) < 3600:
            rem = int(3600 - (now - robber.get("last_rob", 0)))
            await interaction.response.send_message(f"🚔 Cảnh sát đang tuần tra, đợi **{rem // 60} phút** nữa nhé!", ephemeral=True)
            return

        v_wallet = victim.get("wallet", 0)
        r_wallet = robber.get("wallet", 0)

        if r_wallet < 500:
            await interaction.response.send_message("❌ Bạn cần ít nhất **500** tiền trong ví để nộp phạt!", ephemeral=True)
            return
        if v_wallet < 500:
            await interaction.response.send_message(f"❌ Ví của {nan_nhan.mention} dưới 500 tiền, tha cho nó đi!", ephemeral=True)
            return

        robber["last_rob"] = now
        if random.random() < 0.5:
            stolen = max(100, int(v_wallet * random.uniform(0.15, 0.35)))
            victim["wallet"] -= stolen
            robber["wallet"] += stolen
            save_db(data)
            await interaction.response.send_message(f"🥷 Thành công! Bạn vừa móc trộm được **+{stolen:,}** {COIN} từ ví của {nan_nhan.mention}!")
        else:
            fine = min(r_wallet, random.randint(300, 600))
            robber["wallet"] -= fine
            victim["wallet"] += fine
            save_db(data)
            await interaction.response.send_message(f"🚨 Bị bắt quả tang tại trận! Bạn bị đền **-{fine:,}** {COIN} cho {nan_nhan.mention}!")

    # ================= 9. CHUYỂN TIỀN PAY (THUẾ 20% & KHÓA NỢ QUÁ HẠN) =================
    @commands.command(name="pay", aliases=["give", "chuyen"])
    async def cmd_pay(self, ctx, target: discord.Member, amount: int):
        if target.id == ctx.author.id or target.bot or amount <= 0:
            await ctx.send("❌ Thông tin chuyển khoản không hợp lệ!")
            return

        data = load_db()
        apply_bank_tax(data)

        # 🚨 CHẶN TẨU TÁN TÀI SẢN KHI ĐANG BỊ NỢ QUÁ HẠN
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, ctx.author.id)
        if is_overdue:
            await ctx.send(f"🚨 **TÀI KHOẢN BỊ PHONG TỎA CHUYỂN TIỀN!**\n"
                           f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{total_debt:,}** {COIN}!\n"
                           f"👉 Bắt buộc phải trả hết nợ (`!trano`) mới được phép chuyển tiền cho người khác!")
            return

        sender = get_user(data, ctx.author.id)
        receiver = get_user(data, target.id)

        if sender.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})")
            return

        tax = int(amount * 0.20)
        net_received = amount - tax

        sender["wallet"] -= amount
        receiver["wallet"] = receiver.get("wallet", 0) + net_received
        add_to_treasury(data, tax)
        save_db(data)

        await ctx.send(
            f"💸 **CHUYỂN KHOẢN THÀNH CÔNG!**\n"
            f"• {ctx.author.mention} chuyển: **{amount:,}** {COIN}\n"
            f"• Thuế giao dịch (20% nộp Kho Bạc): **-{tax:,}** {COIN}\n"
            f"• {target.mention} thực nhận: **+{net_received:,}** {COIN}!"
        )

    @app_commands.command(name="pay", description="Chuyển tiền cho thành viên khác (Phí chiết khấu 20%)")
    async def slash_pay(self, interaction: discord.Interaction, nguoi_nhan: discord.Member, so_tien: int):
        if nguoi_nhan.id == interaction.user.id or nguoi_nhan.bot or so_tien <= 0:
            await interaction.response.send_message("❌ Thông tin chuyển khoản không hợp lệ!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)

        # 🚨 CHẶN TẨU TÁN TÀI SẢN KHI ĐANG BỊ NỢ QUÁ HẠN
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
        if is_overdue:
            await interaction.response.send_message(
                f"🚨 **TÀI KHOẢN BỊ PHONG TỎA CHUYỂN TIỀN!**\n"
                f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{total_debt:,}** {COIN}!\n"
                f"👉 Bắt buộc phải trả hết nợ (`/trano`) mới được phép chuyển tiền!",
                ephemeral=True
            )
            return

        sender = get_user(data, interaction.user.id)
        receiver = get_user(data, nguoi_nhan.id)

        if sender.get("wallet", 0) < so_tien:
            await interaction.response.send_message(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})", ephemeral=True)
            return

        tax = int(so_tien * 0.20)
        net_received = so_tien - tax

        sender["wallet"] -= so_tien
        receiver["wallet"] = receiver.get("wallet", 0) + net_received
        add_to_treasury(data, tax)
        save_db(data)

        await interaction.response.send_message(
            f"💸 **CHUYỂN KHOẢN THÀNH CÔNG!**\n"
            f"• {interaction.user.mention} chuyển: **{so_tien:,}** {COIN}\n"
            f"• Thuế giao dịch (20% nộp Kho Bạc): **-{tax:,}** {COIN}\n"
            f"• {nguoi_nhan.mention} thực nhận: **+{net_received:,}** {COIN}!"
        )

    # ================= 10. LAO ĐỘNG CÔNG ÍCH CHUỘC NỢ =================
    @commands.command(name="laodong", aliases=["chuocno", "laodongcongich", "culi_work"])
    async def cmd_laodong(self, ctx):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_laodong", 0)

        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, ctx.author.id)
        if total_debt <= 0:
            await ctx.send("✨ Bạn không có khoản nợ ngân hàng nào để phải đi lao động công ích!")
            return

        if now - last < 900:
            rem = int(900 - (now - last))
            await ctx.send(f"⏳ Bạn vừa đi lao động công ích mệt rồi, nghỉ ngơi **{rem // 60}p {rem % 60}s** nữa mới được cuốc đất tiếp!")
            return

        tasks = [
            ("Quét dọn sòng bạc Casino sau giờ bão xúc xắc", random.randint(1000000, 2500000)),
            ("Lao công chùi rửa toilet phòng Vip Server", random.randint(1200000, 3000000)),
            ("Chạy bàn bưng bê nước phục vụ các Đại Gia sòng bạc", random.randint(1000000, 2000000)),
            ("Nhặt bóng sân Golf cho các chủ nợ", random.randint(1500000, 3000000)),
            ("Làm culi chạy deadline chuộc tội đánh bạc thua", random.randint(1000000, 2500000))
        ]
        task_name, debt_cleared_val = random.choice(tasks)
        u["last_laodong"] = now

        paid, rem_debt, cleared = deduct_loan_debt(data, ctx.author.id, debt_cleared_val)
        save_db(data)

        if cleared:
            status_text = "🎉 **BẠN ĐÃ TRẢ HẾT SẠCH TOÀN BỘ NỢ NGÂN HÀNG! TÀI KHOẢN ĐÃ ĐƯỢC TỰ DO!**"
            color = discord.Color.green()
        else:
            status_text = f"💳 **Nợ ngân hàng còn lại:** **{rem_debt:,}** {COIN}"
            color = discord.Color.orange()

        embed = discord.Embed(
            title="👮 LAO ĐỘNG CÔNG ÍCH CHUỘC NỢ 🧹",
            description=f"**Con nợ:** {ctx.author.mention}\n"
                        f"🔨 **Công việc:** *{task_name}*\n"
                        f"✨ **Được trừ nợ:** **-{paid:,}** {COIN}\n\n"
                        f"{status_text}",
            color=color
        )
        embed.set_footer(text="Mỗi 15 phút được lao động công ích 1 lần để xóa nợ!")
        await ctx.send(embed=embed)

    @app_commands.command(name="laodong", description="Lao động công ích chuộc tội đánh bạc thua để trừ nợ ngân hàng (15 phút/lần)")
    async def slash_laodong(self, interaction: discord.Interaction):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)
        now = time.time()
        last = u.get("last_laodong", 0)

        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
        if total_debt <= 0:
            await interaction.response.send_message("✨ Bạn không có khoản nợ ngân hàng nào để phải đi lao động công ích!", ephemeral=True)
            return

        if now - last < 900:
            rem = int(900 - (now - last))
            await interaction.response.send_message(f"⏳ Bạn vừa đi lao động công ích mệt rồi, nghỉ ngơi **{rem // 60}p {rem % 60}s** nữa mới được cuốc đất tiếp!", ephemeral=True)
            return

        tasks = [
            ("Quét dọn sòng bạc Casino sau giờ bão xúc xắc", random.randint(1000000, 2500000)),
            ("Lao công chùi rửa toilet phòng Vip Server", random.randint(1200000, 3000000)),
            ("Chạy bàn bưng bê nước phục vụ các Đại Gia sòng bạc", random.randint(1000000, 2000000)),
            ("Nhặt bóng sân Golf cho các chủ nợ", random.randint(1500000, 3000000)),
            ("Làm culi chạy deadline chuộc tội đánh bạc thua", random.randint(1000000, 2500000))
        ]
        task_name, debt_cleared_val = random.choice(tasks)
        u["last_laodong"] = now

        paid, rem_debt, cleared = deduct_loan_debt(data, interaction.user.id, debt_cleared_val)
        save_db(data)

        if cleared:
            status_text = "🎉 **BẠN ĐÃ TRẢ HẾT SẠCH TOÀN BỘ NỢ NGÂN HÀNG! TÀI KHOẢN ĐÃ ĐƯỢC TỰ DO!**"
            color = discord.Color.green()
        else:
            status_text = f"💳 **Nợ ngân hàng còn lại:** **{rem_debt:,}** {COIN}"
            color = discord.Color.orange()

        embed = discord.Embed(
            title="👮 LAO ĐỘNG CÔNG ÍCH CHUỘC NỢ 🧹",
            description=f"**Con nợ:** {interaction.user.mention}\n"
                        f"🔨 **Công việc:** *{task_name}*\n"
                        f"✨ **Được trừ nợ:** **-{paid:,}** {COIN}\n\n"
                        f"{status_text}",
            color=color
        )
        await interaction.response.send_message(embed=embed)

    # ================= 11. TOP ĐẠI GIA =================
    @commands.command(name="top", aliases=["leaderboard", "rich"])
    async def cmd_top(self, ctx):
        data = load_db()
        apply_bank_tax(data)
        users = data.get("users", {})
        if not users:
            await ctx.send("Chưa có dữ liệu người chơi.")
            return

        sorted_users = sorted(users.items(), key=lambda x: x[1].get("wallet", 0) + x[1].get("bank", 0), reverse=True)
        embed = discord.Embed(title="🏆 BẢNG PHONG THẦN ĐẠI GIA NEKO 🌟", color=discord.Color.gold())
        desc = ""
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, (u_id, u_info) in enumerate(sorted_users[:10]):
            tot = u_info.get("wallet", 0) + u_info.get("bank", 0)
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            desc += f"{medal} <@{u_id}> — **{tot:,}** {COIN}\n"
        embed.description = desc
        await ctx.send(embed=embed)

    @app_commands.command(name="top", description="Xem Bảng Phong Thần Top 10 Đại Gia giàu nhất")
    async def slash_top(self, interaction: discord.Interaction):
        data = load_db()
        apply_bank_tax(data)
        users = data.get("users", {})
        if not users:
            await interaction.response.send_message("Chưa có dữ liệu người chơi.")
            return

        sorted_users = sorted(users.items(), key=lambda x: x[1].get("wallet", 0) + x[1].get("bank", 0), reverse=True)
        embed = discord.Embed(title="🏆 BẢNG PHONG THẦN ĐẠI GIA NEKO 🌟", color=discord.Color.gold())
        desc = ""
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, (u_id, u_info) in enumerate(sorted_users[:10]):
            tot = u_info.get("wallet", 0) + u_info.get("bank", 0)
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            desc += f"{medal} <@{u_id}> — **{tot:,}** {COIN}\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed)

    # ================= 12. BẢNG PHONG THẦN THẦN BÀI TOPWIN =================
    @commands.command(name="topwin", aliases=["topthang", "bangwin", "thanbai"])
    async def cmd_topwin(self, ctx):
        """Xem Bảng Phong Thần Top Tỷ Lệ Thắng Sòng Bạc"""
        data = load_db()
        users = data.get("users", {})
        
        player_stats = []
        for uid, uinfo in users.items():
            games = uinfo.get("casino_games", 0)
            wins = uinfo.get("casino_wins", 0)
            profit = uinfo.get("casino_profit", 0)
            if games >= 3:
                win_rate = (wins / games) * 100.0
                player_stats.append((uid, win_rate, wins, games, profit))

        if not player_stats:
            await ctx.send("🎰 Chưa có đủ dữ liệu sòng bạc (Cần tối thiểu chơi 3 ván để lên Bảng Phong Thần)!")
            return

        player_stats.sort(key=lambda x: (x[1], x[4]), reverse=True)

        embed = discord.Embed(
            title="🏆 BẢNG PHONG THẦN THẦN BÀI (TOP WIN RATE) 🎰",
            description="Vinh danh những cao thủ cờ bạc có tỷ lệ thắng cao nhất Server:\n",
            color=discord.Color.gold()
        )
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        desc = ""
        for i, (uid, wr, wins, games, profit) in enumerate(player_stats[:10]):
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            profit_str = f"+{profit:,}" if profit >= 0 else f"{profit:,}"
            desc += f"{medal} <@{uid}> — **{wr:.1f}% Win Rate** *({wins}/{games} trận)* • Lãi: **{profit_str}** {COIN}\n"

        embed.description = desc
        embed.set_footer(text="Tối thiểu 3 ván để lên bảng • Tỷ lệ thắng tự động điều chỉnh theo mức cược!")
        await ctx.send(embed=embed)

    @app_commands.command(name="topwin", description="Xem Bảng Phong Thần Top Tỷ Lệ Thắng Casino của Server")
    async def slash_topwin(self, interaction: discord.Interaction):
        data = load_db()
        users = data.get("users", {})
        
        player_stats = []
        for uid, uinfo in users.items():
            games = uinfo.get("casino_games", 0)
            wins = uinfo.get("casino_wins", 0)
            profit = uinfo.get("casino_profit", 0)
            if games >= 3:
                win_rate = (wins / games) * 100.0
                player_stats.append((uid, win_rate, wins, games, profit))

        if not player_stats:
            await interaction.response.send_message("🎰 Chưa có đủ dữ liệu sòng bạc (Cần tối thiểu chơi 3 ván)!", ephemeral=True)
            return

        player_stats.sort(key=lambda x: (x[1], x[4]), reverse=True)

        embed = discord.Embed(
            title="🏆 BẢNG PHONG THẦN THẦN BÀI (TOP WIN RATE) 🎰",
            color=discord.Color.gold()
        )
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        desc = ""
        for i, (uid, wr, wins, games, profit) in enumerate(player_stats[:10]):
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            profit_str = f"+{profit:,}" if profit >= 0 else f"{profit:,}"
            desc += f"{medal} <@{uid}> — **{wr:.1f}% Win Rate** *({wins}/{games} trận)* • Lãi: **{profit_str}** {COIN}\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
