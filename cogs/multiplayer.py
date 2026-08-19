# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user

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
                u1["wallet"] += self.bet
                u2["wallet"] -= self.bet
                result_text = f"🏆 **{self.p1.mention} CHIẾN THẮNG!**\n" \
                              f"• {self.p1.display_name}: {choice_icons[c1]}\n" \
                              f"• {self.p2.display_name}: {choice_icons[c2]}\n\n" \
                              f"💰 {self.p1.mention} nhận **+{self.bet:,}** {COIN} từ {self.p2.mention}!"
                color = discord.Color.green()
            else:
                u2["wallet"] += self.bet
                u1["wallet"] -= self.bet
                result_text = f"🏆 **{self.p2.mention} CHIẾN THẮNG!**\n" \
                              f"• {self.p2.display_name}: {choice_icons[c2]}\n" \
                              f"• {self.p1.display_name}: {choice_icons[c1]}\n\n" \
                              f"💰 {self.p2.mention} nhận **+{self.bet:,}** {COIN} từ {self.p1.mention}!"
                color = discord.Color.green()

            save_db(data)
            embed = discord.Embed(
                title="✂️ KẾT QUẢ KÉO BÚA BAO SOLO 🪨",
                description=result_text,
                color=color
            )
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


# ================= 2. PHÁT BAO LÌ XÌ NHIỀU NGƯỜI (LIXI VIEW) =================
class LiXiView(discord.ui.View):
    def __init__(self, sender: discord.Member, total_money: int, total_slots: int):
        super().__init__(timeout=120.0)
        self.sender = sender
        self.total_money = total_money
        self.total_slots = total_slots
        self.claimed_users = {}
        self.remaining_money = total_money
        self.remaining_slots = total_slots

    @discord.ui.button(label="🧧 Giật Lì Xì Nhanh!", style=discord.ButtonStyle.danger, custom_id="btn_claim_lixi")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        u = get_user(data, interaction.user.id)
        u["wallet"] = u.get("wallet", 0) + amount
        save_db(data)

        await interaction.response.send_message(f"🎉 Bạn giật được **+{amount:,}** {COIN} từ bao lì xì của {self.sender.display_name}!", ephemeral=True)

        # Cập nhật danh sách người đã giật
        desc = f"🧧 **{self.sender.mention}** đã phát bao lì xì tổng cộng **{self.total_money:,}** {COIN} cho **{self.total_slots} người**!\n\n"
        desc += f"📊 **Còn lại:** **{self.remaining_money:,}** {COIN} ({self.remaining_slots}/{self.total_slots} phần)\n\n"
        desc += "**🏆 Danh sách cao thủ giật nhanh:**\n"
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


class Multiplayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tx_rooms = {}  # guild_id: room_data

    # ================= 1. KÉO BÚA BAO SOLO PVP =================
    @commands.command(name="rps", aliases=["keobuabao", "kbb"])
    async def cmd_rps(self, ctx, opponent: discord.Member, bet: int = 1000):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.send("❌ Đối thủ không hợp lệ!")
            return
        if bet <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        u1 = get_user(data, ctx.author.id)
        u2 = get_user(data, opponent.id)

        if u1.get("wallet", 0) < bet:
            await ctx.send(f"❌ Bạn không đủ tiền cược! (Ví: **{u1.get('wallet', 0):,}** {COIN})")
            return
        if u2.get("wallet", 0) < bet:
            await ctx.send(f"❌ {opponent.mention} không đủ tiền cược **{bet:,}** {COIN}!")
            return

        embed = discord.Embed(
            title="⚔️ THÁCH ĐẤU KÉO BÚA BAO SOLO 1V1 🪨📄✂️",
            description=f"**{ctx.author.mention}** đã thách đấu **{opponent.mention}**!\n"
                        f"💰 **Tiền cược:** **{bet:,}** {COIN}\n\n"
                        f"👉 Cả 2 hãy bấm chọn nút bên dưới (Lựa chọn được giữ bí mật 100% cho đến khi cả 2 chọn xong)!",
            color=discord.Color.blue()
        )
        view = RPSView(ctx.author, opponent, bet)
        await ctx.send(content=f"{ctx.author.mention} vs {opponent.mention}", embed=embed, view=view)

    # ================= 2. ĐỔ XÚC XẮC SOLO 1V1 =================
    @commands.command(name="dice", aliases=["xucxac", "dicesolo"])
    async def cmd_dice(self, ctx, opponent: discord.Member, bet: int = 1000):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.send("❌ Đối thủ không hợp lệ!")
            return
        if bet <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        u1 = get_user(data, ctx.author.id)
        u2 = get_user(data, opponent.id)

        if u1.get("wallet", 0) < bet or u2.get("wallet", 0) < bet:
            await ctx.send(f"❌ Một trong hai người không đủ tiền cược **{bet:,}** {COIN}!")
            return

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        if d1 > d2:
            u1["wallet"] += bet
            u2["wallet"] -= bet
            winner = ctx.author
            loser = opponent
            win_txt = f"🏆 **{winner.mention} ĐÃ THẮNG (+{bet:,} {COIN})!**"
            color = discord.Color.green()
        elif d2 > d1:
            u2["wallet"] += bet
            u1["wallet"] -= bet
            winner = opponent
            loser = ctx.author
            win_txt = f"🏆 **{winner.mention} ĐÃ THẮNG (+{bet:,} {COIN})!**"
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
        await ctx.send(embed=embed)

    # ================= 3. PHÁT BAO LÌ XÌ CẢ PHÒNG =================
    @commands.command(name="lixi", aliases=["phattien", "giveaway"])
    async def cmd_lixi(self, ctx, tong_tien: int, so_nguoi: int = 5):
        if tong_tien < 100 or so_nguoi <= 0:
            await ctx.send("❌ Tổng tiền tối thiểu 100 và số người phải lớn hơn 0!")
            return

        data = load_db()
        sender = get_user(data, ctx.author.id)

        if sender.get("wallet", 0) < tong_tien:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})")
            return

        sender["wallet"] -= tong_tien
        save_db(data)

        embed = discord.Embed(
            title="🧧 BAO LÌ XÌ MAY MẮN CẢ LÀNG 🧧",
            description=f"🧧 **{ctx.author.mention}** vừa phát bao lì xì **{tong_tien:,}** {COIN} cho **{so_nguoi} người**!\n\n"
                        f"👉 Bấm nút **'🧧 Giật Lì Xì Nhanh!'** bên dưới để giật tiền may mắn!",
            color=discord.Color.red()
        )
        view = LiXiView(ctx.author, tong_tien, so_nguoi)
        await ctx.send(embed=embed, view=view)

    # ================= 4. BÀN TÀI XỈU CẢ LÀNG CÙNG ĐẶT =================
    @commands.command(name="txopen", aliases=["bantaixiu", "txl"])
    async def cmd_txopen(self, ctx, seconds: int = 30):
        guild_id = ctx.guild.id
        if guild_id in self.active_tx_rooms:
            await ctx.send("❌ Hiện tại đang có một bàn Tài Xỉu đang mở đặt cược rồi!")
            return

        seconds = max(15, min(seconds, 90))
        self.active_tx_rooms[guild_id] = {
            "tai": {},  # user_id: amount
            "xiu": {},  # user_id: amount
            "open": True
        }

        embed = discord.Embed(
            title="🎲 BÀN TÀI XỈU CẢ LÀNG MỞ CƯỢC! 🎲",
            description=f"📢 **{ctx.author.mention}** đã mở bàn Tài Xỉu cho cả Server!\n\n"
                        f"⏰ Thời gian đặt cược: **{seconds} Giây**\n"
                        f"👉 **Cách đặt cược:** Gõ `!txb <tiền> <t/x>` (Ví dụ: `!txb 5000 t` hoặc `!txb 2000 x`)\n\n"
                        f"🔴 **Cửa TÀI:** 0 {COIN} (0 người)\n"
                        f"🟢 **Cửa XỈU:** 0 {COIN} (0 người)",
            color=discord.Color.gold()
        )
        main_msg = await ctx.send(embed=embed)

        # Chờ đặt cược
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

        # Xử lý trả thưởng
        for side, bets in [("tai", room["tai"]), ("xiu", room["xiu"])]:
            for uid, amt in bets.items():
                u = get_user(data, uid)
                if is_bao:
                    if side == actual:
                        win = amt * 3
                        u["wallet"] += win
                        winners.append(f"<@{uid}>: **+{win:,}** {COIN} (Bão x3)")
                    else:
                        losers.append(f"<@{uid}>: **-{amt:,}** {COIN}")
                elif side == actual:
                    u["wallet"] += amt
                    winners.append(f"<@{uid}>: **+{amt:,}** {COIN}")
                else:
                    losers.append(f"<@{uid}>: **-{amt:,}** {COIN}")

        save_db(data)

        res_name = f"🔴 TÀI ({total} điểm)" if actual == "tai" else f"🟢 XỈU ({total} điểm)"
        if is_bao:
            res_name += f" 🌪️ BÃO {d1}!"

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
        await ctx.send(embed=embed_res)

    @commands.command(name="txb", aliases=["txbet"])
    async def cmd_txb(self, ctx, amount: int, choice: str):
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

        if amount <= 0:
            await ctx.send("❌ Tiền cược phải lớn hơn 0!")
            return

        data = load_db()
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < amount:
            await ctx.send(f"❌ Ví không đủ tiền! Hiện có: **{u.get('wallet', 0):,}** {COIN}")
            return

        # Trừ tiền trước khi vào bàn
        u["wallet"] -= amount
        save_db(data)

        room = self.active_tx_rooms[guild_id]
        room[side][ctx.author.id] = room[side].get(ctx.author.id, 0) + amount

        side_text = "🔴 TÀI" if side == "tai" else "🟢 XỈU"
        await ctx.send(f"✅ {ctx.author.mention} đã đặt cược **{amount:,}** {COIN} vào cửa **{side_text}**!")


async def setup(bot):
    await bot.add_cog(Multiplayer(bot))
