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
        if rank in ['J', 'Q', 'K']:
            val += 10
        elif rank == 'A':
            aces += 1
        elif rank == '10':
            val += 10
        else:
            val += int(rank)
    while val > 21 and aces > 0:
        val -= 10
        aces -= 1
    return val

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
    def __init__(self, user: discord.Member, bet: int, player_hand: list, dealer_hand: list):
        super().__init__(timeout=60.0)
        self.user = user
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Bàn bài này không phải của bạn!", ephemeral=True)
            return False
        return True

    def build_embed(self, show_dealer: bool = False, outcome: str = "", color: discord.Color = discord.Color.blue()):
        p_val = calculate_hand(self.player_hand)
        p_cards = " ".join(card_to_str(c) for c in self.player_hand)

        if show_dealer:
            d_val = calculate_hand(self.dealer_hand)
            d_cards = " ".join(card_to_str(c) for c in self.dealer_hand)
            dealer_text = f"**Bài Nhà Cái:** {d_cards} `({d_val} điểm)`"
        else:
            dealer_text = f"**Bài Nhà Cái:** {card_to_str(self.dealer_hand[0])} `🂠` `(? điểm)`"

        embed = discord.Embed(
            title="🃏 SÒNG BẠC XÌ DÁCH (BLACKJACK) 🎰",
            description=f"**Người chơi:** {self.user.mention} | **Tiền cược:** **{self.bet:,}** {COIN}\n\n"
                        f"{dealer_text}\n"
                        f"**Bài Của Bạn:** {p_cards} `({p_val} điểm)`\n\n"
                        f"{outcome}",
            color=color
        )
        embed.set_footer(text="Bấm 'Rút Bài' để lấy thêm lá hoặc 'Dằn Bài' để so điểm! (Thuế thắng cược: 10%)")
        return embed

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
            for child in self.children:
                child.disabled = True
            
            u["wallet"] -= self.bet
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
            for child in self.children:
                child.disabled = True
            
            raw_profit = int(self.bet * 1.5)
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            u["wallet"] += net_profit
            record_game(u, True, net_profit)
            add_to_treasury(data, tax)
            save_db(data)

            embed = self.build_embed(
                show_dealer=True,
                outcome=f"🌟 **NGŨ LINH THẦN THÁNH (5 LÁ)!**\n"
                        f"🎉 Bạn nhận **+{net_profit:,}** {COIN} *(Đã khấu trừ 10% thuế: -{tax:,} {COIN})*!\n"
                        f"💰 Ví hiện tại: **{u['wallet']:,}** {COIN}.",
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
        for child in self.children:
            child.disabled = True

        p_val = calculate_hand(self.player_hand)
        while calculate_hand(self.dealer_hand) < 17 and len(self.dealer_hand) < 5:
            self.dealer_hand.append(draw_card())
        d_val = calculate_hand(self.dealer_hand)

        data = load_db()
        u = get_user(data, self.user.id)

        if d_val > 21 or (p_val > d_val and p_val <= 21):
            raw_profit = self.bet
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            u["wallet"] += net_profit
            record_game(u, True, net_profit)
            add_to_treasury(data, tax)
            outcome = f"🎉 **BẠN ĐÃ CHIẾN THẮNG ({p_val} vs {d_val})!**\n" \
                      f"🏆 Thắng nhận: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.green()
        else:
            u["wallet"] -= self.bet
            record_game(u, False, -self.bet)
            outcome = f"💀 **NHÀ CÁI THẮNG ({d_val} vs {p_val})!**\n💸 Bạn mất **-{self.bet:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = self.build_embed(show_dealer=True, outcome=outcome, color=color)
        await interaction.response.edit_message(embed=embed, view=self)


class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

        p_hand = [draw_card(), draw_card()]
        d_hand = [draw_card(), draw_card()]

        if calculate_hand(p_hand) == 21:
            raw_profit = int(bet_val * 1.5)
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            u["wallet"] += net_profit
            record_game(u, True, net_profit)
            add_to_treasury(data, tax)
            save_db(data)

            embed = discord.Embed(
                title="🃏 XÌ DÁCH TỰ NHIÊN (BLACKJACK 21)! 🌟",
                description=f"**Bài Của Bạn:** {' '.join(card_to_str(c) for c in p_hand)} `(21 ĐIỂM)`\n"
                            f"🏆 Thắng gấp rưỡi: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                            f"💰 Ví: **{u['wallet']:,}** {COIN}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        view = BlackjackView(ctx.author, bet_val, p_hand, d_hand)
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="blackjack", description="Đánh bài Xì Dách Blackjack (Hỗ trợ cược ngàn tỷ: 10m, 5b, all)")
    async def slash_bj(self, interaction: discord.Interaction, tien_cuoc: str):
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

        p_hand = [draw_card(), draw_card()]
        d_hand = [draw_card(), draw_card()]

        if calculate_hand(p_hand) == 21:
            raw_profit = int(bet_val * 1.5)
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            u["wallet"] += net_profit
            record_game(u, True, net_profit)
            add_to_treasury(data, tax)
            save_db(data)

            embed = discord.Embed(
                title="🃏 XÌ DÁCH TỰ NHIÊN (BLACKJACK 21)! 🌟",
                description=f"**Bài Của Bạn:** {' '.join(card_to_str(c) for c in p_hand)} `(21 ĐIỂM)`\n"
                            f"🏆 Thắng gấp rưỡi: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!\n"
                            f"💰 Ví: **{u['wallet']:,}** {COIN}",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed)
            return

        view = BlackjackView(interaction.user, bet_val, p_hand, d_hand)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)

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
            # Đảm bảo thua không vô tình ra 3 hình x10
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
        footer_note = "Thuế thắng: 10% • Cược trên 10 Tỷ: Khóa Jackpot x10 chống phá sản ngân khố!" if is_above_10b else "Thuế thắng: 10% • Tỷ lệ nổ hũ x10 khi cược dưới 10 Tỷ!"
        embed = discord.Embed(
            title="🎰 MÁY XÈNG QUAY HŨ (SLOTS) 🎰",
            description=f"{slot_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text=footer_note)
        await ctx.send(embed=embed)

    @app_commands.command(name="slots", description="Quay hũ máy xèng hoa quả (Cược > 10B khóa x10 jackpot)")
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
        footer_note = "Thuế thắng: 10% • Cược trên 10 Tỷ: Khóa Jackpot x10 chống phá sản ngân khố!" if is_above_10b else "Thuế thắng: 10% • Tỷ lệ nổ hũ x10 khi cược dưới 10 Tỷ!"
        embed = discord.Embed(
            title="🎰 MÁY XÈNG QUAY HŨ (SLOTS) 🎰",
            description=f"{slot_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text=footer_note)
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
