# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import random
import time
from typing import Optional
from cogs.database import load_db, save_db, get_user

COIN = "💵"

SHOP_ITEMS = {
    "nhan_cuoi": {"name": "Nhẫn Kim Cương", "icon": "💍", "price": 10000, "desc": "Dùng để cầu hôn bạn bè (!marry)"},
    "thuc_an_pet": {"name": "Thức Ăn Pet", "icon": "🍖", "price": 500, "desc": "Cho thú cưng ăn tăng độ no"},
    "khien_bao_ve": {"name": "Khiên Bảo Vệ 24h", "icon": "🛡️", "price": 5000, "desc": "Chống 100% các vụ cướp bóc trong 24 giờ"},
    "ve_so": {"name": "Vé Số May Mắn", "icon": "🎟️", "price": 1000, "desc": "Mở ra trúng tiền ngẫu nhiên từ 0 đến 50,000$"},
}

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="shop", aliases=["cuahang"])
    async def cmd_shop(self, ctx):
        embed = discord.Embed(
            title="🏪 CỬA HÀNG VẬT PHẨM NEKO 🛒",
            description="Dùng lệnh `!buy <mã_vật_phẩm>` để mua đồ:\n",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        for key, item in SHOP_ITEMS.items():
            embed.add_field(
                name=f"{item['icon']} {item['name']} (`!buy {key}`)",
                value=f"• Giá: **{item['price']:,}** {COIN}\n• Công dụng: *{item['desc']}*",
                inline=False
            )
        embed.set_footer(text="Dùng !inv để xem túi đồ của bạn | !use <mã_vật_phẩm> để sử dụng")
        await ctx.send(embed=embed)

    @commands.command(name="buy", aliases=["mua"])
    async def cmd_buy(self, ctx, item_key: str, amount: int = 1):
        item_key = item_key.lower()
        if item_key not in SHOP_ITEMS:
            await ctx.send("❌ Vật phẩm không tồn tại! Gõ `!shop` để xem danh sách.")
            return

        if amount <= 0:
            await ctx.send("❌ Số lượng phải lớn hơn 0!")
            return

        item = SHOP_ITEMS[item_key]
        total_price = item["price"] * amount

        data = load_db()
        u = get_user(data, ctx.author.id)

        if u.get("wallet", 0) < total_price:
            await ctx.send(f"❌ Bạn không đủ tiền! Cần **{total_price:,}** {COIN} (Ví có: **{u.get('wallet', 0):,}** {COIN})")
            return

        u["wallet"] -= total_price
        if "inventory" not in u:
            u["inventory"] = {}
        u["inventory"][item_key] = u["inventory"].get(item_key, 0) + amount
        save_db(data)

        await ctx.send(f"✅ Bạn đã mua thành công **x{amount} {item['name']} {item['icon']}**! (Ví còn: **{u['wallet']:,}** {COIN})")

    @commands.command(name="inv", aliases=["inventory", "tuido", "balo"])
    async def cmd_inv(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author
        data = load_db()
        u = get_user(data, target.id)
        inv = u.get("inventory", {})

        embed = discord.Embed(
            title=f"🎒 Balo Túi Đồ — {target.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        if not inv or not any(v > 0 for v in inv.values()):
            embed.description = "Túi đồ hiện đang trống rỗng! Hãy ghé `!shop` để mua sắm nhé."
        else:
            desc = ""
            for key, count in inv.items():
                if count > 0 and key in SHOP_ITEMS:
                    item = SHOP_ITEMS[key]
                    desc += f"• {item['icon']} **{item['name']}**: x{count}\n"
            embed.description = desc

        now = time.time()
        if u.get("shield_until", 0) > now:
            rem = int(u.get("shield_until", 0) - now)
            embed.add_field(name="🛡️ Trạng Thái Bảo Vệ:", value=f"Còn **{rem // 3600}h {(rem % 3600) // 60}p**", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="use", aliases=["dung"])
    async def cmd_use(self, ctx, item_key: str):
        item_key = item_key.lower()
        data = load_db()
        u = get_user(data, ctx.author.id)
        inv = u.get("inventory", {})

        if inv.get(item_key, 0) <= 0:
            await ctx.send("❌ Bạn không có vật phẩm này trong balo! Gõ `!inv` để kiểm tra.")
            return

        inv[item_key] -= 1

        if item_key == "khien_bao_ve":
            now = time.time()
            current_shield = max(now, u.get("shield_until", 0))
            u["shield_until"] = current_shield + 86400
            save_db(data)
            await ctx.send(f"🛡️ Bạn đã kích hoạt **Khiên Bảo Vệ 24h**! Không ai có thể cướp tiền của bạn trong vòng 24 giờ!")

        elif item_key == "ve_so":
            prize = random.choice([0, 0, 500, 1000, 2000, 5000, 10000, 50000])
            u["wallet"] = u.get("wallet", 0) + prize
            save_db(data)
            if prize > 0:
                await ctx.send(f"🎟️ Chúc mừng! Bạn cào vé số và trúng giải thưởng **+{prize:,}** {COIN}!")
            else:
                await ctx.send(f"🎟️ Rất tiếc, vé số của bạn chỉ trúng chữ 'Chúc bạn may mắn lần sau'!")

        elif item_key == "thuc_an_pet":
            pet = u.get("pet")
            if not pet:
                inv[item_key] += 1
                await ctx.send("❌ Bạn chưa có thú cưng để dùng thức ăn!")
                return
            pet["hunger"] = 100
            save_db(data)
            await ctx.send(f"🍖 {pet['name']} đã ăn no căng bụng (Độ no: 100/100)!")

        else:
            save_db(data)
            await ctx.send("✅ Đã sử dụng vật phẩm thành công!")


async def setup(bot):
    await bot.add_cog(Shop(bot))
