# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional
from cogs.database import load_db, save_db, get_user

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
            val += 11
        else:
            val += int(rank)
    while val > 21 and aces > 0:
        val -= 10
        aces -= 1
    return val


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
        embed.set_footer(text="Bấm 'Rút Bài' để lấy thêm lá hoặc 'Dằn Bài' để so điểm!")
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
                outcome=f"💥 **BẠN ĐÃ BỊ QUẮC (> 21 điểm)!**\n💸 Bạn đã mất **-{self.bet:,}** {COIN}! Ví còn: **{u['wallet']:,}** {COIN}.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        elif len(self.player_hand) == 5:
            self.finished = True
            for child in self.children:
                child.disabled = True
            
            win = int(self.bet * 1.5)
            u["wallet"] += win
            save_db(data)
            embed = self.build_embed(
                show_dealer=True,
                outcome=f"🌟 **NGŨ LINH THẦN THÁNH!**\n🎉 Bạn nhận **+{win:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}.",
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

        if d_val > 21 or p_val > d_val:
            u["wallet"] += self.bet
            outcome = f"🎉 **BẠN ĐÃ CHIẾN THẮNG!**\n🏆 Thắng nhận **+{self.bet:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.green()
        elif p_val < d_val:
            u["wallet"] -= self.bet
            outcome = f"💀 **NHÀ CÁI THẮNG ({d_val} vs {p_val})!**\n💸 Mất **-{self.bet:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}."
            color = discord.Color.red()
        else:
            outcome = f"🤝 **HÒA ĐIỂM ({p_val} vs {d_val})!** Hoàn lại tiền cược."
            color = discord.Color.yellow()

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
        u = get_user(data, ctx.author.id)
        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2 + d3
        d_str = f"🎲 `{d1}` + `{d2}` + `{d3}` = **{total} điểm**"
        actual = "xiu" if total <= 10 else "tai"
        is_bao = (d1 == d2 == d3)

        if is_bao:
            if user_choice == actual:
                win = amount * 3
                u["wallet"] += win
                msg = f"🌪️ **BÃO XÚC XẮC 3 CON {d1}!**\n🎉 Thắng gấp 3: **+{win:,}** {COIN}!"
            else:
                u["wallet"] -= amount
                msg = f"🌪️ **BÃO XÚC XẮC 3 CON {d1}!**\n💀 Nhà cái hốt trọn ổ! Mất **-{amount:,}** {COIN}!"
        elif user_choice == actual:
            u["wallet"] += amount
            msg = f"🎉 **BẠN ĐOÁN ĐÚNG ({actual.upper()})!**\n🏆 Thắng **+{amount:,}** {COIN}!"
        else:
            u["wallet"] -= amount
            msg = f"💀 **BẠN ĐOÁN SAI ({actual.upper()})!**\n💸 Mất **-{amount:,}** {COIN}!"

        save_db(data)
        embed = discord.Embed(
            title="🎲 SÒNG BẠC TÀI XỈU 🎲",
            description=f"**Người chơi:** {ctx.author.mention} | **Cược:** **{amount:,}** {COIN} vào **{user_choice.upper()}**\n\n"
                        f"{d_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=discord.Color.green() if user_choice == actual else discord.Color.red()
        )
        await ctx.send(embed=embed)

    # ================= 2. XÌ DÁCH BLACKJACK =================
    @commands.command(name="bj", aliases=["blackjack", "xidach"])
    async def cmd_bj(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        u = get_user(data, ctx.author.id)
        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        p_hand = [draw_card(), draw_card()]
        d_hand = [draw_card(), draw_card()]

        if calculate_hand(p_hand) == 21:
            win = int(amount * 1.5)
            u["wallet"] += win
            save_db(data)
            embed = discord.Embed(
                title="🃏 XÌ DÁCH TỰ NHIÊN (BLACKJACK)! 🌟",
                description=f"**Bài Của Bạn:** {' '.join(card_to_str(c) for c in p_hand)} `(21 ĐIỂM)`\n"
                            f"🏆 Thắng gấp rưỡi: **+{win:,}** {COIN}! Ví: **{u['wallet']:,}** {COIN}",
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
        u = get_user(data, ctx.author.id)
        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        actual = random.choice(["sap", "ngua"])
        coin_icon = "⚪ **MẶT SẤP**" if actual == "sap" else "🟡 **MẶT NGỬA**"

        if user_choice == actual:
            u["wallet"] += amount
            msg = f"🎉 **ĐOÁN ĐÚNG!** Thắng **+{amount:,}** {COIN}!"
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
        await ctx.send(embed=embed)

    # ================= 4. QUAY HŨ SLOTS =================
    @commands.command(name="slot", aliases=["slots"])
    async def cmd_slot(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        u = get_user(data, ctx.author.id)
        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        symbols = ["🍎", "🍋", "🍇", "💎", "7️⃣", "👑"]
        s1, s2, s3 = random.choice(symbols), random.choice(symbols), random.choice(symbols)
        slot_str = f"╭──────────╮\n│  {s1} │ {s2} │ {s3}  │\n╰──────────╯"

        if s1 == s2 == s3:
            if s1 == "7️⃣" or s1 == "👑":
                win = amount * 10
                msg = f"💥 **JACKPOT ĐẶC BIỆT!** Thắng gấp 10: **+{win:,}** {COIN}!"
            else:
                win = amount * 5
                msg = f"🎉 **TRÚNG 3 HÌNH GIỐNG NHAU!** Thắng gấp 5: **+{win:,}** {COIN}!"
            u["wallet"] += win
            color = discord.Color.gold()
        elif s1 == s2 or s2 == s3 or s1 == s3:
            win = int(amount * 1.5)
            u["wallet"] += win
            msg = f"✨ **TRÚNG 2 HÌNH!** Thắng: **+{win:,}** {COIN}!"
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
        await ctx.send(embed=embed)

    # ================= 5. BẦU CUA TÔM CÁ =================
    @commands.command(name="baucua", aliases=["bc"])
    async def cmd_baucua(self, ctx, amount: int, con: str):
        valid = {"bau": "Bầu 🍐", "cua": "Cua 🦀", "tom": "Tôm 🦐", "ca": "Cá 🐟", "ga": "Gà 🐓", "nai": "Nai 🦌"}
        con = con.lower()
        if con not in valid:
            await ctx.send("❌ Chọn 1 trong các con: `bau`, `cua`, `tom`, `ca`, `ga`, `nai`!")
            return

        data = load_db()
        u = get_user(data, ctx.author.id)
        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        items = ["bau", "cua", "tom", "ca", "ga", "nai"]
        r1, r2, r3 = random.choice(items), random.choice(items), random.choice(items)
        matches = [r1, r2, r3].count(con)

        res_str = f"{valid[r1]} | {valid[r2]} | {valid[r3]}"
        if matches > 0:
            win = amount * matches
            u["wallet"] += win
            msg = f"🎉 **TRÚNG {matches} CON {valid[con]}!** Nhận **+{win:,}** {COIN}!"
            color = discord.Color.green()
        else:
            u["wallet"] -= amount
            msg = f"💀 **TRẬT LỦI!** Mất **-{amount:,}** {COIN}."
            color = discord.Color.red()

        save_db(data)
        embed = discord.Embed(
            title="🎲 BẦU CUA TÔM CÁ 🎲",
            description=f"Kết quả mở bát: {res_str}\n\n{msg}\n💰 Ví hiện tại: **{u['wallet']:,}** {COIN}",
            color=color
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Casino(bot))
