const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } = require('discord.js');
const {
    loadDb,
    saveDb,
    getUser,
    parseAmount,
    formatMoney,
    addTreasury,
    applyBankTax,
    checkCasinoLockout
} = require('../utils/database');

const COIN = "💵";

module.exports = {
    // ================= 1. KÉO BÚA BAO SOLO (RPS) =================
    async rps(interactionOrMsg, opponentMember, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (!opponentMember || opponentMember.id === user.id || opponentMember.bot) {
            const msg = "❌ Vui lòng thách đấu một thành viên hợp lệ (không phải bot hoặc chính mình)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        applyBankTax(data);
        const p1 = getUser(data, user.id);
        const p2 = getUser(data, opponentMember.id);

        const betVal = parseAmount(amountStr, p1.wallet || 0);
        if (betVal <= 0n) {
            const msg = "❌ Tiền cược không hợp lệ! (Ví dụ: `!rps @user 10m`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(p1.wallet || 0) < betVal) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Ví: **${formatMoney(p1.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(p2.wallet || 0) < betVal) {
            const msg = `❌ Đối thủ không đủ tiền trong ví! (Ví đối thủ: **${formatMoney(p2.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('rps_rock').setLabel('🪨 Búa').setStyle(ButtonStyle.Primary),
            new ButtonBuilder().setCustomId('rps_paper').setLabel('📄 Bao').setStyle(ButtonStyle.Primary),
            new ButtonBuilder().setCustomId('rps_scissors').setLabel('✂️ Kéo').setStyle(ButtonStyle.Primary)
        );

        const embed = new EmbedBuilder()
            .setTitle("⚔️ THÁCH ĐẤU KÉO BÚA BAO SOLO 1v1 ⚔️")
            .setDescription(`• **Người thách đấu:** <@${user.id}>\n` +
                            `• **Đối thủ:** <@${opponentMember.id}>\n` +
                            `• **Tiền cược:** **${formatMoney(betVal)}** ${COIN}\n\n` +
                            `👉 Cả 2 người hãy bấm nút bí mật bên dưới để chọn nước đi (Thời hạn: 60s)!`)
            .setColor(0x5865F2);

        let message;
        if (isSlash) message = await interactionOrMsg.reply({ embeds: [embed], components: [row], fetchReply: true });
        else message = await interactionOrMsg.channel.send({ embeds: [embed], components: [row] });

        const choices = {};
        const collector = message.createMessageComponentCollector({
            componentType: ComponentType.Button,
            time: 60000
        });

        collector.on('collect', async (btnInt) => {
            if (![user.id, opponentMember.id].includes(btnInt.user.id)) {
                return btnInt.reply({ content: "❌ Bạn không tham gia kèo đấu này!", ephemeral: true });
            }

            if (choices[btnInt.user.id]) {
                return btnInt.reply({ content: "⚠️ Bạn đã chọn rồi, không được đổi ý!", ephemeral: true });
            }

            const val = btnInt.customId.replace('rps_', '');
            choices[btnInt.user.id] = val;
            await btnInt.reply({ content: `✅ Bạn đã chọn bí mật thành công!`, ephemeral: true });

            if (choices[user.id] && choices[opponentMember.id]) {
                collector.stop('done');
            }
        });

        collector.on('end', async (collected, reason) => {
            if (reason !== 'done') {
                const cancelEmbed = new EmbedBuilder()
                    .setTitle("⏰ KÈO ĐẤU ĐÃ BỊ HỦY DO HẾT THỜI GIAN!")
                    .setDescription("Một trong hai người chơi đã không kịp ra tay sau 60 giây.")
                    .setColor(0xED4245);
                try { await message.edit({ embeds: [cancelEmbed], components: [] }); } catch {}
                return;
            }

            const c1 = choices[user.id];
            const c2 = choices[opponentMember.id];

            const nameMap = { rock: "🪨 Búa", paper: "📄 Bao", scissors: "✂️ Kéo" };

            const freshDb = loadDb();
            const freshP1 = getUser(freshDb, user.id);
            const freshP2 = getUser(freshDb, opponentMember.id);

            let resultDesc = "";
            let color = 0x5865F2;

            if (c1 === c2) {
                resultDesc = `🤝 **KẾT QUẢ: HÒA NHAU!**\n• <@${user.id}> ra: **${nameMap[c1]}**\n• <@${opponentMember.id}> ra: **${nameMap[c2]}**\n✨ Không ai bị trừ tiền cược!`;
                color = 0xFEE75C;
            } else if (
                (c1 === 'rock' && c2 === 'scissors') ||
                (c1 === 'paper' && c2 === 'rock') ||
                (c1 === 'scissors' && c2 === 'paper')
            ) {
                const tax = (betVal * 10n) / 100n;
                const netWin = betVal - tax;

                freshP2.wallet = Number(BigInt(freshP2.wallet) - betVal);
                freshP1.wallet = Number(BigInt(freshP1.wallet) + netWin);
                addTreasury(freshDb, tax);
                saveDb(freshDb);

                resultDesc = `👑 **<@${user.id}> ĐÃ CHIẾN THẮNG!**\n• <@${user.id}>: **${nameMap[c1]}**\n• <@${opponentMember.id}>: **${nameMap[c2]}**\n\n🏆 <@${user.id}> nhận: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!\n💸 <@${opponentMember.id}> mất: **-${formatMoney(betVal)}** ${COIN}!`;
                color = 0x57F287;
            } else {
                const tax = (betVal * 10n) / 100n;
                const netWin = betVal - tax;

                freshP1.wallet = Number(BigInt(freshP1.wallet) - betVal);
                freshP2.wallet = Number(BigInt(freshP2.wallet) + netWin);
                addTreasury(freshDb, tax);
                saveDb(freshDb);

                resultDesc = `👑 **<@${opponentMember.id}> ĐÃ CHIẾN THẮNG!**\n• <@${user.id}>: **${nameMap[c1]}**\n• <@${opponentMember.id}>: **${nameMap[c2]}**\n\n🏆 <@${opponentMember.id}> nhận: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!\n💸 <@${user.id}> mất: **-${formatMoney(betVal)}** ${COIN}!`;
                color = 0x57F287;
            }

            const finalEmbed = new EmbedBuilder()
                .setTitle("⚔️ KẾT QUẢ KÉO BÚA BAO SOLO ⚔️")
                .setDescription(resultDesc)
                .setColor(color);

            try { await message.edit({ embeds: [finalEmbed], components: [] }); } catch {}
        });
    },

    // ================= 2. LÌ XÌ SERVER =================
    async lixi(interactionOrMsg, amountStr, countStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const host = getUser(data, user.id);

        const totalAmt = parseAmount(amountStr, host.wallet || 0);
        const slotsCount = parseInt(countStr, 10);

        if (totalAmt <= 0n || isNaN(slotsCount) || slotsCount < 1 || slotsCount > 50) {
            const msg = "❌ Cú pháp không hợp lệ! (Ví dụ: `!lixi 100m 5` — Phát 100M cho 5 người)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(host.wallet || 0) < totalAmt) {
            const msg = `❌ Ví không đủ tiền để phát lì xì! (Ví: **${formatMoney(host.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        host.wallet = Number(BigInt(host.wallet) - totalAmt);
        saveDb(data);

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('claim_lixi').setLabel('🧧 Giật Lì Xì Ngay!').setStyle(ButtonStyle.Danger)
        );

        const embed = new EmbedBuilder()
            .setTitle("🧧 BAO LÌ XÌ MAY MẮN TOÀN SERVER 🧧")
            .setDescription(`🎉 **Đại gia <@${user.id}>** vừa ném ra một bao lì xì siêu to khổng lồ!\n\n` +
                            `• **Tổng số tiền:** **${formatMoney(totalAmt)}** ${COIN}\n` +
                            `• **Số người được nhận:** **${slotsCount} người**\n\n` +
                            `👉 Nhanh tay bấm nút bên dưới để giật lì xì! (Thời hạn: 60s)`)
            .setColor(0xED4245);

        let message;
        if (isSlash) message = await interactionOrMsg.reply({ embeds: [embed], components: [row], fetchReply: true });
        else message = await interactionOrMsg.channel.send({ embeds: [embed], components: [row] });

        const claimers = new Map();
        let remainingAmt = totalAmt;
        let remainingSlots = slotsCount;

        const collector = message.createMessageComponentCollector({
            componentType: ComponentType.Button,
            time: 60000
        });

        collector.on('collect', async (btnInt) => {
            if (claimers.has(btnInt.user.id)) {
                return btnInt.reply({ content: "❌ Bạn đã giật bao này rồi, đừng tham lam!", ephemeral: true });
            }

            let gotAmt = 0n;
            if (remainingSlots === 1) {
                gotAmt = remainingAmt;
            } else {
                const maxShare = Number((remainingAmt * 2n) / BigInt(remainingSlots));
                const minShare = Number(remainingAmt / BigInt(remainingSlots * 3));
                const randShare = Math.floor(Math.random() * (maxShare - minShare + 1)) + minShare;
                gotAmt = BigInt(Math.max(1, randShare));
                if (gotAmt >= remainingAmt) gotAmt = remainingAmt - BigInt(remainingSlots - 1);
            }

            remainingAmt -= gotAmt;
            remainingSlots -= 1;
            claimers.set(btnInt.user.id, gotAmt);

            const userDb = loadDb();
            const luckyUser = getUser(userDb, btnInt.user.id);
            luckyUser.wallet = Number(BigInt(luckyUser.wallet || 0) + gotAmt);
            saveDb(userDb);

            await btnInt.reply({ content: `🎉 Bạn đã giật được **+${formatMoney(gotAmt)}** ${COIN} lì xì!`, ephemeral: true });

            if (remainingSlots <= 0) {
                collector.stop('full');
            }
        });

        collector.on('end', async () => {
            let desc = `🧧 **BAO LÌ XÌ ĐÃ KẾT THÚC!**\n• Đại gia phát: <@${user.id}> (**${formatMoney(totalAmt)}** ${COIN})\n\n**Danh sách người may mắn:**\n`;
            if (claimers.size === 0) {
                desc += "*(Không có ai giật lì xì, tiền đã hoàn lại ví đại gia)*";
                const refundDb = loadDb();
                const hostU = getUser(refundDb, user.id);
                hostU.wallet = Number(BigInt(hostU.wallet) + totalAmt);
                saveDb(refundDb);
            } else {
                claimers.forEach((amt, uid) => {
                    desc += `• <@${uid}>: **+${formatMoney(amt)}** ${COIN}\n`;
                });
                if (remainingAmt > 0n) {
                    desc += `\n✨ Hoàn lại **+${formatMoney(remainingAmt)}** ${COIN} chưa ai giật về ví <@${user.id}>!`;
                    const refundDb = loadDb();
                    const hostU = getUser(refundDb, user.id);
                    hostU.wallet = Number(BigInt(hostU.wallet) + remainingAmt);
                    saveDb(refundDb);
                }
            }

            const endEmbed = new EmbedBuilder()
                .setTitle("🧧 TỔNG KẾT BAO LÌ XÌ SERVER 🧧")
                .setDescription(desc)
                .setColor(0xFEE75C);

            try { await message.edit({ embeds: [endEmbed], components: [] }); } catch {}
        });
    }
};
