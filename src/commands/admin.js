const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, StringSelectMenuBuilder, PermissionFlagsBits, ComponentType } = require('discord.js');
const {
    loadDb,
    saveDb,
    getUser,
    parseAmount,
    formatMoney,
    calculateLoanDebt,
    calculateWinRate
} = require('../utils/database');

const COIN = "💵";

module.exports = {
    async help(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const embed = new EmbedBuilder()
            .setTitle("🐱 MENU HƯỚNG DẪN LỆNH NEKO BOT (DISCORD.JS V14) 🎮")
            .setDescription("Chào mừng bạn đến với **Neko Bot** — Kinh Tế, Vay Vốn Ngân Hàng, Sòng Bạc & Lì Xì Server!\n*Tiền tố lệnh:* `!` hoặc `n!` hoặc dùng `/` (Slash Commands)")
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
                           "• `!laodong` / `/laodong` : Lao động công ích chuộc nợ (-50k đến -200k nợ/lần, 15p)\n" +
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
                    value: "• `!hien` / `/hien` : Mở bảng điều khiển bí mật Admin VIP\n" +
                           "• `!nhacai` / `/nhacai` : Bảng điều khiển nhà cái chỉnh tỷ lệ thắng\n" +
                           "• `!buffme <tiền>` : Bơm tiền vào ví Admin\n" +
                           "• `!setmoney @user <tiền>` : Đặt số dư ví thành viên\n" +
                           "• `!addmoney @user <tiền>` : Cộng tiền vào ví thành viên\n" +
                           "• `!trutien @user <tiền>` : Phạt trừ tiền thành viên",
                    inline: false
                }
            );

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async hien(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const embed = new EmbedBuilder()
            .setTitle("👑 BẢNG TRA CỨU QUYỀN LỰC VIP DÀNH CHO ADMIN 🔒")
            .setDescription("Dưới đây là toàn bộ công cụ quản trị, lệnh ẩn cheat và kiểm soát ngân khố của bạn:")
            .setColor(0xFEE75C)
            .setThumbnail("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f451.png")
            .addFields(
                {
                    name: "🎲 1. Bảng Điều Khiển Nhà Cái & Hack Tỷ Lệ Thắng",
                    value: "• `!nhacai` / `/nhacai` : Mở Menu giao diện điều khiển tỷ lệ thắng toàn server\n" +
                           "• `!checkwin @user` / `/checkwin` : Soi chi tiết bảng tỷ lệ thắng của @user\n" +
                           "• `!listwin` / `/listwin` : Xem danh sách tất cả người bị can thiệp tỷ lệ\n" +
                           "• `!setwin @user <0-100>` / `/setwin` : Ép tỷ lệ thắng của @user (100: Hack Win, 0: Ép Thua)\n" +
                           "• `!resetwin @user` : Xóa can thiệp, trả @user về tỷ lệ bình thường",
                    inline: false
                },
                {
                    name: "🏦 2. Quản Lý Ngân Hàng & Nợ Nần Thành Viên",
                    value: "• `!setbank @user <tiền>` : Đặt thẳng số dư ngân hàng\n" +
                           "• `!addbank @user <tiền>` : Cộng thêm tiền vào ngân hàng\n" +
                           "• `!trubank @user <tiền>` : Trừ bớt tiền trong ngân hàng\n" +
                           "• `!checkmoney @user` : Soi toàn bộ tài sản (Ví, Bank, Nợ vay, Lãi suất)\n" +
                           "• `!xoano_bank @user` : Xóa nợ vay ngân hàng cho thành viên\n" +
                           "• `!xoano @user` : Xóa nợ trong sổ đòi nợ dân gian P2P\n" +
                           "• `!clear_so_no` : Xóa sạch toàn bộ sổ nợ của Server",
                    inline: false
                },
                {
                    name: "🏛️ 3. Quản Lý Tiền Mặt & Kho Bạc Bot",
                    value: "• `!khobac` : Xem tổng số tiền thuế bot đã thu thập được\n" +
                           "• `!rutkhobac <tiền / all>` : Admin rút tiền từ Kho Bạc Bot về ví để tiêu xài!\n" +
                           "• `!buffme <tiền>` : Bơm tiền mặt vào ví Admin (mặc định 100k)\n" +
                           "• `!setmoney @user <tiền>` / `!addmoney` / `!trutien` : Can thiệp ví tiền mặt",
                    inline: false
                }
            )
            .setFooter({ text: "Bảo mật tuyệt đối • Chỉ hiển thị cho Admin!" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed], ephemeral: true }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async nhacai(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const curMode = data.cheat_config?.global_mode || 'default';

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('nc_default').setLabel('⚖️ Mặc Định (8%-48%)').setStyle(curMode === 'default' ? ButtonStyle.Success : ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('nc_generous').setLabel('🎰 Mồi Chài (60% Win)').setStyle(curMode === 'generous' ? ButtonStyle.Success : ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('nc_hardcore').setLabel('💀 Hút Máu (25% Win)').setStyle(curMode === 'hardcore' ? ButtonStyle.Success : ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('nc_drain').setLabel('🩸 Tận Thu (10% Win)').setStyle(curMode === 'drain' ? ButtonStyle.Success : ButtonStyle.Secondary)
        );

        const row2 = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('nc_listwin').setLabel('📋 Xem Danh Sách Can Thiệp').setStyle(ButtonStyle.Primary)
        );

        const embed = new EmbedBuilder()
            .setTitle("🕵️‍♂️ BẢNG ĐIỀU KHIỂN NHÀ CÁI ẨN 🎰")
            .setDescription(`Chọn chế độ tỷ lệ thắng toàn Server hoặc kiểm tra danh sách thành viên bị can thiệp:\n\n• **Chế độ hiện tại:** \`${curMode.toUpperCase()}\``)
            .setColor(0x5865F2);

        let msg;
        if (isSlash) msg = await interactionOrMsg.reply({ embeds: [embed], components: [row, row2], fetchReply: true, ephemeral: true });
        else msg = await interactionOrMsg.channel.send({ embeds: [embed], components: [row, row2] });

        const collector = msg.createMessageComponentCollector({
            componentType: ComponentType.Button,
            time: 120000
        });

        collector.on('collect', async (btnInt) => {
            if (!btnInt.member.permissions.has(PermissionFlagsBits.Administrator)) {
                return btnInt.reply({ content: "❌ Bạn không có quyền Admin!", ephemeral: true });
            }

            const currentDb = loadDb();
            if (!currentDb.cheat_config) currentDb.cheat_config = {};

            if (btnInt.customId === 'nc_listwin') {
                const overrides = currentDb.cheat_config.user_overrides || {};
                if (Object.keys(overrides).length === 0) {
                    return btnInt.reply({ content: "📋 Hiện tại không có thành viên nào bị can thiệp tỷ lệ riêng.", ephemeral: true });
                }
                let desc = "**🎯 Danh sách can thiệp riêng từng User:**\n";
                for (const uid in overrides) {
                    const rate = overrides[uid];
                    const tag = rate >= 90 ? "👑 [HACK THẮNG]" : (rate <= 10 ? "💀 [ÉP THUA]" : `[${rate}%]`);
                    desc += `• <@${uid}>: **${rate}% Win Rate** ${tag}\n`;
                }
                return btnInt.reply({ content: desc, ephemeral: true });
            }

            const modeMap = {
                nc_default: 'default',
                nc_generous: 'generous',
                nc_hardcore: 'hardcore',
                nc_drain: 'drain'
            };

            const selected = modeMap[btnInt.customId] || 'default';
            currentDb.cheat_config.global_mode = selected;
            saveDb(currentDb);

            const modeNames = {
                default: "⚖️ Mặc định (Tự động theo cược 8% - 48%)",
                generous: "🎰 Mồi chài (60% Win Rate)",
                hardcore: "💀 Hút máu (Max 25% Win Rate)",
                drain: "🩸 Tận thu (Max 10% Win Rate)"
            };

            await btnInt.reply({ content: `✅ Đã chuyển tỷ lệ thắng toàn Server sang: **${modeNames[selected]}**!`, ephemeral: true });
        });
    },

    async setwin(interactionOrMsg, targetMember, rateStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const rate = parseInt(rateStr, 10);
        if (isNaN(rate) || rate < 0 || rate > 100) {
            const msg = "❌ Tỷ lệ thắng không hợp lệ! Vui lòng nhập từ `0` đến `100` (Ví dụ: `!setwin @user 100`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        if (!data.cheat_config) data.cheat_config = {};
        if (!data.cheat_config.user_overrides) data.cheat_config.user_overrides = {};

        data.cheat_config.user_overrides[String(targetMember.id)] = rate;
        saveDb(data);

        const tag = rate >= 90 ? "👑 [HACK THẮNG 100%]" : (rate <= 10 ? "💀 [ÉP THUA 0%]" : `[${rate}%]`);
        const msg = `✅ Đã thiết lập tỷ lệ thắng của <@${targetMember.id}> thành **${rate}%** ${tag}!`;
        return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
    },

    async resetwin(interactionOrMsg, targetMember) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const overrides = data.cheat_config?.user_overrides || {};
        if (overrides[String(targetMember.id)] !== undefined) {
            delete data.cheat_config.user_overrides[String(targetMember.id)];
            saveDb(data);
            const msg = `🔄 Đã xóa can thiệp tỷ lệ của <@${targetMember.id}>, trả về ngẫu nhiên bình thường!`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        } else {
            const msg = `ℹ️ <@${targetMember.id}> không có can thiệp tỷ lệ riêng.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }
    },

    async checkwin(interactionOrMsg, targetMember) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;
        const target = targetMember || (isSlash ? interactionOrMsg.user : interactionOrMsg.author);

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const cheatCfg = data.cheat_config || {};
        const overrides = cheatCfg.user_overrides || {};
        const globalMode = cheatCfg.global_mode || 'default';

        const globalModeNames = {
            default: "⚖️ Mặc định (Tự động giảm theo tiền cược 8% - 48%)",
            generous: "🎰 Mồi chài (Cố định 60% Win)",
            hardcore: "💀 Hút máu (Tối đa 25% Win)",
            drain: "🩸 Tận thu (Tối đa 10% Win)"
        };

        const uid = String(target.id);
        let statusText = "";
        let color = 0x5865F2;

        if (overrides[uid] !== undefined) {
            const rate = overrides[uid];
            statusText = `🚨 **CAN THIỆP ĐÍCH DANH:** \`${rate}%\` `;
            if (rate >= 90) statusText += "👑 **[HACK THẮNG 100%]**";
            else if (rate <= 10) statusText += "💀 **[ÉP THUA 0%]**";
            color = rate >= 50 ? 0xFEE75C : 0xED4245;
        } else {
            statusText = `⚖️ **THEO TOÀN SERVER (${globalModeNames[globalMode] || 'Mặc định'})**`;
        }

        const betSimulations = [
            [100_000n, "Cược nhỏ (<= 500k)"],
            [10_000_000n, "Vừa phải (500k - 50M)"],
            [500_000_000n, "Đại gia (50M - 1B)"],
            [5_000_000_000n, "Khủng (1B - 10B)"],
            [50_000_000_000n, "Tài phiệt (10B - 100B)"],
            [500_000_000_000n, "Siêu cá mập (100B - 1,000B)"],
            [2_000_000_000_000n, "Tất tay (> 1 Ngàn Tỷ)"]
        ];

        let tableLines = "";
        for (const [betVal, label] of betSimulations) {
            const prob = calculateWinRate(data, target.id, betVal);
            const pct = Math.round(prob * 100);
            tableLines += `• **${label}:** \`${pct}%\` xác suất thắng\n`;
        }

        const embed = new EmbedBuilder()
            .setTitle(`📊 BẢNG SOI TỶ LỆ THẮNG — ${target.displayName || target.username}`)
            .setDescription(`**Thành viên:** <@${target.id}> (ID: \`${target.id}\`)\n\n` +
                            `🎯 **Trạng Thái Hiện Tại:**\n${statusText}\n\n` +
                            `🎲 **Bảng Tỷ Lệ Thắng Thực Tế Theo Mức Cược:**\n${tableLines}`)
            .setColor(color)
            .setFooter({ text: "Dùng !setwin @user <%> để đổi tỷ lệ • !resetwin @user để hủy" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed], ephemeral: true }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async listwin(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const overrides = data.cheat_config?.user_overrides || {};
        const entries = Object.entries(overrides);

        if (entries.length === 0) {
            const msg = "📋 Hiện tại không có thành viên nào bị can thiệp tỷ lệ riêng.";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        entries.sort((a, b) => b[1] - a[1]);
        const medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"];
        let desc = "";

        entries.slice(0, 10).forEach(([uid, rate], idx) => {
            const medal = medals[idx] || `#${idx + 1}`;
            const tag = rate >= 90 ? "👑 **[HACK THẮNG 100%]**" : (rate <= 10 ? "💀 **[ÉP THUA 0%]**" : `**[${rate}%]**`);
            desc += `${medal} <@${uid}> — \`${rate}%\` Win Rate ${tag}\n`;
        });

        const embed = new EmbedBuilder()
            .setTitle("🎯 BẢNG XẾP HẠNG CAN THIỆP TỶ LỆ THẮNG 👑")
            .setDescription(desc)
            .setColor(0x5865F2)
            .setFooter({ text: "Dùng !setwin @user <%> để chỉnh • !resetwin @user để xóa" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed], ephemeral: true }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async khobac(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const bal = data.treasury?.balance || 0;

        const embed = new EmbedBuilder()
            .setTitle("🏛️ KHO BẠC THUẾ NEKO BOT 💰")
            .setDescription(`Tổng số tiền thuế & lãi tích lũy hiện tại:\n\n💎 **${formatMoney(bal)}** ${COIN}\n\n*(Nguồn thu: 10% thuế thắng cược, 5% thuế bank/5h, 20% thuế chuyển tiền, lãi vay ngân hàng)*`)
            .setColor(0xFEE75C)
            .setFooter({ text: "Gõ !rutkhobac <tiền / all> để rút tiền về ví Admin!" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed], ephemeral: true }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async rutkhobac(interactionOrMsg, amountStr = "all") {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const bal = BigInt(data.treasury?.balance || 0);

        const amt = parseAmount(amountStr, bal);
        if (amt <= 0n || amt > bal) {
            const msg = `❌ Kho Bạc không đủ tiền! Cần: **${formatMoney(amt)}** (Hiện có: **${formatMoney(bal)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        data.treasury.balance = Number(bal - amt);
        const u = getUser(data, user.id);
        u.wallet = Number(BigInt(u.wallet || 0) + amt);
        saveDb(data);

        const msg = `👑 Admin <@${user.id}> đã rút **+${formatMoney(amt)}** ${COIN} từ Kho Bạc về ví! (Ví: **${formatMoney(u.wallet)}** ${COIN})`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async checkmoney(interactionOrMsg, targetMember) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, targetMember.id);
        const { totalDebt, principal, interest } = calculateLoanDebt(data, targetMember.id);
        const overrides = data.cheat_config?.user_overrides || {};
        const cheatVal = overrides[String(targetMember.id)] !== undefined ? `${overrides[String(targetMember.id)]}% Win` : "Mặc định";

        const embed = new EmbedBuilder()
            .setTitle(`🔍 SOI HỒ SƠ TÀI CHÍNH — ${targetMember.displayName || targetMember.username}`)
            .setColor(0x5865F2)
            .addFields(
                { name: "💵 Tiền Mặt (Ví):", value: `**${formatMoney(u.wallet || 0)}** ${COIN}`, inline: true },
                { name: "🏦 Ngân Hàng:", value: `**${formatMoney(u.bank || 0)}** ${COIN}`, inline: true },
                { name: "💰 Tổng Tài Sản:", value: `**${formatMoney(BigInt(u.wallet || 0) + BigInt(u.bank || 0))}** ${COIN}`, inline: false },
                { name: "💳 Nợ Ngân Hàng:", value: `**${formatMoney(totalDebt)}** ${COIN} *(Gốc: ${formatMoney(principal)}, Lãi: ${formatMoney(interest)})*`, inline: true },
                { name: "🎯 Trạng Thái Can Thiệp:", value: `**${cheatVal}**`, inline: true }
            );

        return isSlash ? interactionOrMsg.reply({ embeds: [embed], ephemeral: true }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async xoano_bank(interactionOrMsg, targetMember) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Chỉ Quản Trị Viên mới có quyền dùng lệnh này!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const uid = String(targetMember.id);
        if (data.loans && data.loans[uid]) {
            delete data.loans[uid];
            saveDb(data);
            const msg = `✅ Admin đã xóa sạch toàn bộ nợ vay ngân hàng cho <@${targetMember.id}>!`;
            return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
        } else {
            const msg = `ℹ️ <@${targetMember.id}> không có khoản nợ ngân hàng nào.`;
            return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
        }
    },

    async setbank(interactionOrMsg, targetMember, amountStr) {
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

        u.bank = Number(amt);
        saveDb(data);

        const msg = `🏦 Đã đặt số dư Bank của <@${targetMember.id}> thành: **${formatMoney(amt)}** ${COIN}!`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async addbank(interactionOrMsg, targetMember, amountStr) {
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

        u.bank = Number(BigInt(u.bank || 0) + amt);
        saveDb(data);

        const msg = `✨ Đã cộng **+${formatMoney(amt)}** ${COIN} vào Bank cho <@${targetMember.id}>! Bank: **${formatMoney(u.bank)}** ${COIN}`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async trubank(interactionOrMsg, targetMember, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Chỉ Quản Trị Viên mới có quyền dùng lệnh này!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, targetMember.id);
        const amt = parseAmount(amountStr, u.bank || 0);

        if (amt <= 0n) {
            const msg = "❌ Số tiền không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const cur = BigInt(u.bank || 0);
        u.bank = Number(cur > amt ? cur - amt : 0n);
        saveDb(data);

        const msg = `⚠️ Đã trừ **-${formatMoney(amt)}** ${COIN} trong Bank của <@${targetMember.id}>! (Bank còn: **${formatMoney(u.bank)}** ${COIN})`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async buffme(interactionOrMsg, amountStr = "100000") {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const member = isSlash ? interactionOrMsg.member : interactionOrMsg.member;
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (!member.permissions.has(PermissionFlagsBits.Administrator)) {
            const msg = "❌ Lệnh này chỉ dành riêng cho Quản Trị Viên (Administrator)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const u = getUser(data, user.id);
        const amt = parseAmount(amountStr || "100000", 100_000);

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
