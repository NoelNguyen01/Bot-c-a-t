const { EmbedBuilder, PermissionFlagsBits } = require('discord.js');
const {
    loadDb,
    saveDb,
    getUser,
    parseAmount,
    formatMoney
} = require('../utils/database');

const COIN = "💵";

module.exports = {
    async help(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const embed = new EmbedBuilder()
            .setTitle("🐱 MENU HƯỚNG DẪN LỆNH NEKO BOT (DISCORD.JS V14) 🎮")
            .setDescription("Chào mừng bạn đến với **Neko Bot (JavaScript Edition)** — Kinh Tế, Vay Vốn Ngân Hàng, Sòng Bạc & Lì Xì Server!\n*Tiền tố lệnh:* `!` hoặc `n!` hoặc dùng `/` (Slash Commands)")
            .setThumbnail("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png")
            .setColor(0xFF69B4)
            .addFields(
                {
                    name: "🪙 1. Kinh Tế & Ngân Hàng & Vay Vốn",
                    value: "• `!bal` / `/bal` : Xem ví tiền, bank & nợ vay\n" +
                           "• `!dep <tiền>` / `/dep` : Gửi tiền vào ngân hàng\n" +
                           "• `!with <tiền>` / `/with` : Rút tiền ra ví\n" +
                           "• `!vay <tiền>` / `/vay` : Vay ngân hàng (Tối đa 100M, lãi 2%/phút)\n" +
                           "• `!trano <tiền>` / `/trano` : Trả nợ ngân hàng (Trả góp mỗi 10% nợ được giảm 0.5% lãi)\n" +
                           "• `!laodong` / `/laodong` : Lao động công ích chuộc nợ (-5% đến -15% nợ/lần, 15p)\n" +
                           "• `!topno` / `/topno` : Bảng phong thần Chúa Chổm ngập nợ\n" +
                           "• `!daily` / `/daily` : Điểm danh nhận tiền hằng ngày + streak\n" +
                           "• `!work` / `/work` : Đi làm kiếm lương mỗi 30 phút\n" +
                           "• `!beg` / `/beg` : Ăn xin tiền lẻ\n" +
                           "• `!rob @user` / `/rob` : Trộm ví tiền người khác\n" +
                           "• `!pay @user <tiền>` / `/pay` : Chuyển khoản (Phí chiết khấu 20%)\n" +
                           "• `!top` / `/top` : Bảng xếp hạng đại gia",
                    inline: false
                },
                {
                    name: "🎰 2. Sòng Bạc Mini (Casino)",
                    value: "• `!tx <tiền> <t/x>` / `/taixiu` : Đổ xúc xắc Tài Xỉu (Bão nhà cái ăn sạch)\n" +
                           "• `!bj <tiền>` / `/blackjack` : Đánh bài Xì Dách Blackjack (30s đếm ngược, chống thoát)\n" +
                           "• `!cf <tiền> <s/n>` / `/coinflip` : Tung đồng xu may rủi Sấp/Ngửa\n" +
                           "• `!slot <tiền>` / `/slots` : Quay hũ máy xèng hoa quả trúng Jackpot\n" +
                           "• `!baucua <tiền> <con>` / `/baucua` : Bầu cua tôm cá (bau, cua, tom, ca, ga, nai)\n" +
                           "• `!topwin` / `/topwin` : Bảng Phong Thần Thần Bài (Top Tỷ Lệ Thắng)\n" +
                           "*(Tất cả ván thắng cờ bạc chịu 10% thuế • Nợ ngân hàng quá hạn sẽ bị phong tỏa Casino)*",
                    inline: false
                },
                {
                    name: "🧧 3. Đấu Solo PvP & Lì Xì",
                    value: "• `!rps @user <cược>` / `/rps` : Kéo búa bao solo 1v1 nút bấm\n" +
                           "• `!lixi <tổng tiền> <số người>` / `/lixi` : Ném bao lì xì server giật thưởng",
                    inline: false
                },
                {
                    name: "👑 4. Quyền Quản Trị Viên (Admin)",
                    value: "• `!buffme <tiền>` : Bơm tiền vào ví của bạn (Admin only)\n" +
                           "• `!setmoney @user <tiền>` : Đặt số dư ví thành viên\n" +
                           "• `!addmoney @user <tiền>` : Cộng tiền vào ví thành viên\n" +
                           "• `!trutien @user <tiền>` : Phạt trừ tiền thành viên\n" +
                           "• `!cheat <mode>` : Chỉnh tỷ lệ thắng sòng bạc (`generous`, `hardcore`, `drain`, `default`)\n" +
                           "• `!help` / `/help` : Mở bảng hướng dẫn này",
                    inline: false
                }
            );

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async buffme(interactionOrMsg, amountStr = "1000000") {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, user.id);
        const amt = parseAmount(amountStr || "1000000", 1_000_000);

        if (amt <= 0n) {
            const msg = "❌ Số tiền buff không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        u.wallet = Number(BigInt(u.wallet || 0) + amt);
        saveDb(data);

        const msg = `👑 **ADMIN BUFF MONEY THÀNH CÔNG!**\n• Đã cộng: **+${formatMoney(amt)}** ${COIN}\n• Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async setmoney(interactionOrMsg, targetMember, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Chỉ Quản Trị Viên mới có quyền dùng lệnh này!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, targetMember.id);
        const amt = parseAmount(amountStr, 0);

        if (amt < 0n) {
            const msg = "❌ Số tiền không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        u.wallet = Number(amt);
        saveDb(data);

        const msg = `👑 Đã đặt lại ví của <@${targetMember.id}> thành: **${formatMoney(amt)}** ${COIN}!`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async addmoney(interactionOrMsg, targetMember, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Chỉ Quản Trị Viên mới có quyền dùng lệnh này!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, targetMember.id);
        const amt = parseAmount(amountStr, 0);

        if (amt <= 0n) {
            const msg = "❌ Số tiền không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        u.wallet = Number(BigInt(u.wallet || 0) + amt);
        saveDb(data);

        const msg = `👑 Đã cộng **+${formatMoney(amt)}** ${COIN} vào ví của <@${targetMember.id}>! Ví mới: **${formatMoney(u.wallet)}** ${COIN}`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async trutien(interactionOrMsg, targetMember, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Chỉ Quản Trị Viên mới có quyền dùng lệnh này!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, targetMember.id);
        const amt = parseAmount(amountStr, u.wallet || 0);

        if (amt <= 0n) {
            const msg = "❌ Số tiền không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const cur = BigInt(u.wallet || 0);
        u.wallet = Number(cur > amt ? cur - amt : 0n);
        saveDb(data);

        const msg = `👑 Đã phạt trừ **-${formatMoney(amt)}** ${COIN} khỏi ví <@${targetMember.id}>! Ví còn: **${formatMoney(u.wallet)}** ${COIN}`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async cheat(interactionOrMsg, mode) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Chỉ Quản Trị Viên mới có quyền chỉnh cheat sòng bạc!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const validModes = ["generous", "hardcore", "drain", "default"];
        const chosenMode = String(mode).toLowerCase();
        if (!validModes.includes(chosenMode)) {
            const msg = `❌ Mode không hợp lệ! Chọn: \`generous\` (60% win), \`hardcore\` (25% win), \`drain\` (10% win), \`default\` (tự động theo cược).`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        if (!data.cheat_config) data.cheat_config = {};
        data.cheat_config.global_mode = chosenMode;
        saveDb(data);

        const msg = `👑 Đã chuyển chế độ Casino thành công sang: **${chosenMode.toUpperCase()}**!`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    }
};
