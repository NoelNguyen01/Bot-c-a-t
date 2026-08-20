# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional
from cogs.database import load_db, save_db, get_user, add_to_treasury, calculate_win_rate, apply_bank_tax

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

        # Luật Nhà Cái: Thắng khi d_val > p_val HOẶC Hòa điểm
        if d_val > 21 or (p_val > d_val and p_val <= 21):
            raw_profit = self.bet
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            u["wallet"] += net_profit
            add_to_treasury(data, tax)
            outcome = f"🎉 **BẠN ĐÃ CHIẾN THẮNG ({p_val} vs {d_val})!**\n" \
                      f"🏆 Thắng nhận: **+{net_profit:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.green()
        else:
            u["wallet"] -= self.bet
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
    async def cmd_tx(self, ctx, amount: int, choice: str):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        choice = choice.lower()
        if choice in ["t", "tai", "tài"]:
            user_choice = "tai"
        elif choice in ["x", "xiu", "xỉu"]:
            user_choice = "xiu"
        else:
            await ctx.send("❌ Vui lòng chọn `t` (Tài) hoặc `x` (Xỉu)!")
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        # Tính tỷ lệ thắng động
        win_prob = calculate_win_rate(data, ctx.author.id, amount)
        user_won = (random.random() < win_prob)

        # Sinh xúc xắc phù hợp với kết quả
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
            # Người chơi thua -> Ra ngược lại hoặc ra BÃO (nhà cái ăn sạch)
            if random.random() < 0.15:  # 15% cơ hội ra Bão nuốt trọn
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
            u["wallet"] -= amount
            msg = f"🌪️ **BÃO XÚC XẮC 3 CON {d1}!**\n💀 Nhà cái hốt trọn ổ cả làng! Mất **-{amount:,}** {COIN}!"
            color = discord.Color.red()
        elif user_won:
            tax = int(amount * 0.10)
            net_win = amount - tax
            u["wallet"] += net_win
            add_to_treasury(data, tax)
            msg = f"🎉 **BẠN ĐOÁN ĐÚNG ({actual.upper()})!**\n🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= amount
            msg = f"💀 **BẠN ĐOÁN SAI ({actual.upper()})!**\n💸 Mất **-{amount:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎲 SÒNG BẠC TÀI XỈU 🎲",
            description=f"**Người chơi:** {ctx.author.mention} | **Cược:** **{amount:,}** {COIN} vào **{user_choice.upper()}**\n\n"
                        f"{d_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng cược: 10% nộp vào Kho Bạc Bot • Tỷ lệ thắng tự động điều chỉnh theo mức cược!")
        await ctx.send(embed=embed)

    @app_commands.command(name="taixiu", description="Đổ xúc xắc Tài Xỉu (Xỉu: 4-10, Tài: 11-17, Bão: Nhà cái ăn sạch)")
    @app_commands.choices(lua_chon=[
        app_commands.Choice(name="🟢 Xỉu (4 - 10 điểm)", value="xiu"),
        app_commands.Choice(name="🔴 Tài (11 - 17 điểm)", value="tai")
    ])
    async def slash_tx(self, interaction: discord.Interaction, tien_cuoc: int, lua_chon: app_commands.Choice[str]):
        if tien_cuoc <= 0:
            await interaction.response.send_message("❌ Tiền cược phải lớn hơn 0!", ephemeral=True)
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, interaction.user.id)

        if u.get("wallet", 0) < tien_cuoc:
            await interaction.response.send_message(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}", ephemeral=True)
            return

        user_choice = lua_chon.value
        win_prob = calculate_win_rate(data, interaction.user.id, tien_cuoc)
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
            u["wallet"] -= tien_cuoc
            msg = f"🌪️ **BÃO XÚC XẮC 3 CON {d1}!**\n💀 Nhà cái hốt trọn ổ! Mất **-{tien_cuoc:,}** {COIN}!"
            color = discord.Color.red()
        elif user_won:
            tax = int(tien_cuoc * 0.10)
            net_win = tien_cuoc - tax
            u["wallet"] += net_win
            add_to_treasury(data, tax)
            msg = f"🎉 **BẠN ĐOÁN ĐÚNG ({actual.upper()})!**\n🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= tien_cuoc
            msg = f"💀 **BẠN ĐOÁN SAI ({actual.upper()})!**\n💸 Mất **-{tien_cuoc:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎲 SÒNG BẠC TÀI XỈU 🎲",
            description=f"**Người chơi:** {interaction.user.mention} | **Cược:** **{tien_cuoc:,}** {COIN} vào **{lua_chon.name}**\n\n"
                        f"{d_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng cược: 10% nộp vào Kho Bạc Bot")
        await interaction.response.send_message(embed=embed)

    # ================= 2. XÌ DÁCH BLACKJACK =================
    @commands.command(name="bj", aliases=["blackjack", "xidach"])
    async def cmd_bj(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        p_hand = [draw_card(), draw_card()]
        d_hand = [draw_card(), draw_card()]

        if calculate_hand(p_hand) == 21:
            raw_profit = int(amount * 1.5)
            tax = int(raw_profit * 0.10)
            net_profit = raw_profit - tax
            u["wallet"] += net_profit
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

        view = BlackjackView(ctx.author, amount, p_hand, d_hand)
        embed = view.build_embed()
        await ctx.send(embed=embed, view=view)

    # ================= 3. TUNG ĐỒNG XU COINFLIP =================
    @commands.command(name="cf", aliases=["coinflip", "flip"])
    async def cmd_cf(self, ctx, amount: int, choice: str):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        choice = choice.lower()
        if choice in ["s", "sap", "sấp"]:
            user_choice = "sap"
        elif choice in ["n", "ngua", "ngửa"]:
            user_choice = "ngua"
        else:
            await ctx.send("❌ Chọn `s` (Sấp) hoặc `n` (Ngửa)!")
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        win_prob = calculate_win_rate(data, ctx.author.id, amount)
        user_won = (random.random() < win_prob)
        actual = user_choice if user_won else ("ngua" if user_choice == "sap" else "sap")
        coin_icon = "⚪ **MẶT SẤP**" if actual == "sap" else "🟡 **MẶT NGỬA**"

        if user_won:
            tax = int(amount * 0.10)
            net_win = amount - tax
            u["wallet"] += net_win
            add_to_treasury(data, tax)
            msg = f"🎉 **ĐOÁN ĐÚNG!** Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= amount
            msg = f"💀 **ĐOÁN SAI!** Mất **-{amount:,}** {COIN}!"
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🪙 TUNG ĐỒNG XU MAY RỦI 🪙",
            description=f"Kết quả rơi xuống: {coin_icon}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% • Tỷ lệ thắng giảm khi cược to!")
        await ctx.send(embed=embed)

    # ================= 4. QUAY HŨ SLOTS =================
    @commands.command(name="slot", aliases=["slots"])
    async def cmd_slot(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        win_prob = calculate_win_rate(data, ctx.author.id, amount)
        user_won = (random.random() < win_prob)

        symbols = ["🍎", "🍋", "🍇", "💎", "7️⃣", "👑", "💀", "💩", "🤡"]

        if user_won:
            if random.random() < 0.15:  # Jackpot 3 hình
                s1 = random.choice(["7️⃣", "👑", "💎"])
                s2, s3 = s1, s1
            else:  # Trúng 2 hình
                s1 = random.choice(["🍎", "🍋", "🍇", "💎"])
                s2 = s1
                s3 = random.choice([s for s in symbols if s != s1])
        else:  # 100% thua (3 hình khác nhau)
            sample = random.sample(symbols, 3)
            s1, s2, s3 = sample[0], sample[1], sample[2]

        slot_str = f"╭──────────╮\n│  {s1} │ {s2} │ {s3}  │\n╰──────────╯"

        if s1 == s2 == s3:
            raw_win = amount * 10 if s1 in ["7️⃣", "👑"] else amount * 5
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            add_to_treasury(data, tax)
            msg = f"💥 **JACKPOT NỔ HŨ THẦN THÁNH!**\n🎉 Thắng nhận: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.gold()
        elif s1 == s2 or s2 == s3 or s1 == s3:
            raw_win = int(amount * 1.5)
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            add_to_treasury(data, tax)
            msg = f"✨ **TRÚNG 2 HÌNH!**\n🎉 Thắng nhận: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= amount
            msg = f"💀 Không trúng hình nào! Mất **-{amount:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎰 MÁY XÈNG QUAY HŨ (SLOTS) 🎰",
            description=f"{slot_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% • Tỷ lệ nổ hũ dựa trên số tiền cược!")
        await ctx.send(embed=embed)

    # ================= 5. BẦU CUA =================
    @commands.command(name="baucua", aliases=["bc"])
    async def cmd_baucua(self, ctx, amount: int, choice: str):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
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

        data = load_db()
        apply_bank_tax(data)
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Ví không đủ tiền! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        all_animals = ["🍐 Bầu", "🦀 Cua", "🦐 Tôm", "🐟 Cá", "🐔 Gà", "🦌 Nai"]
        chosen_animal = bc_map[choice_key]

        win_prob = calculate_win_rate(data, ctx.author.id, amount)
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
            raw_win = amount * match_count
            tax = int(raw_win * 0.10)
            net_win = raw_win - tax
            u["wallet"] += net_win
            add_to_treasury(data, tax)
            msg = f"🎉 **TRÚNG {match_count} CON {chosen_animal}!**\n" \
                  f"🏆 Thắng: **+{net_win:,}** {COIN} *(Thuế 10%: -{tax:,} {COIN})*!"
            color = discord.Color.green()
        else:
            u["wallet"] -= amount
            msg = f"💀 **TRẬT LẤT!** Mất **-{amount:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🦞 SÒNG BẠC BẦU CUA TÔM CÁ 🎲",
            description=f"**Người chơi:** {ctx.author.mention} | **Cược:** **{amount:,}** {COIN} vào **{chosen_animal}**\n\n"
                        f"🎲 **Kết quả:** [ {d_str} ]\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        embed.set_footer(text="Thuế thắng: 10% nộp vào Kho Bạc Bot")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Casino(bot))
