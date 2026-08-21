# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional
from cogs.database import load_db, save_db, get_user, add_to_treasury, calculate_win_rate, apply_bank_tax, calculate_loan_debt, parse_amount

COIN = "💵"

SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def draw_card():
    return (random.choice(RANKS), random.choice(SUITS))

def card_to_str(card):
    return f"`{card[0]}{card[1]}`"

def calculate_hand(hand):
    val = 0
    aces = 0
    for rank, _ in hand:
        if rank in ['10', 'J', 'Q', 'K']:
            val += 10
        elif rank == 'A':
            val += 11
            aces += 1
        else:
            val += int(rank)
    while val > 21 and aces > 0:
        val -= 10
        aces -= 1
    return val

def is_xi_bang(hand):
    return len(hand) == 2 and hand[0][0] == 'A' and hand[1][0] == 'A'

def is_xi_dach(hand):
    if len(hand) != 2:
        return False
    ranks = [hand[0][0], hand[1][0]]
    has_ace = ('A' in ranks)
    has_ten = (ranks[0] in ['10', 'J', 'Q', 'K'] or ranks[1] in ['10', 'J', 'Q', 'K'])
    return has_ace and has_ten

def is_ngu_linh(hand):
    return len(hand) == 5 and calculate_hand(hand) <= 21

def get_hand_display(hand):
    val = calculate_hand(hand)
    cards_str = " ".join(card_to_str(c) for c in hand)
    if is_xi_bang(hand):
        return f"{cards_str} `(XÌ BÀNG 🌟🌟)`"
    if is_xi_dach(hand):
        return f"{cards_str} `(XÌ DÁCH 🌟)`"
    if len(hand) == 5 and val <= 21:
        return f"{cards_str} `(NGŨ LINH {val}đ)`"
    if val > 21:
        return f"{cards_str} `(QUẮC {val}đ)`"
    return f"{cards_str} `({val} điểm)`"

def record_game(u: dict, won: bool, profit: int):
    u["casino_games"] = u.get("casino_games", 0) + 1
    if won:
        u["casino_wins"] = u.get("casino_wins", 0) + 1
    u["casino_profit"] = u.get("casino_profit", 0) + profit

def check_casino_lockout(data, user_id) -> tuple[bool, int]:
    total_debt, principal, interest, is_overdue = calculate_loan_debt(data, user_id)
    return is_overdue, total_debt


