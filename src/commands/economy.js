const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const {
    loadDb,
    saveDb,
    getUser,
    parseAmount,
    formatMoney,
    addTreasury,
    applyBankTax,
    calculateLoanDebt,
    deductLoanDebt,
    MAX_LOAN_LIMIT
} = require('../utils/database');

const COIN = "💵";

module.exports = {
    async bal(interactionOrMsg, targetUser = null) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const author = isSlash ? interactionOrMsg.user : interactionOrMsg.author;
        const target = targetUser || author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, target.id);
        const { totalDebt, interest, isOverdue } = calculateLoanDebt(data, target.id);

        const totalAssets = BigInt(u.wallet || 0) + BigInt(u.bank || 0);

        let statusText = isOverdue ? "💀 **Nợ Xấu Quá Hạn (Casino Đang Bị Khóa!)**" : (totalDebt > 0n ? "⚠️ **Đang Nợ Ngân Hàng**" : "✨ **Tài Khoản Tốt**");

        const embed = new EmbedBuilder()
            .setTitle(`💳 VÍ TIỀN & TÀI KHOẢN: ${target.username}`)
            .setDescription(`• **Ví tiền mặt (Wallet):** \`${formatMoney(u.wallet || 0)}\` ${COIN}\n` +
                            `• **Ngân Hàng (Bank):** \`${formatMoney(u.bank || 0)}\` ${COIN}\n` +
                            `• **Tổng tài sản ròng:** \`${formatMoney(totalAssets)}\` ${COIN}\n\n` +
                            `🏦 **TÌNH TRẠNG VAY VỐN NGÂN HÀNG:**\n` +
                            `• **Dư nợ hiện tại:** \`${formatMoney(totalDebt)}\` ${COIN} *(Lãi phát sinh: +${formatMoney(interest)} ${COIN})*\n` +
                            `• **Trạng thái:** ${statusText}`)
            .setColor(isOverdue ? 0xED4245 : 0x5865F2)
            .setFooter({ text: "Thuế 5% Bank sau mỗi 5 tiếng • Vay ngân hàng tối đa 100M" });

        if (isSlash) await interactionOrMsg.reply({ embeds: [embed] });
        else await interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async dep(interactionOrMsg, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const depAmt = parseAmount(amountStr, u.wallet || 0);
        if (depAmt <= 0n) {
            const msg = "❌ Số tiền gửi không hợp lệ! (Ví dụ: `!dep 500k`, `!dep 10m`, `!dep all`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.wallet || 0) < depAmt) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Ví: **${formatMoney(u.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        u.wallet = Number(BigInt(u.wallet || 0) - depAmt);
        u.bank = Number(BigInt(u.bank || 0) + depAmt);
        saveDb(data);

        const msg = `🏦 Bạn đã gửi **+${formatMoney(depAmt)}** ${COIN} vào Ngân Hàng!\n• Ví còn: **${formatMoney(u.wallet)}** ${COIN}\n• Số dư Bank: **${formatMoney(u.bank)}** ${COIN}`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async with(interactionOrMsg, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const withAmt = parseAmount(amountStr, u.bank || 0);
        if (withAmt <= 0n) {
            const msg = "❌ Số tiền rút không hợp lệ! (Ví dụ: `!with 500k`, `!with 10m`, `!with all`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.bank || 0) < withAmt) {
            const msg = `❌ Số dư ngân hàng không đủ! (Bank: **${formatMoney(u.bank || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        u.bank = Number(BigInt(u.bank || 0) - withAmt);
        u.wallet = Number(BigInt(u.wallet || 0) + withAmt);
        saveDb(data);

        const msg = `💵 Bạn đã rút **+${formatMoney(withAmt)}** ${COIN} từ Ngân Hàng ra ví!\n• Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}\n• Số dư Bank còn: **${formatMoney(u.bank)}** ${COIN}`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async vay(interactionOrMsg, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;
        const uid = String(user.id);

        const data = loadDb();
        const loans = data.loans || {};

        const loanAmt = parseAmount(amountStr, 0);
        if (loanAmt <= 0n) {
            const msg = "❌ Số tiền vay không hợp lệ! (Ví dụ: `!vay 10m`, `!vay 50m`, `!vay 100m`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (loans[uid] && (loans[uid].principal || 0) > 0) {
            const { totalDebt } = calculateLoanDebt(data, user.id);
            const msg = `❌ Bạn đang có khoản nợ chưa trả (**${formatMoney(totalDebt)}** ${COIN})! Vui lòng dùng \`!trano\` trả hết trước khi vay tiếp.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        // Hạn mức tối đa 100M
        if (loanAmt > MAX_LOAN_LIMIT) {
            const msg = `❌ Hạn mức vay tối đa của Ngân Hàng là **${formatMoney(MAX_LOAN_LIMIT)}** ${COIN} (100M)!`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const u = getUser(data, user.id);
        u.wallet = Number(BigInt(u.wallet || 0) + loanAmt);
        if (!data.loans) data.loans = {};
        data.loans[uid] = {
            principal: Number(loanAmt),
            timestamp: Math.floor(Date.now() / 1000),
            tier: "Hạn mức tối đa 100M",
            rate_discount: 0.0
        };
        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("💳 HỢP ĐỒNG VAY NGÂN HÀNG THÀNH CÔNG! 🏦")
            .setDescription(`🎉 <@${user.id}> đã vay thành công **+${formatMoney(loanAmt)}** ${COIN}!\n\n` +
                            `• **Hạn mức tối đa:** \`100,000,000\` ${COIN} (100M)\n` +
                            `• **Lãi suất:** \`2% mỗi 1 phút\` (Tính lãi kép theo phút)\n` +
                            `• **Thời hạn vay gốc:** \`30 Phút\`\n` +
                            `• **Quá hạn:** Tự động gia hạn thêm 18 phút (60%) với \`lãi phạt 4%/phút\`\n` +
                            `• **Trần nợ tối đa:** 300% gốc (${formatMoney(loanAmt * 3n)} ${COIN})\n` +
                            `• **🎁 Ưu đãi trả góp:** Cứ trả góp đạt 10% nợ được **giảm 0.5% lãi**!\n\n` +
                            `💰 Tiền đã cộng vào ví! Gõ \`!trano all\` khi có tiền để thanh toán nợ.`)
            .setColor(0xFEE75C);

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async trano(interactionOrMsg, amountStr = "all") {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;
        const uid = String(user.id);

        const data = loadDb();
        const loans = data.loans || {};

        if (!loans[uid] || (loans[uid].principal || 0) <= 0) {
            const msg = "🎉 Bạn không có khoản nợ ngân hàng nào cần trả!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { totalDebt } = calculateLoanDebt(data, user.id);
        const u = getUser(data, user.id);
        const wallet = BigInt(u.wallet || 0);

        const payAmt = parseAmount(amountStr, totalDebt);
        if (payAmt <= 0n) {
            const msg = "❌ Số tiền trả không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (wallet < payAmt && amountStr.toLowerCase() !== "all") {
            const msg = `❌ Ví không đủ tiền! Cần **${formatMoney(payAmt)}** ${COIN}, ví có **${formatMoney(wallet)}** ${COIN}.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const actualPay = wallet < payAmt ? wallet : payAmt;
        if (actualPay <= 0n) {
            const msg = `❌ Bạn không có đồng nào trong ví để trả nợ!`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { actualPaid, remDebt, cleared } = deductLoanDebt(data, user.id, actualPay);
        u.wallet = Number(wallet - actualPaid);
        saveDb(data);

        let desc = "";
        if (cleared) {
            desc = `🎉 **CHÚC MỪNG! BẠN ĐÃ TRẢ SẠCH TOÀN BỘ NỢ NGÂN HÀNG!**\n• Số tiền thanh toán: **-${formatMoney(actualPaid)}** ${COIN}\n• Ví còn: **${formatMoney(u.wallet)}** ${COIN}\n✨ Tài khoản ngân hàng và sòng bạc đã được giải phóng hoàn toàn!`;
        } else {
            desc = `💳 **TRẢ GÓP NỢ THÀNH CÔNG!**\n• Đã trả: **-${formatMoney(actualPaid)}** ${COIN}\n• **Dư nợ còn lại:** **${formatMoney(remDebt)}** ${COIN}\n• Ví còn: **${formatMoney(u.wallet)}** ${COIN}\n🎁 *Mỗi 10% nợ được thanh toán đã được trừ thêm 0.5% lãi suất!*`;
        }

        const embed = new EmbedBuilder()
            .setTitle("🏦 BIÊN LAI THANH TOÁN NỢ NGÂN HÀNG 🧾")
            .setDescription(desc)
            .setColor(cleared ? 0x57F287 : 0xFEE75C);

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async laodong(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);
        const now = Math.floor(Date.now() / 1000);
        const last = u.last_laodong || 0;

        const { totalDebt } = calculateLoanDebt(data, user.id);
        if (totalDebt <= 0n) {
            const msg = "✨ Bạn không có khoản nợ ngân hàng nào để phải đi lao động công ích!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (now - last < 900) {
            const rem = 900 - (now - last);
            const msg = `⏳ Bạn vừa đi lao động công ích mệt rồi, nghỉ ngơi **${Math.floor(rem / 60)}p ${rem % 60}s** nữa mới được cuốc đất tiếp!`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const baseCleared = BigInt(Math.floor(Math.random() * 150_000 + 50_000));
        const pctCleared = (totalDebt * BigInt(Math.floor(Math.random() * 10 + 5))) / 100n;
        const debtClearedVal = baseCleared > pctCleared ? baseCleared : pctCleared;

        const tasks = [
            "Quét dọn sòng bạc Casino sau giờ bão xúc xắc",
            "Lao công chùi rửa toilet phòng Vip Server",
            "Chạy bàn bưng bê nước phục vụ các Đại Gia sòng bạc",
            "Nhặt bóng sân Golf cho các chủ nợ",
            "Làm culi chạy deadline chuộc tội đánh bạc thua"
        ];
        const taskName = tasks[Math.floor(Math.random() * tasks.length)];
        u.last_laodong = now;

        const { actualPaid, remDebt, cleared } = deductLoanDebt(data, user.id, debtClearedVal);
        saveDb(data);

        const statusText = cleared ? "🎉 **BẠN ĐÃ TRẢ HẾT SẠCH TOÀN BỘ NỢ NGÂN HÀNG! TÀI KHOẢN ĐÃ ĐƯỢC TỰ DO!**" : `💳 **Nợ ngân hàng còn lại:** **${formatMoney(remDebt)}** ${COIN}`;

        const embed = new EmbedBuilder()
            .setTitle("👮 LAO ĐỘNG CÔNG ÍCH CHUỘC NỢ 🧹")
            .setDescription(`**Con nợ:** <@${user.id}>\n` +
                            `🔨 **Công việc:** *${taskName}*\n` +
                            `✨ **Được trừ nợ:** **-${formatMoney(actualPaid)}** ${COIN}\n\n` +
                            `${statusText}`)
            .setColor(cleared ? 0x57F287 : 0xE67E22)
            .setFooter({ text: "Mỗi 15 phút được lao động công ích 1 lần để xóa 50k - 200k nợ!" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async daily(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);
        const now = Math.floor(Date.now() / 1000);
        const last = u.last_daily || 0;

        if (now - last < 86400) {
            const rem = 86400 - (now - last);
            const msg = `⏳ Bạn đã điểm danh hôm nay rồi! Quay lại sau **${Math.floor(rem / 3600)}h ${Math.floor((rem % 3600) / 60)}p**.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        let streak = u.streak || 0;
        if (now - last < 172800) streak += 1;
        else streak = 1;

        const baseReward = 10_000;
        const streakBonus = Math.min(streak * 2_000, 40_000);
        const totalReward = baseReward + streakBonus;

        u.wallet = Number(BigInt(u.wallet || 0) + BigInt(totalReward));
        u.last_daily = now;
        u.streak = streak;
        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("🎁 ĐIỂM DANH HÀNG NGÀY (DAILY)")
            .setDescription(`🎉 Bạn nhận được **+${formatMoney(totalReward)}** ${COIN}!\n` +
                            `• Lương cơ bản: \`+${formatMoney(baseReward)}\` ${COIN}\n` +
                            `• Thưởng chuỗi (Streak 🔥 ${streak} ngày): \`+${formatMoney(streakBonus)}\` ${COIN}\n` +
                            `💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
            .setColor(0x57F287);

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async work(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);
        const now = Math.floor(Date.now() / 1000);
        const last = u.last_work || 0;

        if (now - last < 1800) {
            const rem = 1800 - (now - last);
            const msg = `⏳ Bạn vừa đi làm mệt rồi, nghỉ ngơi **${Math.floor(rem / 60)}p ${rem % 60}s** nữa nhé!`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const jobs = [
            { name: "Chạy Grab buổi tối", salary: Math.floor(Math.random() * 5_000 + 5_000) },
            { name: "Lập trình viên fix bug cho sếp", salary: Math.floor(Math.random() * 10_000 + 10_000) },
            { name: "Bán trà đá vỉa hè", salary: Math.floor(Math.random() * 7_000 + 5_000) },
            { name: "Streamer game giải trí", salary: Math.floor(Math.random() * 10_000 + 8_000) }
        ];
        const job = jobs[Math.floor(Math.random() * jobs.length)];

        u.wallet = Number(BigInt(u.wallet || 0) + BigInt(job.salary));
        u.last_work = now;
        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("💼 LÀM VIỆC CHĂM CHỈ (WORK)")
            .setDescription(`👷 Bạn đã làm công việc: **${job.name}**\n` +
                            `💵 Tiền lương nhận được: **+${formatMoney(job.salary)}** ${COIN}\n` +
                            `💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
            .setColor(0x3498DB);

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async beg(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        const u = getUser(data, user.id);
        const now = Math.floor(Date.now() / 1000);
        const last = u.last_beg || 0;

        if (now - last < 300) {
            const rem = 300 - (now - last);
            const msg = `⏳ Mặt dày vừa thôi, xin xỏ gì lắm! Đợi **${Math.floor(rem / 60)}p ${rem % 60}s** nữa đi xin tiếp.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const money = Math.floor(Math.random() * 2_500 + 500);
        u.wallet = Number(BigInt(u.wallet || 0) + BigInt(money));
        u.last_beg = now;
        saveDb(data);

        return isSlash ? interactionOrMsg.reply(`🥺 Đại gia đi ngang qua bố thí cho bạn **+${formatMoney(money)}** ${COIN}! Ví: **${formatMoney(u.wallet)}** ${COIN}`) : interactionOrMsg.channel.send(`🥺 Đại gia đi ngang qua bố thí cho bạn **+${formatMoney(money)}** ${COIN}! Ví: **${formatMoney(u.wallet)}** ${COIN}`);
    },

    async rob(interactionOrMsg, targetMember) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (!targetMember || targetMember.id === user.id) {
            const msg = "❌ Bạn không thể tự trộm chính mình!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        const robber = getUser(data, user.id);
        const victim = getUser(data, targetMember.id);
        const now = Math.floor(Date.now() / 1000);

        if (now - (robber.last_rob || 0) < 600) {
            const rem = 600 - (now - (robber.last_rob || 0));
            const msg = `⏳ Cảnh sát đang tuần tra! Đợi **${Math.floor(rem / 60)}p ${rem % 60}s** nữa mới được hành nghề trộm cắp.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(victim.wallet || 0) < 5_000n) {
            const msg = "❌ Nạn nhân quá nghèo, ví không có nổi 5,000 💵 để trộm!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        robber.last_rob = now;
        const success = Math.random() < 0.45;

        if (success) {
            const pct = Math.random() * 0.15 + 0.10;
            const stolen = BigInt(Math.floor(Number(victim.wallet) * pct));
            victim.wallet = Number(BigInt(victim.wallet) - stolen);
            robber.wallet = Number(BigInt(robber.wallet) + stolen);
            saveDb(data);

            const msg = `🥷 <@${user.id}> đã móc túi thành công <@${targetMember.id}> lấy trộm **+${formatMoney(stolen)}** ${COIN}!`;
            return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
        } else {
            const fine = BigInt(Math.floor(Number(robber.wallet || 0) * 0.15));
            robber.wallet = Number(BigInt(robber.wallet) - fine);
            addTreasury(data, fine);
            saveDb(data);

            const msg = `👮 <@${user.id}> bị cảnh sát tóm sống khi đang trộm <@${targetMember.id}>! Bị phạt **-${formatMoney(fine)}** ${COIN} nộp Kho Bạc!`;
            return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
        }
    },

    async pay(interactionOrMsg, targetMember, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (!targetMember || targetMember.id === user.id) {
            const msg = "❌ Người nhận không hợp lệ!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        applyBankTax(data);

        const { isOverdue, totalDebt } = calculateLoanDebt(data, user.id);
        if (isOverdue) {
            const msg = `🚨 **TÀI KHOẢN BỊ PHONG TỎA CHUYỂN TIỀN!**\n💀 Bạn đang có nợ quá hạn **${formatMoney(totalDebt)}** ${COIN}! Hãy trả nợ trước.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const sender = getUser(data, user.id);
        const receiver = getUser(data, targetMember.id);

        const payAmt = parseAmount(amountStr, sender.wallet || 0);
        if (payAmt <= 0n) {
            const msg = "❌ Số tiền chuyển không hợp lệ! (Ví dụ: `!pay @user 10m`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(sender.wallet || 0) < payAmt) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Hiện có: **${formatMoney(sender.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const tax = (payAmt * 20n) / 100n;
        const netReceived = payAmt - tax;

        sender.wallet = Number(BigInt(sender.wallet) - payAmt);
        receiver.wallet = Number(BigInt(receiver.wallet || 0) + netReceived);
        addTreasury(data, tax);
        saveDb(data);

        const msg = `💸 **CHUYỂN KHOẢN THÀNH CÔNG!**\n• <@${user.id}> chuyển: **${formatMoney(payAmt)}** ${COIN}\n• Phí giao dịch (20% nộp Kho Bạc): **-${formatMoney(tax)}** ${COIN}\n• <@${targetMember.id}> thực nhận: **+${formatMoney(netReceived)}** ${COIN}!`;
        return isSlash ? interactionOrMsg.reply(msg) : interactionOrMsg.channel.send(msg);
    },

    async top(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const data = loadDb();
        applyBankTax(data);

        const userList = [];
        for (const uid in data.users) {
            const u = data.users[uid];
            const total = BigInt(u.wallet || 0) + BigInt(u.bank || 0);
            if (total > 0n) {
                userList.push({ uid, total, wallet: u.wallet, bank: u.bank });
            }
        }

        userList.sort((a, b) => (b.total > a.total ? 1 : -1));
        const top10 = userList.slice(0, 10);

        let desc = top10.length === 0 ? "Chưa có đại gia nào có tiền!" : "";
        const medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"];

        top10.forEach((item, index) => {
            desc += `${medals[index]} <@${item.uid}>: **${formatMoney(item.total)}** ${COIN}\n` +
                    `   *(Ví: ${formatMoney(item.wallet)} • Bank: ${formatMoney(item.bank)})*\n`;
        });

        const embed = new EmbedBuilder()
            .setTitle("🏆 BẢNG XẾP HẠNG ĐẠI GIA SERVER (TOP WEALTH)")
            .setDescription(desc)
            .setColor(0xFEE75C);

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    async topno(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const data = loadDb();

        const debtList = [];
        for (const uid in data.loans) {
            const { totalDebt, principal, interest, isOverdue } = calculateLoanDebt(data, uid);
            if (totalDebt > 0n) {
                debtList.push({ uid, totalDebt, principal, interest, isOverdue });
            }
        }

        debtList.sort((a, b) => (b.totalDebt > a.totalDebt ? 1 : -1));
        const top10 = debtList.slice(0, 10);

        let desc = top10.length === 0 ? "🎉 Server bình yên, không ai nợ nần!" : "";
        top10.forEach((item, index) => {
            const tag = item.isOverdue ? "💀 *(Quá hạn)*" : "⏳ *(Đang vay)*";
            desc += `**#${index + 1}** <@${item.uid}>: **${formatMoney(item.totalDebt)}** ${COIN} ${tag}\n` +
                    `   *(Gốc: ${formatMoney(item.principal)} • Lãi: +${formatMoney(item.interest)})*\n`;
        });

        const embed = new EmbedBuilder()
            .setTitle("💀 BẢNG PHONG THẦN CHÚA CHỔM (TOP NỢ NGÂN HÀNG)")
            .setDescription(desc)
            .setColor(0xED4245);

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    }
};
