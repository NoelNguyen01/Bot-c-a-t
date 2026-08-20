# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user, add_to_treasury, apply_bank_tax, calculate_loan_debt

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

    # ================= 1. XEM VÍ & NGÂN HÀNG & NỢ NẦN =================
    @commands.command(name="bal", aliases=["balance", "vi", "money"])
    async def cmd_bal(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, target.id)
        wallet = u.get("wallet", 0)
        bank = u.get("bank", 0)
        total = wallet + bank

        # Kiểm tra nợ ngân hàng
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
                value=f"{status_tag}\n• Nợ gốc: **{principal:,}** {COIN}\n• Lãi phát sinh: **+{interest:,}** {COIN}\n👉 **TỔNG CẦN TRẢ:** **{total_debt:,}** {COIN}\n*(Gõ `!trano all` để thanh toán)*",
                inline=False
            )

        embed.set_footer(text="Thuế Bank 5% mỗi 5h • Giao dịch chuyển tiền !pay phí 20%")
        await ctx.send(embed=embed)

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

    # ================= 3. HỆ THỐNG VAY NGÂN HÀNG =================
    @commands.command(name="vay", aliases=["loan", "vaytien"])
    async def cmd_vay(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Số tiền vay phải lớn hơn 0!")
            return

        data = load_db()
        uid = str(ctx.author.id)
        loans = data.get("loans", {})

        # Kiểm tra nợ cũ
        if uid in loans and loans[uid].get("principal", 0) > 0:
            total_debt, principal, interest, _ = calculate_loan_debt(data, ctx.author.id)
            await ctx.send(f"❌ Bạn đang có khoản nợ chưa trả (**{total_debt:,}** {COIN})! Vui lòng dùng `!trano` trả hết trước khi vay tiếp.")
            return

        u = get_user(data, ctx.author.id)
        total_assets = u.get("wallet", 0) + u.get("bank", 0)

        # Tính hạn mức vay
        if total_assets >= 50000000:
            max_limit = 100000000
            tier_name = "VIP (Tài sản ≥ 50M)"
        else:
            max_limit = 30000000
            tier_name = "Thường (Tài sản < 50M)"

        if amount > max_limit:
            await ctx.send(f"❌ Hạn mức vay của bạn ({tier_name}) tối đa là **{max_limit:,}** {COIN}!")
            return

        # Giải ngân
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

        # Xử lý trả nợ
        if pay_amt >= total_debt:
            # Trả sạch toàn bộ nợ
            actual_paid = total_debt
            u["wallet"] -= actual_paid
            add_to_treasury(data, interest)  # Tiền lãi nộp vào Kho Bạc Bot
            del data["loans"][uid]
            save_db(data)
            await ctx.send(f"🎉 **CHÚC MỪNG BẠN ĐÃ TRẢ SẠCH NỢ!** Đã thanh toán **{actual_paid:,}** {COIN} (Gốc: {principal:,} + Lãi: {interest:,})!")
        else:
            # Trả một phần nợ
            u["wallet"] -= pay_amt
            new_debt = total_debt - pay_amt
            # Cập nhật lại gốc và timestamp
            data["loans"][uid]["principal"] = new_debt
            data["loans"][uid]["timestamp"] = time.time()
            save_db(data)
            await ctx.send(f"✅ Đã trả bớt **{pay_amt:,}** {COIN}! Số nợ còn lại: **{new_debt:,}** {COIN}.")

    @commands.command(name="topno", aliases=["banno", "chuachom"])
    async def cmd_topno(self, ctx):
        """Xem danh sách Top 10 Chúa Chổm nợ ngân hàng nhiều nhất"""
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

    @commands.command(name="sono", aliases=["bangno", "danhsachno"])
    async def cmd_sono(self, ctx):
        """Xem Bảng Phong Thần Nợ Nần P2P giữa các thành viên"""
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
        total = base + bonus

        u["last_daily"] = now
        u["streak"] = streak
        u["wallet"] = u.get("wallet", 0) + total
        save_db(data)

        embed = discord.Embed(
            title="🎁 PHẦN THƯỞNG ĐIỂM DANH HẰNG NGÀY",
            description=f"🎉 Bạn nhận được **+{total:,}** {COIN}!\n"
                        f"• Thưởng gốc: **{base:,}** {COIN}\n"
                        f"• Thưởng chuỗi (Streak {streak} ngày): **+{bonus:,}** {COIN}\n"
                        f"• Số dư ví: **{u['wallet']:,}** {COIN}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

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
        u["last_work"] = now
        u["wallet"] = u.get("wallet", 0) + wage
        save_db(data)
        await ctx.send(f"💼 Bạn vừa làm **{job}** và nhận được **+{wage:,}** {COIN}! (Ví: **{u['wallet']:,}** {COIN})")

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
            u["wallet"] = u.get("wallet", 0) + amt
            save_db(data)
            await ctx.send(f"🥺 Bạn được người tốt bố thí cho **+{amt:,}** {COIN}! (Ví: **{u['wallet']:,}** {COIN})")
        else:
            await ctx.send("💀 Bạn chìa nón ra nhưng bị bảo vệ đuổi chạy té khói!")

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

        if victim.get("shield_until", 0) > now:
            await ctx.send(f"🛡️ {target.mention} đang được bảo vệ bởi Khiên Thần Thánh! Không thể cướp!")
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

    # ================= 9. CHUYỂN TIỀN PAY (THUẾ 20%) =================
    @commands.command(name="pay", aliases=["give", "chuyen"])
    async def cmd_pay(self, ctx, target: discord.Member, amount: int):
        if target.id == ctx.author.id or target.bot or amount <= 0:
            await ctx.send("❌ Thông tin chuyển khoản không hợp lệ!")
            return

        data = load_db()
        apply_bank_tax(data)
        sender = get_user(data, ctx.author.id)
        receiver = get_user(data, target.id)

        if sender.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})")
            return

        # Thuế chiết khấu giao dịch 20%
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

    # ================= 10. TOP ĐẠI GIA =================
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


async def setup(bot):
    await bot.add_cog(Economy(bot))
