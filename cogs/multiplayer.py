# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user, add_to_treasury, apply_bank_tax, calculate_loan_debt, deduct_loan_debt, parse_amount

COIN = "💵"


# ================= 1. KÉO BÚA BAO SOLO (RPS VIEW) =================
class RPSView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, bet: int):
        super().__init__(timeout=45.0)
        self.p1 = p1
        self.p2 = p2
        self.bet = bet
        self.choices = {}
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("❌ Trận đấu này không phải của bạn!", ephemeral=True)
            return False
        return True

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        if self.finished:
            return

        if interaction.user.id in self.choices:
            await interaction.response.send_message(f"Bạn đã chọn rồi, đang đợi đối thủ ra đòn!", ephemeral=True)
            return

        self.choices[interaction.user.id] = choice
        choice_icons = {"rock": "🪨 Búa", "paper": "📄 Bao", "scissors": "✂️ Kéo"}
        await interaction.response.send_message(f"🤫 Bạn đã bí mật chọn **{choice_icons[choice]}**! Chờ đối thủ chọn...", ephemeral=True)

        if len(self.choices) == 2:
            self.finished = True
            for child in self.children:
                child.disabled = True

            c1 = self.choices[self.p1.id]
            c2 = self.choices[self.p2.id]

            data = load_db()
            u1 = get_user(data, self.p1.id)
            u2 = get_user(data, self.p2.id)

            rules = {"rock": "scissors", "scissors": "paper", "paper": "rock"}

            if c1 == c2:
                result_text = f"🤝 **HÒA NHAU!** Cả 2 đều ra {choice_icons[c1]}!\nHoàn lại tiền cược **{self.bet:,}** {COIN}."
                color = discord.Color.yellow()
            elif rules[c1] == c2:
                tax = int(self.bet * 0.10)
                net_win = self.bet - tax
                u1["wallet"] += net_win
                u2["wallet"] -= self.bet
                add_to_treasury(data, tax)
                result_text = f"🏆 **{self.p1.mention} CHIẾN THẮNG!**\n" \
                              f"• {self.p1.display_name}: {choice_icons[c1]}\n" \
                              f"• {self.p2.display_name}: {choice_icons[c2]}\n\n" \
                              f"💰 {self.p1.mention} nhận **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
                color = discord.Color.green()
            else:
                tax = int(self.bet * 0.10)
                net_win = self.bet - tax
                u2["wallet"] += net_win
                u1["wallet"] -= self.bet
                add_to_treasury(data, tax)
                result_text = f"🏆 **{self.p2.mention} CHIẾN THẮNG!**\n" \
                              f"• {self.p2.display_name}: {choice_icons[c2]}\n" \
                              f"• {self.p1.display_name}: {choice_icons[c1]}\n\n" \
                              f"💰 {self.p2.mention} nhận **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
                color = discord.Color.green()

            save_db(data)
            embed = discord.Embed(
                title="✂️ KẾT QUẢ KÉO BÚA BAO SOLO 🪨",
                description=result_text,
                color=color
            )
            embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
            await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="🪨 Búa", style=discord.ButtonStyle.primary)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="📄 Bao", style=discord.ButtonStyle.success)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label="✂️ Kéo", style=discord.ButtonStyle.danger)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")