# ================= 1. VIEW XÌ DÁCH BLACKJACK =================
class BlackjackView(discord.ui.View):
    def __init__(self, cog, user: discord.Member, bet: int, player_hand: list, dealer_hand: list, message: Optional[discord.Message] = None):
        super().__init__(timeout=30.0)
        self.cog = cog
        self.user = user
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.message = message
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Bàn bài này không phải của bạn!", ephemeral=True)
            return False
        return True

    def build_embed(self, show_dealer: bool = False, outcome: str = "", color: discord.Color = discord.Color.blue()):
        p_display = get_hand_display(self.player_hand)

        if show_dealer:
            d_display = get_hand_display(self.dealer_hand)
            dealer_text = f"**Bài Nhà Cái:** {d_display}"
        else:
            dealer_text = f"**Bài Nhà Cái:** {card_to_str(self.dealer_hand[0])} `🂠` `(? điểm)`"

        embed = discord.Embed(
            title="🃏 SÒNG BẠC XÌ DÁCH (BLACKJACK) 🎰",
            description=f"**Người chơi:** {self.user.mention} | **Tiền cược:** **{self.bet:,}** {COIN}\n\n"
                        f"{dealer_text}\n"
                        f"**Bài Của Bạn:** {p_display}\n\n"
                        f"{outcome}",
            color=color
        )
        embed.set_footer(text="⏳ Đếm ngược: 30 Giây • Bấm 'Rút Bài' hoặc 'Dằn Bài' (Quá 30s bỏ ván bị xử thua mất cược!)")
        return embed

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        if self.cog and hasattr(self.cog, "active_bj_players"):
            self.cog.active_bj_players.discard(self.user.id)

        for child in self.children:
            child.disabled = True

        data = load_db()
        u = get_user(data, self.user.id)
        record_game(u, False, -self.bet)
        save_db(data)

        embed = self.build_embed(
            show_dealer=True,
            outcome=f"⏰ **HẾT GIỜ (30 GIÂY)! BẠN ĐÃ BỎ VÁN — XỬ THUA!**\n"
                    f"💸 Bạn đã mất trắng tiền cược **-{self.bet:,}** {COIN} do bỏ ván!\n"
                    f"💰 Ví hiện tại: **{u['wallet']:,}** {COIN}.",
            color=discord.Color.dark_red()
        )
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

    @discord.ui.button(label="🃏 Rút Bài (Hit)", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            return

        self.player_hand.append(draw_card())
        p_val = calculate_hand(self.player_hand)

        data = load_db()
        u = get_user(data, self.user.id)

        if p_val > 21:
            self.finished = True
            if self.cog and hasattr(self.cog, "active_bj_players"):
                self.cog.active_bj_players.discard(self.user.id)
            for child in self.children:
                child.disabled = True

            record_game(u, False, -self.bet)
            save_db(data)
            embed = self.build_embed(
                show_dealer=True,
                outcome=f"💥 **BẠN ĐÃ BỊ QUẮC ({p_val} > 21 điểm)!**\n💸 Bạn đã mất **-{self.bet:,}** {COIN}! Ví còn: **{u['wallet']:,}** {COIN}.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        elif len(self.player_hand) == 5:
            self.finished = True
            if self.cog and hasattr(self.cog, "active_bj_players"):
                self.cog.active_bj_players.discard(self.user.id)
            for child in self.children:
                child.disabled = True

            raw_profit = int(self.bet * 1.5)
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            total_return = self.bet + net_profit
            u["wallet"] += total_return
            record_game(u, True, net_profit)
            add_to_treasury(data, tax)
            save_db(data)

            embed = self.build_embed(
                show_dealer=True,
                outcome=f"🌟 **NGŨ LINH THẦN THÁNH (5 LÁ <= 21)!**\n"
                        f"🏆 Hoàn cược **+{self.bet:,}** + Thắng lãi: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                        f"💰 Tổng nhận về ví: **+{total_return:,}** {COIN} • Ví hiện tại: **{u['wallet']:,}** {COIN}.",
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🛑 Dằn Bài (Stand)", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            return
        self.finished = True
        if self.cog and hasattr(self.cog, "active_bj_players"):
            self.cog.active_bj_players.discard(self.user.id)
        for child in self.children:
            child.disabled = True

        p_val = calculate_hand(self.player_hand)
        p_ngu_linh = is_ngu_linh(self.player_hand)

        # Nhà cái rút bài: tối thiểu 17 điểm hoặc tối đa 5 lá
        while calculate_hand(self.dealer_hand) < 17 and len(self.dealer_hand) < 5:
            self.dealer_hand.append(draw_card())
        d_val = calculate_hand(self.dealer_hand)
        d_ngu_linh = is_ngu_linh(self.dealer_hand)

        data = load_db()
        u = get_user(data, self.user.id)

        # 1. So sánh trường hợp Ngũ Linh
        if p_ngu_linh and d_ngu_linh:
            if p_val < d_val:
                raw_profit = int(self.bet * 1.5)
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = self.bet + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                outcome = f"🌟 **CẢ HAI ĐỀU NGŨ LINH — BẠN THẮNG DO ÍT ĐIỂM HƠN ({p_val} < {d_val})!**\n" \
                          f"🏆 Hoàn cược + Thắng lãi: **+{total_return:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
                color = discord.Color.gold()
            elif p_val > d_val:
                record_game(u, False, -self.bet)
                outcome = f"💀 **CẢ HAI ĐỀU NGŨ LINH — NHÀ CÁI THẮNG DO ÍT ĐIỂM HƠN ({d_val} < {p_val})!**\n" \
                          f"💸 Mất **-{self.bet:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
                color = discord.Color.red()
            else:
                u["wallet"] += self.bet
                outcome = f"🤝 **CẢ HAI CÙNG NGŨ LINH BẰNG ĐIỂM ({p_val} ĐIỂM) — HÒA NHAU!**\n" \
                          f"✨ Hoàn lại tiền cược **+{self.bet:,}** {COIN}! Ví giữ nguyên: **{u['wallet']:,}** {COIN}."
                color = discord.Color.yellow()
        elif p_ngu_linh:
            raw_profit = int(self.bet * 1.5)
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            total_return = self.bet + net_profit
            u["wallet"] += total_return
            record_game(u, True, net_profit)
            add_to_treasury(data, tax)
            outcome = f"🌟 **NGŨ LINH THẦN THÁNH (5 LÁ <= 21)!**\n" \
                      f"🏆 Hoàn cược + Thắng lãi: **+{total_return:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.gold()
        elif d_ngu_linh:
            record_game(u, False, -self.bet)
            outcome = f"💀 **NHÀ CÁI ĐẠT NGŨ LINH (5 LÁ <= 21)!**\n" \
                      f"💸 Bạn mất **-{self.bet:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.red()
        else:
            # 2. So sánh điểm số thông thường
            if d_val > 21:
                raw_profit = self.bet
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = self.bet + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                outcome = f"🎉 **NHÀ CÁI ĐÃ BỊ QUẮC ({d_val} > 21) — BẠN CHIẾN THẮNG!**\n" \
                          f"🏆 Hoàn cược **+{self.bet:,}** + Thắng nhận: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*! Ví: **{u['wallet']:,}** {COIN}."
                color = discord.Color.green()
            elif p_val > d_val:
                raw_profit = self.bet
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = self.bet + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                outcome = f"🎉 **BẠN ĐÃ CHIẾN THẮNG ({p_val} vs {d_val})!**\n" \
                          f"🏆 Hoàn cược **+{self.bet:,}** + Thắng nhận: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*! Ví: **{u['wallet']:,}** {COIN}."
                color = discord.Color.green()
            elif p_val == d_val:
                u["wallet"] += self.bet
                outcome = f"🤝 **HÒA NHAU VỚI NHÀ CÁI ({p_val} vs {d_val})!**\n" \
                          f"✨ Hoàn lại tiền cược **+{self.bet:,}** {COIN}! Số dư ví: **{u['wallet']:,}** {COIN}."
                color = discord.Color.yellow()
            else:
                record_game(u, False, -self.bet)
                outcome = f"💀 **NHÀ CÁI THẮNG ({d_val} vs {p_val})!**\n" \
                          f"💸 Bạn mất **-{self.bet:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
                color = discord.Color.red()

        save_db(data)
        embed = self.build_embed(show_dealer=True, outcome=outcome, color=color)
        await interaction.response.edit_message(embed=embed, view=self)


class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_bj_players = set()

    # ================= 1. TÀI XỈU =================
    @commands.command(name="tx", aliases=["taixiu"])
    async def cmd_tx(self, ctx, amount: str, choice: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        bet_val = parse_amount(amount, u.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Số tiền cược không hợp lệ! (Ví dụ: `!tx 500k t`, `!tx 10b x`, `!tx all t`)")
            return

        choice = choice.lower()
        if choice in ["t", "tai", "tài"]:
            user_choice = "tai"
        elif choice in ["x", "xiu", "xỉu"]:
            user_choice = "xiu"
        else:
            await ctx.send("❌ Vui lòng chọn `t` (Tài) hoặc `x` (Xỉu)!")
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, ctx.author.id)
        if is_locked:
            await ctx.send(f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                           f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                           f"👉 Bắt buộc phải đi làm (`!work`, `!daily`, `!laodong`) để trả nợ (`!trano`) mới được mở lại sòng bạc!")
            return

        if u.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        win_prob = calculate_win_rate(data, ctx.author.id, bet_val)
        user_won = (random.random() < win_prob)

        if user_won:
            actual = user_choice
            is_bao = False
            if actual == "tai":
                d1, d2, d3 = random.randint(3, 6), random.randint(4, 6), random.randint(4, 6)
                if d1 == d2 == d3: d1 = (d1 % 6) + 1
            else:
                d1, d2, d3 = random.randint(1, 3), random.randint(1, 3), random.randint(1, 4)
                if d1 == d2 == d3: d1 = (d1 % 3) + 1
        else:
            if random.random() < 0.15:
                b_val = random.randint(1, 6)
                d1, d2, d3 = b_val, b_val, b_val
                is_bao = True
                actual = "xiu" if (d1 * 3) <= 10 else "tai"
            else:
                is_bao = False
                actual = "xiu" if user_choice == "tai" else "tai"
                if actual == "tai":
                    d1, d2, d3 = random.randint(3, 6), random.randint(4, 6), random.randint(4, 6)
                    if d1 == d2 == d3: d1 = (d1 % 6) + 1
                else:
                    d1, d2, d3 = random.randint(1, 3), random.randint(1, 3), random.randint(1, 4)
                    if d1 == d2 == d3: d1 = (d1 % 3) + 1

        total = d1 + d2 + d3
        d_str = f"🎲 `{d1}` + `{d2}` + `{d3}` = **{total} điểm**"

        if is_bao:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"🌪️ **BÃO XÚC XẮC 3 CON {d1}!**\n💀 Nhà cái hốt trọn ổ cả làng! Mất **-{bet_val:,}** {COIN}!"
            color = discord.Color.red()
        elif user_won:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"🎉 **BẠN ĐOÁN ĐÚNG ({actual.upper()})!**\n🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 **BẠN ĐOÁN SAI ({actual.upper()})!**\n💸 Mất **-{bet_val:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎲 SÒNG BẠC TÀI XỈU 🎲",
            description=f"**Người chơi:** {ctx.author.mention} | **Cược:** **{bet_val:,}** {COIN} vào **{user_choice.upper()}**\n\n"
                        f"{d_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng cược: 10% nộp vào Kho Bạc Bot • Hỗ trợ cược ngàn tỷ (10b, 500b, 1t)")
        await ctx.send(embed=embed)

    @app_commands.command(name="taixiu", description="Đổ xúc xắc Tài Xỉu (Hỗ trợ cược ngàn tỷ: 100k, 50m, 10b, 1t, all)")
    @app_commands.choices(lua_chon=[
        app_commands.Choice(name="🟢 Xỉu (4 - 10 điểm)", value="xiu"),
        app_commands.Choice(name="🔴 Tài (11 - 17 điểm)", value="tai")
    ])
    async def slash_tx(self, interaction: discord.Interaction, tien_cuoc: str, lua_chon: app_commands.Choice[str]):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)

        bet_val = parse_amount(tien_cuoc, u.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `10b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, interaction.user.id)
        if is_locked:
            await interaction.response.send_message(
                f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                f"👉 Bắt buộc phải đi làm (`/work`, `/daily`, `/laodong`) để trả nợ (`/trano`) mới được mở lại sòng bạc!",
                ephemeral=True
            )
            return

        if u.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        user_choice = lua_chon.value
        win_prob = calculate_win_rate(data, interaction.user.id, bet_val)
        user_won = (random.random() < win_prob)

        if user_won:
            actual = user_choice
            is_bao = False
            if actual == "tai":
                d1, d2, d3 = random.randint(3, 6), random.randint(4, 6), random.randint(4, 6)
                if d1 == d2 == d3: d1 = (d1 % 6) + 1
            else:
                d1, d2, d3 = random.randint(1, 3), random.randint(1, 3), random.randint(1, 4)
                if d1 == d2 == d3: d1 = (d1 % 3) + 1
        else:
            if random.random() < 0.15:
                b_val = random.randint(1, 6)
                d1, d2, d3 = b_val, b_val, b_val
                is_bao = True
                actual = "xiu" if (d1 * 3) <= 10 else "tai"
            else:
                is_bao = False
                actual = "xiu" if user_choice == "tai" else "tai"
                if actual == "tai":
                    d1, d2, d3 = random.randint(3, 6), random.randint(4, 6), random.randint(4, 6)
                    if d1 == d2 == d3: d1 = (d1 % 6) + 1
                else:
                    d1, d2, d3 = random.randint(1, 3), random.randint(1, 3), random.randint(1, 4)
                    if d1 == d2 == d3: d1 = (d1 % 3) + 1

        total = d1 + d2 + d3
        d_str = f"🎲 `{d1}` + `{d2}` + `{d3}` = **{total} điểm**"

        if is_bao:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"🌪️ **BÃO XÚC XẮC 3 CON {d1}!**\n💀 Nhà cái hốt trọn ổ! Mất **-{bet_val:,}** {COIN}!"
            color = discord.Color.red()
        elif user_won:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"🎉 **BẠN ĐOÁN ĐÚNG ({actual.upper()})!**\n🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 **BẠN ĐOÁN SAI ({actual.upper()})!**\n💸 Mất **-{bet_val:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎲 SÒNG BẠC TÀI XỈU 🎲",
            description=f"**Người chơi:** {interaction.user.mention} | **Cược:** **{bet_val:,}** {COIN} vào **{lua_chon.name}**\n\n"
                        f"{d_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng cược: 10% nộp vào Kho Bạc Bot")
        await interaction.response.send_message(embed=embed)

    # ================= 2. XÌ DÁCH BLACKJACK =================
    @commands.command(name="bj", aliases=["blackjack", "xidach"])
    async def cmd_bj(self, ctx, amount: str):
        if ctx.author.id in self.active_bj_players:
            await ctx.send("❌ Bạn đang có 1 ván Xì Dách đang chạy! Hãy chơi hết ván đó hoặc đợi hết 30s đếm ngược.")
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        bet_val = parse_amount(amount, u.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!bj 10m`, `!bj 5b`, `!bj all`)")
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, ctx.author.id)
        if is_locked:
            await ctx.send(f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                           f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                           f"👉 Bắt buộc phải đi làm (`!work`, `!daily`, `!laodong`) để trả nợ (`!trano`) mới được mở lại sòng bạc!")
            return

        if u.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        # 🚨 TRỪ TIỀN CƯỢC NGAY TỪ ĐẦU ĐỂ CHỐNG HỦY VÁN / SO BÀI XẤU
        u["wallet"] -= bet_val
        save_db(data)
        self.active_bj_players.add(ctx.author.id)

        p_hand = [draw_card(), draw_card()]
        d_hand = [draw_card(), draw_card()]

        p_xb = is_xi_bang(p_hand)
        p_xd = is_xi_dach(p_hand)
        d_xb = is_xi_bang(d_hand)
        d_xd = is_xi_dach(d_hand)

        # 🎯 Xử lý các thế bài đặc biệt lật bài ngay đầu ván (Xì Bàng & Xì Dách)
        if p_xb or p_xd or d_xb or d_xd:
            self.active_bj_players.discard(ctx.author.id)
            p_cards_str = get_hand_display(p_hand)
            d_cards_str = get_hand_display(d_hand)

            if p_xb and d_xb:
                # Cả 2 cùng Xì Bàng -> Hòa -> Hoàn tiền cược gốc
                u["wallet"] += bet_val
                save_db(data)
                embed = discord.Embed(
                    title="🃏 SONG LONG XÌ BÀNG HÒA NHAU! 🤝",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🤝 Cả 2 đều có Xì Bàng! Hoàn lại tiền cược **+{bet_val:,}** {COIN}.\n"
                                f"💰 Ví: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.yellow()
                )
                await ctx.send(embed=embed)
                return
            elif p_xb:
                # Người chơi Xì Bàng -> Ăn gấp đôi x2
                raw_profit = int(bet_val * 2.0)
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = bet_val + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                save_db(data)

                embed = discord.Embed(
                    title="🌟 XÌ BÀNG THẦN THÁNH (2 CÂY ÁT)! 👑",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🏆 Bạn đã hạ gục Nhà Cái! Thắng gấp đôi: Hoàn cược + Lãi **+{total_return:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                                f"💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.gold()
                )
                await ctx.send(embed=embed)
                return
            elif d_xb:
                # Nhà cái Xì Bàng (tiền cược đã trừ)
                record_game(u, False, -bet_val)
                save_db(data)

                embed = discord.Embed(
                    title="💀 NHÀ CÁI XÌ BÀNG ĂN SẠCH! 🎰",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"💸 Bạn đã mất **-{bet_val:,}** {COIN}!\n"
                                f"💰 Ví còn: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            elif p_xd and d_xd:
                # Cả 2 cùng Xì Dách -> Hòa -> Hoàn tiền cược gốc
                u["wallet"] += bet_val
                save_db(data)
                embed = discord.Embed(
                    title="🃏 CẢ HAI CÙNG XÌ DÁCH HÒA NHAU! 🤝",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🤝 Hòa nhau! Hoàn lại tiền cược **+{bet_val:,}** {COIN}.\n"
                                f"💰 Ví: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.yellow()
                )
                await ctx.send(embed=embed)
                return
            elif p_xd:
                # Người chơi Xì Dách -> Ăn gấp rưỡi x1.5
                raw_profit = int(bet_val * 1.5)
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = bet_val + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                save_db(data)

                embed = discord.Embed(
                    title="🃏 XÌ DÁCH TỰ NHIÊN (BLACKJACK 21)! 🌟",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🏆 Thắng gấp rưỡi! Hoàn cược + Lãi: **+{total_return:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                                f"💰 Ví: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.gold()
                )
                await ctx.send(embed=embed)
                return
            elif d_xd:
                # Nhà cái Xì Dách (tiền cược đã trừ)
                record_game(u, False, -bet_val)
                save_db(data)

                embed = discord.Embed(
                    title="💀 NHÀ CÁI XÌ DÁCH! 🎰",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"💸 Bạn đã mất **-{bet_val:,}** {COIN}!\n"
                                f"💰 Ví còn: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

        view = BlackjackView(self, ctx.author, bet_val, p_hand, d_hand)
        embed = view.build_embed()
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    @app_commands.command(name="blackjack", description="Đánh bài Xì Dách Blackjack (30s đếm ngược, chống thoát ván)")
    async def slash_bj(self, interaction: discord.Interaction, tien_cuoc: str):
        if interaction.user.id in self.active_bj_players:
            await interaction.response.send_message("❌ Bạn đang có 1 ván Xì Dách đang chạy! Hãy chơi hết ván đó hoặc đợi hết 30s đếm ngược.", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)

        bet_val = parse_amount(tien_cuoc, u.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `5b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, interaction.user.id)
        if is_locked:
            await interaction.response.send_message(
                f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                f"👉 Bắt buộc phải đi làm (`/work`, `/daily`, `/laodong`) để trả nợ (`/trano`) mới được mở lại sòng bạc!",
                ephemeral=True
            )
            return

        if u.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        # 🚨 TRỪ TIỀN CƯỢC NGAY TỪ ĐẦU ĐỂ CHỐNG HỦY VÁN / SO BÀI XẤU
        u["wallet"] -= bet_val
        save_db(data)
        self.active_bj_players.add(interaction.user.id)

        p_hand = [draw_card(), draw_card()]
        d_hand = [draw_card(), draw_card()]

        p_xb = is_xi_bang(p_hand)
        p_xd = is_xi_dach(p_hand)
        d_xb = is_xi_bang(d_hand)
        d_xd = is_xi_dach(d_hand)

        if p_xb or p_xd or d_xb or d_xd:
            self.active_bj_players.discard(interaction.user.id)
            p_cards_str = get_hand_display(p_hand)
            d_cards_str = get_hand_display(d_hand)

            if p_xb and d_xb:
                u["wallet"] += bet_val
                save_db(data)
                embed = discord.Embed(
                    title="🃏 SONG LONG XÌ BÀNG HÒA NHAU! 🤝",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🤝 Cả 2 đều có Xì Bàng! Hoàn lại tiền cược **+{bet_val:,}** {COIN}.\n"
                                f"💰 Ví: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.yellow()
                )
                await interaction.response.send_message(embed=embed)
                return
            elif p_xb:
                raw_profit = int(bet_val * 2.0)
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = bet_val + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                save_db(data)

                embed = discord.Embed(
                    title="🌟 XÌ BÀNG THẦN THÁNH (2 CÂY ÁT)! 👑",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🏆 Bạn đã hạ gục Nhà Cái! Thắng gấp đôi: Hoàn cược + Lãi **+{total_return:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                                f"💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed)
                return
            elif d_xb:
                record_game(u, False, -bet_val)
                save_db(data)

                embed = discord.Embed(
                    title="💀 NHÀ CÁI XÌ BÀNG ĂN SẠCH! 🎰",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"💸 Bạn đã mất **-{bet_val:,}** {COIN}!\n"
                                f"💰 Ví còn: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
                return
            elif p_xd and d_xd:
                u["wallet"] += bet_val
                save_db(data)
                embed = discord.Embed(
                    title="🃏 CẢ HAI CÙNG XÌ DÁCH HÒA NHAU! 🤝",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🤝 Hòa nhau! Hoàn lại tiền cược **+{bet_val:,}** {COIN}.\n"
                                f"💰 Ví: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.yellow()
                )
                await interaction.response.send_message(embed=embed)
                return
            elif p_xd:
                raw_profit = int(bet_val * 1.5)
                tax = int(raw_profit * 0.10)
                net_profit = raw_profit - tax
                total_return = bet_val + net_profit
                u["wallet"] += total_return
                record_game(u, True, net_profit)
                add_to_treasury(data, tax)
                save_db(data)

                embed = discord.Embed(
                    title="🃏 XÌ DÁCH TỰ NHIÊN (BLACKJACK 21)! 🌟",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                                f"🏆 Thắng gấp rưỡi! Hoàn cược + Lãi: **+{total_return:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                                f"💰 Ví: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed)
                return
            elif d_xd:
                record_game(u, False, -bet_val)
                save_db(data)

                embed = discord.Embed(
                    title="💀 NHÀ CÁI XÌ DÁCH! 🎰",
                    description=f"• **Bài Của Bạn:** {p_cards_str}\n"
                                f"• **Bài Nhà Cái:** {d_cards_str}\n\n"
                    f"💸 Bạn đã mất **-{bet_val:,}** {COIN}!\n"
                    f"💰 Ví còn: **{u['wallet']:,}** {COIN}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
                return

        view = BlackjackView(self, interaction.user, bet_val, p_hand, d_hand)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        try:
            view.message = await interaction.original_response()
        except Exception:
            pass

    # ================= 3. TUNG ĐỒNG XU COINFLIP =================
    @commands.command(name="cf", aliases=["coinflip", "flip"])
    async def cmd_cf(self, ctx, amount: str, choice: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        bet_val = parse_amount(amount, u.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!cf 10m s`, `!cf 5b n`, `!cf all s`)")
            return

        choice = choice.lower()
        if choice in ["s", "sap", "sấp"]:
            user_choice = "sap"
        elif choice in ["n", "ngua", "ngửa"]:
            user_choice = "ngua"
        else:
            await ctx.send("❌ Chọn `s` (Sấp) hoặc `n` (Ngửa)!")
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, ctx.author.id)
        if is_locked:
            await ctx.send(f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                           f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                           f"👉 Bắt buộc phải đi làm (`!work`, `!daily`, `!laodong`) để trả nợ (`!trano`) mới được mở lại sòng bạc!")
            return

        if u.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        win_prob = calculate_win_rate(data, ctx.author.id, bet_val)
        user_won = (random.random() < win_prob)
        actual = user_choice if user_won else ("ngua" if user_choice == "sap" else "sap")
        coin_icon = "⚪ **MẶT SẤP**" if actual == "sap" else "🟡 **MẶT NGỬA**"

        if user_won:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"🎉 **ĐOÁN ĐÚNG!** Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 **ĐOÁN SAI!** Mất **-{bet_val:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🪙 TUNG ĐỒNG XU MAY RỦI 🪙",
            description=f"Kết quả rơi xuống: {coin_icon}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% • Tỷ lệ thắng giảm khi cược to!")
        await ctx.send(embed=embed)

    @app_commands.command(name="coinflip", description="Tung đồng xu may rủi Sấp hoặc Ngửa")
    @app_commands.choices(lua_chon=[
        app_commands.Choice(name="⚪ Mặt Sấp", value="sap"),
        app_commands.Choice(name="🟡 Mặt Ngửa", value="ngua")
    ])
    async def slash_cf(self, interaction: discord.Interaction, tien_cuoc: str, lua_chon: app_commands.Choice[str]):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)

        bet_val = parse_amount(tien_cuoc, u.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `5b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, interaction.user.id)
        if is_locked:
            await interaction.response.send_message(
                f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                f"👉 Bắt buộc phải đi làm (`/work`, `/daily`, `/laodong`) để trả nợ (`/trano`) mới được mở lại sòng bạc!",
                ephemeral=True
            )
            return

        if u.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        user_choice = lua_chon.value
        win_prob = calculate_win_rate(data, interaction.user.id, bet_val)
        user_won = (random.random() < win_prob)
        actual = user_choice if user_won else ("ngua" if user_choice == "sap" else "sap")
        coin_icon = "⚪ **MẶT SẤP**" if actual == "sap" else "🟡 **MẶT NGỬA**"

        if user_won:
            tax = int(bet_val * 0.10)
            net_win = bet_val - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"🎉 **ĐOÁN ĐÚNG!** Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 **ĐOÁN SAI!** Mất **-{bet_val:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🪙 TUNG ĐỒNG XU MAY RỦI 🪙",
            description=f"Kết quả rơi xuống: {coin_icon}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        await interaction.response.send_message(embed=embed)

    # ================= 4. QUAY HŨ SLOTS =================
    @commands.command(name="slot", aliases=["slots"])
    async def cmd_slot(self, ctx, amount: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        bet_val = parse_amount(amount, u.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!slot 10m`, `!slot 5b`, `!slot all`)")
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, ctx.author.id)
        if is_locked:
            await ctx.send(f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                           f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                           f"👉 Bắt buộc phải đi làm (`!work`, `!daily`, `!laodong`) để trả nợ (`!trano`) mới được mở lại sòng bạc!")
            return

        if u.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        win_prob = calculate_win_rate(data, ctx.author.id, bet_val)
        user_won = (random.random() < win_prob)

        symbols = ["🍎", "🍋", "🍇", "💎", "7️⃣", "👑", "💀", "💩", "🤡"]

        # 🎯 QUY TẮC: NẾU CƯỢC TRÊN 10B (10 TỶ), TỶ LỆ RA X10 JACKPOT = 0!
        is_above_10b = (bet_val > 10_000_000_000)

        if user_won:
            if not is_above_10b and random.random() < 0.15:
                s1 = random.choice(["7️⃣", "👑"])
                s2, s3 = s1, s1
            else:
                s1 = random.choice(["🍎", "🍋", "🍇", "💎"])
                s2 = s1
                s3 = s1 if (random.random() < 0.35) else random.choice([s for s in symbols if s != s1])
        else:
            sample = random.sample(symbols, 3)
            s1, s2, s3 = sample[0], sample[1], sample[2]
            if s1 in ["7️⃣", "👑"] and s1 == s2 == s3:
                s3 = "🍎"

        slot_str = f"╭──────────╮\n│  {s1} │ {s2} │ {s3}  │\n╰──────────╯"

        if s1 == s2 == s3:
            if s1 in ["7️⃣", "👑"] and not is_above_10b:
                raw_win = bet_val * 10
            else:
                raw_win = bet_val * 5
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            tag = "💥 **JACKPOT NỔ HŨ THẦN THÁNH (X10)!**" if (s1 in ["7️⃣", "👑"] and not is_above_10b) else f"🌟 **TRÚNG 3 HÌNH {s1} (X5)!**"
            msg = f"{tag}\n🎉 Thắng nhận: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.gold()
        elif s1 == s2 or s2 == s3 or s1 == s3:
            raw_win = int(bet_val * 1.5)
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"✨ **TRÚNG 2 HÌNH (X1.5)!**\n🎉 Thắng nhận: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 Không trúng hình nào! Mất **-{bet_val:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎰 MÁY XÈNG QUAY HŨ (SLOTS) 🎰",
            description=f"{slot_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        await ctx.send(embed=embed)

    @app_commands.command(name="slots", description="Quay hũ máy xèng hoa quả trúng Jackpot")
    async def slash_slot(self, interaction: discord.Interaction, tien_cuoc: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)

        bet_val = parse_amount(tien_cuoc, u.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `5b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, interaction.user.id)
        if is_locked:
            await interaction.response.send_message(
                f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                f"👉 Bắt buộc phải đi làm (`/work`, `/daily`, `/laodong`) để trả nợ (`/trano`) mới được mở lại sòng bạc!",
                ephemeral=True
            )
            return

        if u.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        win_prob = calculate_win_rate(data, interaction.user.id, bet_val)
        user_won = (random.random() < win_prob)

        symbols = ["🍎", "🍋", "🍇", "💎", "7️⃣", "👑", "💀", "💩", "🤡"]
        is_above_10b = (bet_val > 10_000_000_000)

        if user_won:
            if not is_above_10b and random.random() < 0.15:
                s1 = random.choice(["7️⃣", "👑"])
                s2, s3 = s1, s1
            else:
                s1 = random.choice(["🍎", "🍋", "🍇", "💎"])
                s2 = s1
                s3 = s1 if (random.random() < 0.35) else random.choice([s for s in symbols if s != s1])
        else:
            sample = random.sample(symbols, 3)
            s1, s2, s3 = sample[0], sample[1], sample[2]
            if s1 in ["7️⃣", "👑"] and s1 == s2 == s3:
                s3 = "🍎"

        slot_str = f"╭──────────╮\n│  {s1} │ {s2} │ {s3}  │\n╰──────────╯"

        if s1 == s2 == s3:
            if s1 in ["7️⃣", "👑"] and not is_above_10b:
                raw_win = bet_val * 10
            else:
                raw_win = bet_val * 5
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            tag = "💥 **JACKPOT NỔ HŨ THẦN THÁNH (X10)!**" if (s1 in ["7️⃣", "👑"] and not is_above_10b) else f"🌟 **TRÚNG 3 HÌNH {s1} (X5)!**"
            msg = f"{tag}\n🎉 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.gold()
        elif s1 == s2 or s2 == s3 or s1 == s3:
            raw_win = int(bet_val * 1.5)
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"✨ **TRÚNG 2 HÌNH (X1.5)!**\n🎉 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 Không trúng hình nào! Mất **-{bet_val:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎰 MÁY XÈNG QUAY HŨ (SLOTS) 🎰",
            description=f"{slot_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        await interaction.response.send_message(embed=embed)

    # ================= 5. BẦU CUA =================
    @commands.command(name="baucua", aliases=["bc"])
    async def cmd_baucua(self, ctx, amount: str, choice: str):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        bet_val = parse_amount(amount, u.get("wallet", 0))
        if bet_val <= 0:
            await ctx.send("❌ Tiền cược không hợp lệ! (Ví dụ: `!bc 10m bau`, `!bc 5b cua`, `!bc all tom`)")
            return

        bc_map = {
            "bau": "🍐 Bầu", "bầu": "🍐 Bầu",
            "cua": "🦀 Cua",
            "tom": "🦐 Tôm", "tôm": "🦐 Tôm",
            "ca": "🐟 Cá", "cá": "🐟 Cá",
            "ga": "🐔 Gà", "gà": "🐔 Gà",
            "nai": "🦌 Nai"
        }
        choice_key = choice.lower()
        if choice_key not in bc_map:
            await ctx.send("❌ Chọn: `bau`, `cua`, `tom`, `ca`, `ga`, `nai`!")
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, ctx.author.id)
        if is_locked:
            await ctx.send(f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                           f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                           f"👉 Bắt buộc phải đi làm (`!work`, `!daily`, `!laodong`) để trả nợ (`!trano`) mới được mở lại sòng bạc!")
            return

        if u.get("wallet", 0) < bet_val:
            await ctx.send(f"❌ Ví không đủ tiền! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        all_animals = ["🍐 Bầu", "🦀 Cua", "🦐 Tôm", "🐟 Cá", "🐔 Gà", "🦌 Nai"]
        chosen_animal = bc_map[choice_key]

        win_prob = calculate_win_rate(data, ctx.author.id, bet_val)
        user_won = (random.random() < win_prob)

        if user_won:
            match_count = random.choices([1, 2, 3], weights=[0.80, 0.18, 0.02])[0]
            dices = [chosen_animal] * match_count
            while len(dices) < 3:
                other = random.choice([a for a in all_animals if a != chosen_animal])
                dices.append(other)
            random.shuffle(dices)
        else:
            match_count = 0
            other_animals = [a for a in all_animals if a != chosen_animal]
            dices = [random.choice(other_animals), random.choice(other_animals), random.choice(other_animals)]

        d_str = " | ".join(dices)

        if match_count > 0:
            raw_win = bet_val * match_count
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"🎉 **TRÚNG {match_count} CON {chosen_animal}!**\n" \
                  f"🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 **TRẬT LẤT!** Mất **-{bet_val:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🦞 SÒNG BẠC BẦU CUA TÔM CÁ 🎲",
            description=f"**Người chơi:** {ctx.author.mention} | **Cược:** **{bet_val:,}** {COIN} vào **{chosen_animal}**\n\n"
                        f"🎲 **Kết quả:** [ {d_str} ]\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        await ctx.send(embed=embed)

    @app_commands.command(name="baucua", description="Đổ xúc xắc Bầu Cua Tôm Cá (Hỗ trợ cược ngàn tỷ: 10m, 5b, all)")
    @app_commands.choices(con_vat=[
        app_commands.Choice(name="🍐 Bầu", value="bau"),
        app_commands.Choice(name="🦀 Cua", value="cua"),
        app_commands.Choice(name="🦐 Tôm", value="tom"),
        app_commands.Choice(name="🐟 Cá", value="ca"),
        app_commands.Choice(name="🐔 Gà", value="ga"),
        app_commands.Choice(name="🦌 Nai", value="nai")
    ])
    async def slash_baucua(self, interaction: discord.Interaction, tien_cuoc: str, con_vat: app_commands.Choice[str]):
        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)

        bet_val = parse_amount(tien_cuoc, u.get("wallet", 0))
        if bet_val <= 0:
            await interaction.response.send_message("❌ Tiền cược không hợp lệ! (Ví dụ: `500k`, `10m`, `5b`, `all`)", ephemeral=True)
            return

        # 🚨 KIỂM TRA PHONG TỎA DO NỢ XẤU
        is_locked, tot_debt = check_casino_lockout(data, interaction.user.id)
        if is_locked:
            await interaction.response.send_message(
                f"🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n"
                f"💀 Bạn đang có khoản nợ quá hạn tại Ngân Hàng: **{tot_debt:,}** {COIN}!\n"
                f"👉 Bắt buộc phải đi làm (`/work`, `/daily`, `/laodong`) để trả nợ (`/trano`) mới được mở lại sòng bạc!",
                ephemeral=True
            )
            return

        if u.get("wallet", 0) < bet_val:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        all_animals = ["🍐 Bầu", "🦀 Cua", "🦐 Tôm", "🐟 Cá", "🐔 Gà", "🦌 Nai"]
        chosen_animal = con_vat.name

        win_prob = calculate_win_rate(data, interaction.user.id, bet_val)
        user_won = (random.random() < win_prob)

        if user_won:
            match_count = random.choices([1, 2, 3], weights=[0.80, 0.18, 0.02])[0]
            dices = [chosen_animal] * match_count
            while len(dices) < 3:
                other = random.choice([a for a in all_animals if a != chosen_animal])
                dices.append(other)
            random.shuffle(dices)
        else:
            match_count = 0
            other_animals = [a for a in all_animals if a != chosen_animal]
            dices = [random.choice(other_animals), random.choice(other_animals), random.choice(other_animals)]

        d_str = " | ".join(dices)

        if match_count > 0:
            raw_win = bet_val * match_count
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            record_game(u, True, net_win)
            add_to_treasury(data, tax)
            msg = f"🎉 **TRÚNG {match_count} CON {chosen_animal}!**\n" \
                  f"🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= bet_val
            record_game(u, False, -bet_val)
            msg = f"💀 **TRẬT LẤT!** Mất **-{bet_val:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🦞 SÒNG BẠC BẦU CUA TÔM CÁ 🎲",
            description=f"**Người chơi:** {interaction.user.mention} | **Cược:** **{bet_val:,}** {COIN} vào **{chosen_animal}**\n\n"
                        f"🎲 **Kết quả:** [ {d_str} ]\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Casino(bot))
