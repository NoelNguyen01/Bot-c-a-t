# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import sys
from pathlib import Path

import aiohttp.web
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("NekoBot")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


async def start_keep_alive_web():
    port = int(os.getenv("PORT", 8080))
    app = aiohttp.web.Application()
    app.router.add_get("/", lambda r: aiohttp.web.Response(text="🐱 Neko Bot đang hoạt động 24/7!"))
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Web keep-alive server đang chạy trên cổng {port}")


class NekoBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or("n!", "!"),
            intents=intents,
            help_command=None,
            status=discord.Status.online,
            activity=discord.Game(name="n!help | Neko 🐱✨"),
        )

    async def setup_hook(self) -> None:
        if os.getenv("PORT") or os.getenv("RENDER"):
            asyncio.create_task(start_keep_alive_web())

        cogs_dir = Path(__file__).parent / "cogs"
        if cogs_dir.exists() and cogs_dir.is_dir():
            for file in cogs_dir.glob("*.py"):
                if file.stem not in ["__init__", "database"]:
                    cog_name = f"cogs.{file.stem}"
                    try:
                        await self.load_extension(cog_name)
                        logger.info(f"Đã tải thành công Cog: {cog_name}")
                    except Exception as e:
                        logger.error(f"Lỗi khi nạp Cog {cog_name}: {e}", exc_info=True)

        self.tree.on_error = self.on_tree_error

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = error.retry_after
            msg = f"⏳ Từ từ thôi bạn ơi, đợi **{retry_after:.0f} giây** nữa nhé!"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ Bạn không có quyền để dùng lệnh này nha!"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        command_name = interaction.command.name if interaction.command else "Không rõ"
        logger.error(f"Lỗi lệnh /{command_name}: {error}", exc_info=True)
        error_msg = f"Có lỗi xảy ra: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(error_msg, ephemeral=True)
        else:
            await interaction.response.send_message(error_msg, ephemeral=True)

    async def on_ready(self) -> None:
        logger.info(f"🐱 Neko Bot đã đăng nhập thành công: {self.user} (ID: {self.user.id})")
        try:
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Game(name="n!help | Neko System 🐱✨")
            )
        except Exception:
            pass

        # Xóa sạch lệnh trùng ở cấp độ Server (Guild) để chỉ giữ 1 bộ lệnh duy nhất
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception as e:
                logger.warning(f"Lỗi clear guild commands {guild.name}: {e}")

        # Đồng bộ bộ lệnh Global chuẩn
        try:
            synced = await self.tree.sync()
            logger.info(f"⚡ Đã đồng bộ chuẩn xác {len(synced)} lệnh Slash Global (Không bị nhân đôi)!")
        except Exception as e:
            logger.error(f"Lỗi sync global: {e}")

        logger.info(f"Đang kết nối tới {len(self.guilds)} máy chủ Discord.")
        print("\n" + "="*50)
        print("       🐱 NEKO BOT ĐÃ SẴN SÀNG PHỤC VỤ! 🐱       ")
        print("="*50 + "\n")


bot = NekoBot()

@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def manual_sync(ctx):
    async with ctx.typing():
        try:
            # Xóa sạch lệnh guild thừa
            bot.tree.clear_commands(guild=ctx.guild)
            await bot.tree.sync(guild=ctx.guild)
            # Sync global
            synced = await bot.tree.sync()
            await ctx.send(f"🧹 **ĐÃ XÓA SẠCH LỆNH TRÙNG & ĐỒNG BỘ {len(synced)} LỆNH DUY NHẤT CHO NEKO BOT!** 🎉")
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi sync: `{e}`")


async def main() -> None:
    if not TOKEN:
        logger.critical("Không tìm thấy DISCORD_TOKEN trong file .env!")
        sys.exit(1)

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot đã được dừng thủ công.")