# ================= 2. VIEW PHÁT LÌ XÌ LÀNG =================
class LiXiView(discord.ui.View):
    def __init__(self, sender_name: str, total_money: int, total_slots: int, wish: str = ""):
        super().__init__(timeout=180.0)
        self.sender_name = sender_name
        self.total_money = total_money
        self.total_slots = total_slots
        self.wish = wish
        self.claimed_users = {}
        self.remaining_money = total_money
        self.remaining_slots = total_slots
        self.lock = asyncio.Lock()

    @discord.ui.button(label="🧧 Giật Lì Xì Nhanh!", style=discord.ButtonStyle.danger, custom_id="btn_claim_lixi")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.lock:
            if interaction.user.id in self.claimed_users:
                await interaction.response.send_message(f"❌ Bạn đã giật được **{self.claimed_users[interaction.user.id]:,}** {COIN} rồi, không được tham lam!", ephemeral=True)
                return

            if self.remaining_slots <= 0:
                await interaction.response.send_message("❌ Bao lì xì đã được giật hết sạch rồi!", ephemeral=True)
                return

            if self.remaining_slots == 1:
                amount = self.remaining_money
            else:
                max_claim = int((self.remaining_money / self.remaining_slots) * 1.8)
                amount = random.randint(1, max(1, max_claim))

            self.remaining_money -= amount
            self.remaining_slots -= 1
            self.claimed_users[interaction.user.id] = amount

            data = load_db()
            debt_msg = ""
            total_debt, principal, interest, is_overdue = calculate_loan_debt(data, interaction.user.id)
            actual_received = amount
            if total_debt > 0:
                seize = int(amount * 0.5)
                paid, rem_debt, cleared = deduct_loan_debt(data, interaction.user.id, seize)
                actual_received -= paid
                if cleared:
                    debt_msg = f" *(Đã trích -{paid:,} {COIN} trả sạch hết nợ ngân hàng!)*"
                else:
                    debt_msg = f" *(Đã trích -{paid:,} {COIN} trả nợ, nợ còn: {rem_debt:,} {COIN})*"

            u = get_user(data, interaction.user.id)
            u["wallet"] = u.get("wallet", 0) + actual_received
            save_db(data)

            await interaction.response.send_message(f"🎉 Bạn giật được **+{amount:,}** {COIN} từ bao lì xì của {self.sender_name}! (Thực nhận: **+{actual_received:,}** {COIN}){debt_msg}", ephemeral=True)

            desc = f"🧧 **{self.sender_name}** vừa phát bao lì xì **{self.total_money:,}** {COIN} cho **{self.total_slots} người**!\n"
            if self.wish:
                desc += f"💬 *Lời chúc:* \"{self.wish}\"\n\n"
            else:
                desc += "\n"

            desc += f"📊 **Còn lại:** **{self.remaining_money:,}** {COIN} ({self.remaining_slots}/{self.total_slots} phần)\n\n"
            desc += "**🏆 Danh sách cao thủ giật lì xì:**\n"
            for uid, amt in self.claimed_users.items():
                desc += f"• <@{uid}>: **+{amt:,}** {COIN}\n"

            if self.remaining_slots <= 0:
                for child in self.children:
                    child.disabled = True
                desc += "\n✨ **BAO LÌ XÌ ĐÃ HẾT SẠCH!**"

            embed = discord.Embed(
                title="🧧 BAO LÌ XÌ MAY MẮN CẢ LÀNG 🧧",
                description=desc,
                color=discord.Color.red()
            )
            await interaction.message.edit(embed=embed, view=self)


# ================= 3. VIEW LÌ XÌ RIÊNG 1V1 =================
class LiXiRiengView(discord.ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member, amount: int, wish: str = ""):
        super().__init__(timeout=300.0)
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.wish = wish
        self.opened = False

    @discord.ui.button(label="🎁 Mở Phong Bao Lì Xì", style=discord.ButtonStyle.success, custom_id="btn_open_lixirieng")
    async def open_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message("❌ Phong bao đỏ này không phải gửi cho bạn!", ephemeral=True)
            return

        if self.opened:
            await interaction.response.send_message("❌ Bao lì xì này đã được mở rồi!", ephemeral=True)
            return

        self.opened = True
        for child in self.children:
            child.disabled = True

        data = load_db()
        debt_msg = ""
        total_debt, principal, interest, is_overdue = calculate_loan_debt(data, self.recipient.id)
        actual_received = self.amount
        if total_debt > 0:
            seize = int(self.amount * 0.5)
            paid, rem_debt, cleared = deduct_loan_debt(data, self.recipient.id, seize)
            actual_received -= paid
            if cleared:
                debt_msg = f"\n💸 **CƯỠNG CHẾ XIẾT NỢ (50%):** Thu **-{paid:,}** {COIN}!\n🎉 **BẠN ĐÃ TRẢ HẾT TOÀN BỘ NỢ VAY NGÂN HÀNG!**"
            else:
                debt_msg = f"\n💸 **CƯỠNG CHẾ XIẾT NỢ (50%):** Thu **-{paid:,}** {COIN} để trả nợ! (Nợ còn: **{rem_debt:,}** {COIN})"

        u = get_user(data, self.recipient.id)
        u["wallet"] = u.get("wallet", 0) + actual_received
        save_db(data)

        embed = discord.Embed(
            title="🎁 PHONG BAO LÌ XÌ ĐÃ ĐƯỢC MỞ! 🧧",
            description=f"🎉 **{self.recipient.mention}** đã mở phong bao lì xì từ **{self.sender.mention}**!\n\n"
                        f"💰 Số tiền nhận được: **+{self.amount:,}** {COIN} (Thực nhận ví: **+{actual_received:,}** {COIN}){debt_msg}\n"
                        f"💬 Lời chúc: *\"{self.wish or 'Chúc bạn luôn may mắn và phát tài phát lộc!'}\"*",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=self)


class Multiplayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tx_rooms = {}

    # ================= 1. KÉO BÚA BAO SOLO =================
    @commands.command(name="rps", aliases=["keobuabao", "kbb"])
    async def cmd_rps(self, ctx, opponent: discord.Member, bet: str = "1000"):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.send("❌ Đối thủ không hợp lệ!")
            return

        data = load_db()
        apply_bank_tax(data)
        u1 = get_user(data, ctx.author.id)
        u2 = get_user(data, opponent.id)

        bet_val = parse_amount(bet, u1.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!rps @user 500k`, `!rps @user 10b`, `!rps @user all`)")
            return

        # 🚨 KIỂM TRA PHONG TỎA NỢ XẤU
        d1_debt, _, _, d1_over = calculate_loan_debt(data, ctx.author.id)
        d2_debt, _, _, d2_over = calculate_loan_debt(data, opponent.id)
        if d1_over:
            await ctx.send(f"🚨 **TÀI KHOẢN CỦA BẠN ĐÃ BỊ PHONG TỎA CÁ CƯỢC!** Nợ quá hạn: **{d1_debt:,}** {COIN}. Hãy trả nợ (`!trano`) trước!")
            return
        if d2_over:
            await ctx.send(f"🚨 **ĐỐI THỦ ĐANG BỊ PHONG TỎA DO NỢ QUÁ HẠN!** (Nợ: **{d2_debt:,}** {COIN})")
            return

        if u1.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Bạn không đủ tiền cược! (Ví: **{u1.get('wallet', 0):,}** {COIN})")
            return
        if u2.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ {opponent.mention} không đủ tiền cược **{bet_val:,}** {COIN}!")
            return

        embed = discord.Embed(
            title="⚔️ THÁCH ĐẤU KÉO BÚA BAO SOLO 1V1 🪨📄✂️",
            description=f"**{ctx.author.mention}** đã thách đấu **{opponent.mention}**!\n"
                        f"💰 **Tiền cược:** **{bet_val:,}** {COIN}\n\n"
                        f"👉 Cả 2 hãy bấm chọn nút bên dưới (Lựa chọn được giữ bí mật 100%)!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        view = RPSView(ctx.author, opponent, bet_val)
        await ctx.send(content=f"{ctx.author.mention} vs {opponent.mention}", embed=embed, view=view)

    @app_commands.command(name="rps", description="Thách đấu Kéo Búa Bao solo 1v1 cược tiền (Hỗ trợ 10m, 5b, all)")
    async def slash_rps(self, interaction: discord.Interaction, doi_thu: discord.Member, tien_cuoc: str = "1000"):
        if doi_thu.id == interaction.user.id or doi_thu.bot:
            await interaction.response.send_message("❌ Không thể thách đấu chính mình / bot!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        u1 = get_user(data, interaction.user.id)
        u2 = get_user(data, doi_thu.id)

        bet_val = parse_amount(tien_cuoc, u1.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `5b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA NỢ XẤU
        d1_debt, _, _, d1_over = calculate_loan_debt(data, interaction.user.id)
        d2_debt, _, _, d2_over = calculate_loan_debt(data, doi_thu.id)
        if d1_over:
            await interaction.response.send_message(f"🚨 **TÀI KHOẢN ĐÃ BỊ PHONG TỎA CÁ CƯỢC!** Nợ quá hạn: **{d1_debt:,}** {COIN}. Hãy trả nợ (`/trano`) trước!", ephemeral=True)
            return
        if d2_over:
            await interaction.response.send_message(f"🚨 **ĐỐI THỦ ĐANG BỊ PHONG TỎA DO NỢ QUÁ HẠN!** (Nợ: **{d2_debt:,}** {COIN})", ephemeral=True)
            return

        if u1.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Bạn không đủ tiền cược! (Ví: **{u1.get('wallet', 0):,}** {COIN})", ephemeral=True)
            return
        if u2.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ {doi_thu.mention} không đủ tiền cược **{bet_val:,}** {COIN}!", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚔️ THÁCH ĐẤU KÉO BÚA BAO SOLO 1V1 🪨📄✂️",
            description=f"**{interaction.user.mention}** đã thách đấu **{doi_thu.mention}**!\n"
                        f"💰 **Tiền cược:** **{bet_val:,}** {COIN}\n\n"
                        f"👉 Cả 2 hãy bấm chọn nút bên dưới (Lựa chọn được giữ bí mật 100%)!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        view = RPSView(interaction.user, doi_thu, bet_val)
        await interaction.response.send_message(content=f"{interaction.user.mention} vs {doi_thu.mention}", embed=embed, view=view)

    # ================= 2. ĐỔ XÚC XẮC SOLO 1V1 =================
    @commands.command(name="dice", aliases=["xucxac", "dicesolo"])
    async def cmd_dice(self, ctx, opponent: discord.Member, bet: str = "1000"):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.send("❌ Đối thủ không hợp lệ!")
            return

        data = load_db()
        apply_bank_tax(data)
        u1 = get_user(data, ctx.author.id)
        u2 = get_user(data, opponent.id)

        bet_val = parse_amount(bet, u1.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!dice @user 10m`, `!dice @user 5b`, `!dice @user all`)")
            return

        # 🚨 KIỂM TRA PHONG TỎA NỢ XẤU
        d1_debt, _, _, d1_over = calculate_loan_debt(data, ctx.author.id)
        d2_debt, _, _, d2_over = calculate_loan_debt(data, opponent.id)
        if d1_over:
            await ctx.send(f"🚨 **TÀI KHOẢN CỦA BẠN ĐÃ BỊ PHONG TỎA CÁ CƯỢC!** Nợ quá hạn: **{d1_debt:,}** {COIN}. Hãy trả nợ (`!trano`) trước!")
            return
        if d2_over:
            await ctx.send(f"🚨 **ĐỐI THỦ ĐANG BỊ PHONG TỎA DO NỢ QUÁ HẠN!** (Nợ: **{d2_debt:,}** {COIN})")
            return

        if u1.get("wallet", 0) < bet_val or u2.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Một trong hai người không đủ tiền cược **{bet_val:,}** {COIN}!")
            return

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        if d1 > d2:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u1["wallet"] += net_win
            u2["wallet"] -= bet_val
            add_to_treasury(data, tax)
            winner = ctx.author
            win_txt = f"🏆 **{winner.mention} ĐÃ THẮNG (+{net_win:,} {COIN})!** *(Thuế 10%: -{tax:,} {COIN})*"
            color = discord.Color.green()
        elif d2 > d1:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u2["wallet"] += net_win
            u1["wallet"] -= bet_val
            add_to_treasury(data, tax)
            winner = opponent
            win_txt = f"🏆 **{winner.mention} ĐÃ THẮNG (+{net_win:,} {COIN})!** *(Thuế 10%: -{tax:,} {COIN})*"
            color = discord.Color.green()
        else:
            win_txt = "🤝 **HÒA NHAU!** Hoàn lại tiền cược."
            color = discord.Color.yellow()

        save_db(data)
        embed = discord.Embed(
            title="🎲 TRẬN CHIẾN ĐỔ XÚC XẮC SOLO 1V1 🎲",
            description=f"• {ctx.author.mention} đổ được: 🎲 **{d1} điểm**\n"
                        f"• {opponent.mention} đổ được: 🎲 **{d2} điểm**\n\n"
                        f"{win_txt}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        await ctx.send(embed=embed)

    @app_commands.command(name="dice", description="Solo Đổ xúc xắc 1v1 so điểm cao thấp (Hỗ trợ 10m, 5b, all)")
    async def slash_dice(self, interaction: discord.Interaction, doi_thu: discord.Member, tien_cuoc: str = "1000"):
        if doi_thu.id == interaction.user.id or doi_thu.bot:
            await interaction.response.send_message("❌ Không thể đấu với chính mình / bot!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        u1 = get_user(data, interaction.user.id)
        u2 = get_user(data, doi_thu.id)

        bet_val = parse_amount(tien_cuoc, u1.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `5b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA NỢ XẤU
        d1_debt, _, _, d1_over = calculate_loan_debt(data, interaction.user.id)
        d2_debt, _, _, d2_over = calculate_loan_debt(data, doi_thu.id)
        if d1_over:
            await interaction.response.send_message(f"🚨 **TÀI KHOẢN ĐÃ BỊ PHONG TỎA CÁ CƯỢC!** Nợ quá hạn: **{d1_debt:,}** {COIN}. Hãy trả nợ (`/trano`) trước!", ephemeral=True)
            return
        if d2_over:
            await interaction.response.send_message(f"🚨 **ĐỐI THỦ ĐANG BỊ PHONG TỎA DO NỢ QUÁ HẠN!** (Nợ: **{d2_debt:,}** {COIN})", ephemeral=True)
            return

        if u1.get("wallet", 0) < bet_val or u2.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Một trong hai người không đủ tiền cược **{bet_val:,}** {COIN}!", ephemeral=True)
            return

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        if d1 > d2:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u1["wallet"] += net_win
            u2["wallet"] -= bet_val
            add_to_treasury(data, tax)
            winner = interaction.user
            win_txt = f"🏆 **{winner.mention} ĐÃ THẮNG (+{net_win:,} {COIN})!** *(Thuế 10%: -{tax:,} {COIN})*"
            color = discord.Color.green()
        elif d2 > d1:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u2["wallet"] += net_win
            u1["wallet"] -= bet_val
            add_to_treasury(data, tax)
            winner = doi_thu
            win_txt = f"🏆 **{winner.mention} ĐÃ THẮNG (+{net_win:,} {COIN})!** *(Thuế 10%: -{tax:,} {COIN})*"
            color = discord.Color.green()
        else:
            win_txt = "🤝 **HÒA NHAU!** Hoàn lại tiền cược."
            color = discord.Color.yellow()

        save_db(data)
        embed = discord.Embed(
            title="🎲 TRẬN CHIẾN ĐỔ XÚC XẮC SOLO 1V1 🎲",
            description=f"• {interaction.user.mention} đổ được: 🎲 **{d1} điểm**\n"
            f"• {doi_thu.mention} đổ được: 🎲 **{d2} điểm**\n\n"
            f"{win_txt}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        await interaction.response.send_message(embed=embed)

    # ================= 3. PHÁT BAO LÌ XÌ CẢ LÀNG =================
    @commands.command(name="lixi", aliases=["phattien", "giveaway"])
    async def cmd_lixi(self, ctx, tong_tien: str, so_nguoi: int = 5, *, loi_chuc: str = ""):
        data = load_db()
        apply_bank_tax(data)
        sender = get_user(data, ctx.author.id)

        amt = parse_amount(tong_tien, sender.get("wallet", 0))
        if amt < 100 or so_nguoi <= 0:
            await ctx.send("❌ Tổng tiền tối thiểu 100 và số người phải lớn hơn 0!")
            return

        if sender.get("wallet", 0) < amt:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})")
            return

        sender["wallet"] -= amt
        save_db(data)

        desc = f"🧧 **{ctx.author.mention}** vừa phát bao lì xì **{amt:,}** {COIN} cho **{so_nguoi} người**!\n"
        if loi_chuc:
            desc += f"💬 *Lời chúc:* \"{loi_chuc}\"\n\n"
        else:
            desc += "\n"
        desc += "👉 Bấm nút **'🧧 Giật Lì Xì Nhanh!'** bên dưới để nhận tiền may mắn!"

        embed = discord.Embed(
            title="🧧 BAO LÌ XÌ MAY MẮN CẢ LÀNG 🧧",
            description=desc,
            color=discord.Color.red()
        )
        view = LiXiView(ctx.author.display_name, amt, so_nguoi, loi_chuc)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="lixi", description="Phát bao lì xì may mắn cho cả làng bấm nút giật nhanh (Hỗ trợ 10m, 50b)")
    async def slash_lixi(self, interaction: discord.Interaction, tong_tien: str, so_nguoi: int = 5, loi_chuc: Optional[str] = ""):
        data = load_db()
        apply_bank_tax(data)
        sender = get_user(data, interaction.user.id)

        amt = parse_amount(tong_tien, sender.get("wallet", 0))
        if amt < 100 or so_nguoi <= 0:
            await interaction.response.send_message("❌ Tổng tiền tối thiểu 100 và số người phải lớn hơn 0!", ephemeral=True)
            return

        if sender.get("wallet", 0) < amt:
            await interaction.response.send_message(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})", ephemeral=True)
            return

        sender["wallet"] -= amt
        save_db(data)

        desc = f"🧧 **{interaction.user.mention}** vừa phát bao lì xì **{amt:,}** {COIN} cho **{so_nguoi} người**!\n"
        if loi_chuc:
            desc += f"💬 *Lời chúc:* \"{loi_chuc}\"\n\n"
        else:
            desc += "\n"
        desc += "👉 Bấm nút **'🧧 Giật Lì Xì Nhanh!'** bên dưới để nhận tiền may mắn!"

        embed = discord.Embed(
            title="🧧 BAO LÌ XÌ MAY MẮN CẢ LÀNG 🧧",
            description=desc,
            color=discord.Color.red()
        )
        view = LiXiView(interaction.user.display_name, amt, so_nguoi, loi_chuc or "")
        await interaction.response.send_message(embed=embed, view=view)

    # ================= 4. LÌ XÌ RIÊNG 1V1 =================
    @commands.command(name="lixirieng", aliases=["lixiprivate", "tanglixi"])
    async def cmd_lixirieng(self, ctx, recipient: discord.Member, amount: str, *, loi_chuc: str = ""):
        if recipient.id == ctx.author.id or recipient.bot:
            await ctx.send("❌ Thông tin lì xì không hợp lệ!")
            return

        data = load_db()
        apply_bank_tax(data)
        sender = get_user(data, ctx.author.id)

        amt = parse_amount(amount, sender.get("wallet", 0))
        if amt <= 0:
            await ctx.send("❌ Số tiền lì xì không hợp lệ!")
            return

        if sender.get("wallet", 0) < amt:
            await ctx.send(f"❌ Ví không đủ tiền! Hiện có: **{sender.get('wallet', 0):,}** {COIN}")
            return

        sender["wallet"] -= amt
        save_db(data)

        embed = discord.Embed(
            title="💌 PHONG BAO LÌ XÌ RIÊNG 1V1 🧧",
            description=f"🧧 **{ctx.author.mention}** vừa gửi một phong bao đỏ bí mật cho **{recipient.mention}**!\n\n"
                        f"👉 Chỉ **{recipient.mention}** mới có quyền bấm nút mở phong bao bên dưới!",
            color=discord.Color.red()
        )
        view = LiXiRiengView(ctx.author, recipient, amt, loi_chuc)
        await ctx.send(content=recipient.mention, embed=embed, view=view)

    @app_commands.command(name="lixirieng", description="Gửi phong bao lì xì đỏ riêng 1v1 bí mật cho 1 người (Hỗ trợ 10m, 5b)")
    async def slash_lixirieng(self, interaction: discord.Interaction, nguoi_nhan: discord.Member, so_tien: str, loi_chuc: Optional[str] = ""):
        if nguoi_nhan.id == interaction.user.id or nguoi_nhan.bot:
            await interaction.response.send_message("❌ Thông tin lì xì không hợp lệ!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        sender = get_user(data, interaction.user.id)

        amt = parse_amount(so_tien, sender.get("wallet", 0))
        if amt <= 0:
            await interaction.response.send_message("❌ Số tiền lì xì không hợp lệ!", ephemeral=True)
            return

        if sender.get("wallet", 0) < amt:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{sender.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        sender["wallet"] -= amt
        save_db(data)

        embed = discord.Embed(
            title="💌 PHONG BAO LÌ XÌ RIÊNG 1V1 🧧",
            description=f"🧧 **{interaction.user.mention}** vừa gửi một phong bao đỏ bí mật cho **{nguoi_nhan.mention}**!\n\n"
                        f"👉 Chỉ **{nguoi_nhan.mention}** mới có quyền bấm nút mở phong bao bên dưới!",
            color=discord.Color.red()
        )
        view = LiXiRiengView(interaction.user, nguoi_nhan, amt, loi_chuc or "")
        await interaction.response.send_message(content=nguoi_nhan.mention, embed=embed, view=view)

    # ================= 5. ADMIN PHÁT LÌ XÌ TỪ KHO BẠC =================
    @commands.command(name="admin_lixi")
    @commands.has_permissions(administrator=True)
    async def cmd_admin_lixi(self, ctx, tong_tien: str, so_nguoi: int = 10, *, loi_chuc: str = "Admin chúc anh em server phát tài phát lộc!"):
        data = load_db()
        treasury_bal = data.get("treasury", {}).get("balance", 0)

        amt = parse_amount(tong_tien, treasury_bal)
        if amt <= 0 or so_nguoi <= 0:
            await ctx.send("❌ Số tiền và số người phải lớn hơn 0!")
            return

        if treasury_bal < amt:
            await ctx.send(f"❌ Kho Bạc Bot không đủ tiền! (Quỹ hiện có: **{treasury_bal:,}** {COIN})")
            return

        data["treasury"]["balance"] -= amt
        save_db(data)

        desc = f"👑 **ADMIN {ctx.author.mention} ĐÃ TRÍCH KHO BẠC PHÁT LÌ XÌ!** 🎊\n" \
               f"💰 Tổng tiền lì xì: **{amt:,}** {COIN} cho **{so_nguoi} người**!\n" \
               f"💬 *Lời chúc:* \"{loi_chuc}\"\n\n" \
               f"👉 Bấm nút **'🧧 Giật Lì Xì Nhanh!'** bên dưới để nhận lộc từ Kho Bạc!"

        embed = discord.Embed(
            title="👑 LÌ XÌ TRI ÂN SERVER TỪ KHO BẠC BOT 🏛️",
            description=desc,
            color=discord.Color.gold()
        )
        view = LiXiView("Kho Bạc Admin", amt, so_nguoi, loi_chuc)
        await ctx.send(embed=embed, view=view)

    # ================= 6. BÀN TÀI XỈU LÀNG =================
    @commands.command(name="txopen", aliases=["bantaixiu", "txl"])
    async def cmd_txopen(self, ctx, seconds: int = 30):
        guild_id = ctx.guild.id
        if guild_id in self.active_tx_rooms:
            await ctx.send("❌ Hiện tại đang có một bàn Tài Xỉu đang mở đặt cược rồi!")
            return

        seconds = max(15, min(seconds, 120))
        self.active_tx_rooms[guild_id] = {
            "tai": {},
            "xiu": {},
            "open": True
        }

        embed = discord.Embed(
            title="🎲 BÀN TÀI XỈU CẢ LÀNG MỞ CƯỢC! 🎲",
            description=f"📢 **{ctx.author.mention}** đã mở bàn Tài Xỉu cho cả Server!\n\n"
                        f"⏰ Thời gian đặt cược: **{seconds} Giây**\n"
                        f"👉 **Cách cược:** Gõ `!txb <tiền> <t/x>` (Ví dụ: `!txb 500m t`, `!txb 10b x`, `!txb all t`)\n\n"
                        f"🔴 **Cửa TÀI:** 0 {COIN}\n"
                        f"🟢 **Cửa XỈU:** 0 {COIN}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        await asyncio.sleep(seconds)

        room = self.active_tx_rooms.pop(guild_id, None)
        if not room:
            return

        d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2 + d3
        actual = "xiu" if total <= 10 else "tai"
        is_bao = (d1 == d2 == d3)

        data = load_db()
        winners = []
        losers = []

        for side, bets in [("tai", room["tai"]), ("xiu", room["xiu"])]:
            for uid, amt in bets.items():
                u = get_user(data, uid)
                if is_bao:
                    losers.append(f"<@{uid}>: **-{amt:,}** {COIN}")
                elif side == actual:
                    tax = int(amt * 0.10)
                    net_win = amt - tax
                    u["wallet"] += net_win
                    add_to_treasury(data, tax)
                    winners.append(f"<@{uid}>: **+{net_win:,}** {COIN}")
                else:
                    losers.append(f"<@{uid}>: **-{amt:,}** {COIN}")

        save_db(data)
        res_name = f"🔴 TÀI ({total} điểm)" if actual == "tai" else f"🟢 XỈU ({total} điểm)"
        if is_bao:
            res_name += f" 🌪️ BÃO {d1}! (Nhà cái hốt trọn ổ)"

        desc = f"🎲 Kết quả xúc xắc: `{d1}` + `{d2}` + `{d3}` = **{res_name}**\n\n"
        desc += f"🏆 **Danh sách THẮNG TIỀN ({len(winners)} người):**\n"
        desc += ("\n".join(winners) if winners else "Không có ai thắng!") + "\n\n"
        desc += f"💀 **Danh sách RA ĐÊ ({len(losers)} người):**\n"
        desc += ("\n".join(losers) if losers else "Không có ai thua!")

        embed_res = discord.Embed(
            title="🎲 KẾT QUẢ MỞ BÁT TÀI XỈU LÀNG 🎲",
            description=desc,
            color=discord.Color.green() if winners else discord.Color.red()
        )
        embed_res.set_footer(text="Thuế thắng cược: 10% nộp vào Kho Bạc Bot")
        await ctx.send(embed=embed_res)

    @commands.command(name="txb", aliases=["txbet"])
    async def cmd_txb(self, ctx, amount: str, choice: str):
        guild_id = ctx.guild.id
        if guild_id not in self.active_tx_rooms:
            await ctx.send("❌ Chưa có bàn Tài Xỉu nào mở! Gõ `!txopen` để mở bàn.")
            return

        choice = choice.lower()
        if choice in ["t", "tai", "tài"]:
            side = "tai"
        elif choice in ["x", "xiu", "xỉu"]:
            side = "xiu"
        else:
            await ctx.send("❌ Chọn `t` (Tài) hoặc `x` (Xỉu)!")
            return

        data = load_db()

        # 🚨 KIỂM TRA PHONG TỎA NỢ XẤU
        d_debt, _, _, d_over = calculate_loan_debt(data, ctx.author.id)
        if d_over:
            await ctx.send(f"🚨 **TÀI KHOẢN ĐÃ BỊ PHONG TỎA!** Bạn đang nợ quá hạn **{d_debt:,}** {COIN}. Hãy trả nợ (`!trano`) trước!")
            return

        u = get_user(data, ctx.author.id)
        bet_val = parse_amount(amount, u.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!txb 500m t`, `!txb 10b x`, `!txb all t`)")
            return

        if u.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}")
            return

        u["wallet"] -= bet_val
        save_db(data)

        room = self.active_tx_rooms[guild_id]
        room[side][ctx.author.id] = room[side].get(ctx.author.id, 0) + bet_val
        side_text = "🔴 TÀI" if side == "tai" else "🟢 XỈU"
        await ctx.send(f"✅ {ctx.author.mention} đã đặt cược **{bet_val:,}** {COIN} vào cửa **{side_text}**!")


async def setup(bot):
    await bot.add_cog(Multiplayer(bot))
