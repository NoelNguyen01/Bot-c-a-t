# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import random
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user

COIN = "💵"

PET_TYPES = {
    "meo": {"name": "Mèo Neko", "icon": "🐱", "price": 5000, "base_atk": 20, "base_hp": 100},
    "cho": {"name": "Chó Shiba", "icon": "🐕", "price": 5000, "base_atk": 25, "base_hp": 110},
    "rong": {"name": "Rồng Lửa", "icon": "🐉", "price": 20000, "base_atk": 45, "base_hp": 180},
    "hamster": {"name": "Hamster Béo", "icon": "🐹", "price": 3000, "base_atk": 15, "base_hp": 80},
}

class Pets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="pet", invoke_without_command=True)
    async def cmd_pet(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        pet = u.get("pet")

        if not pet:
            embed = discord.Embed(
                title="🐾 HỆ THỐNG THÚ CƯNG (PET SYSTEM)",
                description="Bạn chưa sở hữu thú cưng nào!\n\n"
                            "👉 Dùng lệnh `!pet shop` để xem danh sách thú cưng có thể mua.\n"
                            "👉 Dùng `!pet buy <meo/cho/rong/hamster>` để mua thú cưng!",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"🐾 Thú Cưng Của {ctx.author.display_name} — {pet['name']} {pet['icon']}",
            color=discord.Color.green()
        )
        embed.add_field(name="⭐ Cấp Độ (Level):", value=f"**Lv.{pet.get('level', 1)}**", inline=True)
        embed.add_field(name="⚔️ Lực Chiến (ATK):", value=f"**{pet.get('atk', 20)}**", inline=True)
        embed.add_field(name="❤️ Máu Tối Đa (HP):", value=f"**{pet.get('hp', 100)}**", inline=True)
        embed.add_field(name="🍖 Độ No:", value=f"**{pet.get('hunger', 100)}/100**", inline=True)
        embed.add_field(name="✨ EXP:", value=f"**{pet.get('exp', 0)}/{pet.get('level', 1) * 100}**", inline=True)
        embed.set_footer(text="Lệnh: !pet feed (Cho ăn) | !pet train (Luyện tập) | !pet fight @user <cược>")
        await ctx.send(embed=embed)

    @cmd_pet.command(name="shop")
    async def pet_shop(self, ctx):
        embed = discord.Embed(
            title="🏪 CỬA HÀNG THÚ CƯNG NEKO 🐾",
            description="Chọn người bạn đồng hành của bạn:\n",
            color=discord.Color.gold()
        )
        for key, info in PET_TYPES.items():
            embed.add_field(
                name=f"{info['icon']} {info['name']} (`!pet buy {key}`)",
                value=f"• Giá: **{info['price']:,}** {COIN}\n• Công: **{info['base_atk']}** | Máu: **{info['base_hp']}**",
                inline=False
            )
        await ctx.send(embed=embed)

    @cmd_pet.command(name="buy")
    async def pet_buy(self, ctx, pet_type: str):
        pet_type = pet_type.lower()
        if pet_type not in PET_TYPES:
            await ctx.send("❌ Loại pet không hợp lệ! Gõ `!pet shop` để xem danh sách.")
            return

        data = load_db()
        u = get_user(data, ctx.author.id)

        if u.get("pet"):
            await ctx.send("❌ Bạn đã có một thú cưng rồi! Hãy chăm sóc người bạn hiện tại nhé.")
            return

        info = PET_TYPES[pet_type]
        if u.get("wallet", 0) < info["price"]:
            await ctx.send(f"❌ Bạn không đủ tiền! Cần **{info['price']:,}** {COIN} (Ví: **{u.get('wallet', 0):,}** {COIN})")
            return

        u["wallet"] -= info["price"]
        u["pet"] = {
            "type": pet_type,
            "name": info["name"],
            "icon": info["icon"],
            "level": 1,
            "atk": info["base_atk"],
            "hp": info["base_hp"],
            "hunger": 100,
            "exp": 0,
            "last_train": 0
        }
        save_db(data)
        await ctx.send(f"🎉 Chúc mừng bạn đã nhận nuôi thành công **{info['name']} {info['icon']}**!")

    @cmd_pet.command(name="feed")
    async def pet_feed(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        pet = u.get("pet")
        if not pet:
            await ctx.send("❌ Bạn chưa có thú cưng! Gõ `!pet shop` để mua.")
            return

        inv = u.get("inventory", {})
        if inv.get("thuc_an_pet", 0) <= 0:
            if u.get("wallet", 0) < 200:
                await ctx.send("❌ Bạn cần 200 tiền để mua đồ ăn cho Pet!")
                return
            u["wallet"] -= 200
        else:
            inv["thuc_an_pet"] -= 1

        pet["hunger"] = min(100, pet.get("hunger", 100) + 40)
        save_db(data)
        await ctx.send(f"🍖 {pet['name']} {pet['icon']} đã được ăn no nê! (Độ no: **{pet['hunger']}/100**)")

    @cmd_pet.command(name="train")
    async def pet_train(self, ctx):
        data = load_db()
        u = get_user(data, ctx.author.id)
        pet = u.get("pet")
        if not pet:
            await ctx.send("❌ Bạn chưa có thú cưng!")
            return

        now = time.time()
        if now - pet.get("last_train", 0) < 600:
            rem = int(600 - (now - pet.get("last_train", 0)))
            await ctx.send(f"😴 Pet đang nghỉ ngơi, quay lại sau **{rem // 60}p {rem % 60}s**!")
            return

        pet["last_train"] = now
        exp_gain = random.randint(30, 60)
        pet["exp"] = pet.get("exp", 0) + exp_gain
        req_exp = pet.get("level", 1) * 100

        lvl_up = False
        if pet["exp"] >= req_exp:
            pet["level"] = pet.get("level", 1) + 1
            pet["atk"] = pet.get("atk", 20) + 5
            pet["hp"] = pet.get("hp", 100) + 15
            pet["exp"] -= req_exp
            lvl_up = True

        save_db(data)
        if lvl_up:
            await ctx.send(f"🌟 **PET LÊN CẤP!** {pet['name']} đã thăng lên **Lv.{pet['level']}**! (ATK +5, HP +15)")
        else:
            await ctx.send(f"⚔️ {pet['name']} luyện tập chăm chỉ và nhận được **+{exp_gain} EXP**! ({pet['exp']}/{req_exp})")

    @cmd_pet.command(name="fight")
    async def pet_fight(self, ctx, opponent: discord.Member, bet: int = 1000):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.send("❌ Đối thủ không hợp lệ!")
            return

        data = load_db()
        u1 = get_user(data, ctx.author.id)
        u2 = get_user(data, opponent.id)

        p1 = u1.get("pet")
        p2 = u2.get("pet")

        if not p1 or not p2:
            await ctx.send("❌ Cả hai người chơi đều phải sở hữu thú cưng mới có thể solo!")
            return

        if u1.get("wallet", 0) < bet or u2.get("wallet", 0) < bet:
            await ctx.send(f"❌ Một trong hai người không đủ tiền cược **{bet:,}** {COIN}!")
            return

        # Tính toán kết quả dựa trên lực chiến
        power1 = p1["atk"] * 2 + p1["hp"] + random.randint(1, 30)
        power2 = p2["atk"] * 2 + p2["hp"] + random.randint(1, 30)

        if power1 > power2:
            u1["wallet"] += bet
            u2["wallet"] -= bet
            winner = ctx.author
            loser = opponent
            w_pet = p1
        else:
            u2["wallet"] += bet
            u1["wallet"] -= bet
            winner = opponent
            loser = ctx.author
            w_pet = p2

        save_db(data)
        embed = discord.Embed(
            title="⚔️ TRẬN ĐẤU THÚ CƯNG NẢY LỬA! 🐾",
            description=f"{p1['name']} {p1['icon']} (của {ctx.author.mention}) **VS** {p2['name']} {p2['icon']} (của {opponent.mention})\n\n"
                        f"🏆 **CHIẾN THẮNG:** {winner.mention} với thú cưng {w_pet['name']}!\n"
                        f"💰 Tiền thưởng: **+{bet:,}** {COIN} (từ ví của {loser.mention})!",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Pets(bot))
