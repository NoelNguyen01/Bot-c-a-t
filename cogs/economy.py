# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user

COIN = "💵"
CURRENCY = "Neko Coin"

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================= 1. XEM VÍ & NGÂN HÀNG =================
    @commands.command(name="bal", aliases=["balance", "vi", "money"])
    async def cmd_bal(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author
        data = load_db()
        u = get_user(data, target.id)
        
        wallet = u.get("wallet", 0)
        bank = u.get("bank", 0)
        total = wallet + bank

        embed = discord.Embed(
            title=f"👛 Tài Khoản Neko — {target.display_name}",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💵 Tiền Mặt (Ví):", value=f"**{wallet:,}** {COIN}", inline=True)
        embed.add_field(name="🏦 Ngân Hàng:", value=f"**{bank:,}** {COIN}", inline=True)
        embed.add_field(name="💰 Tổng Tài Sản:", value=f"**{total:,}** {COIN}", inline=False)
        embed.set_footer(text="Dùng !dep để gửi tiền vào ngân hàng chống trộm cướp!")
        await ctx.send(embed=embed)

    @app_commands.command(name="bal", description="Xem số dư ví tiền mặt và ngân hàng")
    async def slash_bal(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        data = load_db()
        u = get_user(data, target.id)
        wallet = u.get("wallet", 0)
        bank = u.get("bank", 0)
        total = wallet + bank

        embed = discord.Embed(
            title=f"👛 Tài Khoản Neko — {target.display_name}",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💵 Tiền Mặt (Ví):", value=f"**{wallet:,}** {COIN}", inline=True)
        embed.add_field(name="🏦 Ngân Hàng:", value=f"**{bank:,}** {COIN}", inline=True)
        embed.add_field(name="💰 Tổng Tài Sản:", value=f"**{total:,}** {COIN}", inline=False)
        await interaction.response.send_message(embed=embed)

    # ================= 2. GỬI & RÚT NGÂN HÀNG =================
    @commands.command(name="dep", aliases=["deposit"])
    async def cmd_dep(self, ctx, amount: str):
        data = load_db()
        u = get_user(data, ctx.author.id)
        wallet = u.get("wallet", 0)

        if amount.lower() == "all":
            dep_amt = wallet
        else:
            try:
                dep_amt = int(amount)
            except ValueError:
                await ctx.send("❌ Vui lòng nhập số tiền hợp lệ hoặc gõ `!dep all`!")
                return

        if dep_amt <= 0:
            await ctx.send("❌ Số tiền gửi phải lớn hơn 0!")
            return
        if dep_amt > wallet:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! Ví hiện có: **{wallet:,}** {COIN}")
            return

        u["wallet"] -= dep_amt
        u["bank"] = u.get("bank", 0) + dep_amt
        save_db(data)
        await ctx.send(f"🏦 Bạn đã gửi **{dep_amt:,}** {COIN} vào Ngân Hàng an toàn 100%! (Ngân hàng: **{u['bank']:,}** {COIN})")

    @commands.command(name="with", aliases=["withdraw"])
    async def cmd_with(self, ctx, amount: str):
        data = load_db()
        u = get_user(data, ctx.author.id)
        bank = u.get("bank", 0)

        if amount.lower() == "all":
            with_amt = bank
        else:
            try:
                with_amt = int(amount)
            except ValueError:
                await ctx.send("❌ Vui lòng nhập số tiền hợp lệ hoặc gõ `!with all`!")
                return

        if with_amt <= 0:
            await ctx.send("❌ Số tiền rút phải lớn hơn 0!")
            return
        if with_amt > bank:
            await ctx.send(f"❌ Ngân hàng của bạn không đủ tiền! Hiện có: **{bank:,}** {COIN}")
            return

        u["bank"] -= with_amt
        u["wallet"] = u.get("wallet", 0) + with_amt
        save_db(data)
        await ctx.send(f"💵 Bạn đã rút **{with_amt:,}** {COIN} ra ví tiền mặt! (Ví: **{u['wallet']:,}** {COIN})")

    # ================= 3. ĐIỂM DANH DAILY =================
    @commands.command(name="daily", aliases=["diemdanh"])
    async def cmd_daily(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_daily", 0)
        streak = u.get("streak", 0)

        diff = now - last
        if diff < 86400:
            rem = int(86400 - diff)
            h = rem // 3600
            m = (rem % 3600) // 60
            await ctx.send(f"⏳ Bạn đã nhận quà hôm nay rồi! Quay lại sau **{h}h {m}p** nữa nhé.")
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

    # ================= 4. ĐI LÀM WORK =================
    @commands.command(name="work", aliases=["lam"])
    async def cmd_work(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_work", 0)

        if now - last < 1800:
            rem = int(1800 - (now - last))
            m = rem // 60
            s = rem % 60
            await ctx.send(f"😴 Bạn vừa làm việc mệt rồi, nghỉ ngơi **{m}p {s}s** nữa nhé!")
            return

        jobs = [
            ("Lập trình bot Discord", random.randint(200, 400)),
            ("Phục vụ quán Cà Phê Mèo Neko", random.randint(180, 350)),
            ("Giao đồ ăn nhanh buổi tối", random.randint(150, 300)),
            ("Bán trà sữa trân châu đường đen", random.randint(160, 320)),
            ("Chăm sóc thú cưng", random.randint(170, 310)),
            ("Thiết kế banner anime", random.randint(220, 380))
        ]
        job, wage = random.choice(jobs)
        u["last_work"] = now
        u["wallet"] = u.get("wallet", 0) + wage
        save_db(data)

        await ctx.send(f"💼 Bạn vừa làm **{job}** và nhận được **+{wage:,}** {COIN}! (Ví: **{u['wallet']:,}** {COIN})")

    # ================= 5. ĂN XIN BEG =================
    @commands.command(name="beg", aliases=["anxin"])
    async def cmd_beg(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        now = time.time()
        last = u.get("last_beg", 0)

        if now - last < 600:
            rem = int(600 - (now - last))
            m = rem // 60
            s = rem % 60
            await ctx.send(f"⏳ Vừa xin xong mỏi mồm chưa? Đợi **{m}p {s}s** nữa nhé!")
            return

        u["last_beg"] = now
        if random.random() < 0.75:
            amt = random.randint(40, 180)
            u["wallet"] = u.get("wallet", 0) + amt
            save_db(data)
            await ctx.send(f"🥺 Bạn chìa nón ra và được người qua đường thương tình cho **+{amt:,}** {COIN}! (Ví: **{u['wallet']:,}** {COIN})")
        else:
            await ctx.send(f"💀 Bạn chìa nón ra nhưng bị bảo vệ đuổi chạy té khói!")

    # ================= 6. CƯỚP TIỀN ROB =================
    @commands.command(name="rob", aliases=["cuop"])
    async def cmd_rob(self, ctx, target: discord.Member):
        if target.id == ctx.author.id:
            await ctx.send("❌ Tự cướp tiền mình à?")
            return
        if target.bot:
            await ctx.send("❌ Không thể cướp tiền của Bot!")
            return

        data = load_db()
        robber = get_user(data, ctx.author.id)
        victim = get_user(data, target.id)
        now = time.time()

        if now - robber.get("last_rob", 0) < 3600:
            rem = int(3600 - (now - robber.get("last_rob", 0)))
            m = rem // 60
            await ctx.send(f"🚔 Cảnh sát đang tuần tra, đợi **{m} phút** nữa nhé!")
            return

        # Kiểm tra khiên bảo vệ của nạn nhân
        if victim.get("shield_until", 0) > now:
            await ctx.send(f"🛡️ {target.mention} đang được bảo vệ bởi Khiên Thần Thánh! Bạn không thể cướp!")
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
            await ctx.send(f"🥷 Thành công! Bạn vừa lẻn vào móc trộm được **+{stolen:,}** {COIN} từ ví của {target.mention}!")
        else:
            fine = min(r_wallet, random.randint(300, 600))
            robber["wallet"] -= fine
            victim["wallet"] += fine
            save_db(data)
            await ctx.send(f"🚨 Bị bắt quả tang tại trận! Bạn bị đền **-{fine:,}** {COIN} cho {target.mention}!")

    # ================= 7. CHUYỂN TIỀN PAY =================
    @commands.command(name="pay", aliases=["give", "chuyen"])
    async def cmd_pay(self, ctx, target: discord.Member, amount: int):
        if target.id == ctx.author.id or target.bot:
            await ctx.send("❌ Người nhận không hợp lệ!")
            return
        if amount <= 0:
            await ctx.send("❌ Số tiền phải lớn hơn 0!")
            return

        data = load_db()
        sender = get_user(data, ctx.author.id)
        receiver = get_user(data, target.id)

        if sender.get("wallet", 0) < amount:
            await ctx.send(f"❌ Bạn không đủ tiền trong ví! (Ví: **{sender.get('wallet', 0):,}** {COIN})")
            return

        sender["wallet"] -= amount
        receiver["wallet"] = receiver.get("wallet", 0) + amount
        save_db(data)
        await ctx.send(f"💸 {ctx.author.mention} đã chuyển **{amount:,}** {COIN} cho {target.mention}!")

    # ================= 8. TOP ĐẠI GIA =================
    @commands.command(name="top", aliases=["leaderboard", "rich"])
    async def cmd_top(self, ctx):
        data = load_db()
        users = data.get("users", {})
        if not users:
            await ctx.send("Chưa có dữ liệu người chơi.")
            return

        sorted_users = sorted(users.items(), key=lambda x: x[1].get("wallet", 0) + x[1].get("bank", 0), reverse=True)

        embed = discord.Embed(
            title="🏆 BẢNG PHONG THẦN ĐẠI GIA NEKO 🌟",
            color=discord.Color.gold()
        )
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
