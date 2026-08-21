const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } = require('discord.js');
const {
    loadDb,
    saveDb,
    getUser,
    parseAmount,
    formatMoney,
    addTreasury,
    applyBankTax,
    calculateWinRate,
    checkCasinoLockout
} = require('../utils/database');

const COIN = "💵";
const SUITS = ['♠️', '♥️', '♦️', '♣️'];
const RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];

function drawCard() {
    const rank = RANKS[Math.floor(Math.random() * RANKS.length)];
    const suit = SUITS[Math.floor(Math.random() * SUITS.length)];
    return { rank, suit };
}

function cardToStr(c) {
    return `\`${c.rank}${c.suit}\``;
}

function calculateHand(hand) {
    let val = 0;
    let aces = 0;
    for (const c of hand) {
        if (['10', 'J', 'Q', 'K'].includes(c.rank)) {
            val += 10;
        } else if (c.rank === 'A') {
            val += 11;
            aces += 1;
        } else {
            val += parseInt(c.rank, 10);
        }
    }
    while (val > 21 && aces > 0) {
        val -= 10;
        aces -= 1;
    }
    return val;
}

function isXiBang(hand) {
    return hand.length === 2 && hand[0].rank === 'A' && hand[1].rank === 'A';
}

function isXiDach(hand) {
    if (hand.length !== 2) return false;
    const ranks = [hand[0].rank, hand[1].rank];
    const hasAce = ranks.includes('A');
    const hasTen = ranks.some(r => ['10', 'J', 'Q', 'K'].includes(r));
    return hasAce && hasTen;
}

function isNguLinh(hand) {
    return hand.length === 5 && calculateHand(hand) <= 21;
}

function getHandDisplay(hand) {
    const val = calculateHand(hand);
    const cardsStr = hand.map(cardToStr).join(' ');
    if (isXiBang(hand)) return `${cardsStr} \`(XÌ BÀNG 🌟🌟)\``;
    if (isXiDach(hand)) return `${cardsStr} \`(XÌ DÁCH 🌟)\``;
    if (hand.length === 5 && val <= 21) return `${cardsStr} \`(NGŨ LINH ${val}đ)\``;
    if (val > 21) return `${cardsStr} \`(QUẮC ${val}đ)\``;
    return `${cardsStr} \`(${val} điểm)\``;
}

function recordGame(u, won, profit) {
    u.casino_games = (u.casino_games || 0) + 1;
    if (won) u.casino_wins = (u.casino_wins || 0) + 1;
    u.casino_profit = (u.casino_profit || 0) + Number(profit);
}

const activeBjPlayers = new Set();

module.exports = {
    activeBjPlayers,

    // ================= 1. TÀI XỈU =================
    async tx(interactionOrMsg, amountStr, choice) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const betVal = parseAmount(amountStr, u.wallet || 0);
        if (betVal <= 0n) {
            const msg = "❌ Số tiền cược không hợp lệ! (Ví dụ: `!tx 500k t`, `!tx 10b x`, `!tx all t`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const c = String(choice).toLowerCase();
        let userChoice = "";
        if (['t', 'tai', 'tài'].includes(c)) userChoice = "tai";
        else if (['x', 'xiu', 'xỉu'].includes(c)) userChoice = "xiu";
        else {
            const msg = "❌ Vui lòng chọn `t` (Tài) hoặc `x` (Xỉu)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { isLocked, totalDebt } = checkCasinoLockout(data, user.id);
        if (isLocked) {
            const msg = `🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n💀 Bạn đang có nợ quá hạn **${formatMoney(totalDebt)}** ${COIN}!\n👉 Bắt buộc phải trả nợ (\`!trano\`, \`!laodong\`) mới được mở lại sòng bạc.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.wallet || 0) < betVal) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Ví: **${formatMoney(u.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const winProb = calculateWinRate(data, user.id, betVal);
        const userWon = Math.random() < winProb;

        let d1, d2, d3, actual, isBao = false;

        if (userWon) {
            actual = userChoice;
            if (actual === 'tai') {
                d1 = Math.floor(Math.random() * 4 + 3);
                d2 = Math.floor(Math.random() * 3 + 4);
                d3 = Math.floor(Math.random() * 3 + 4);
                if (d1 === d2 && d2 === d3) d1 = (d1 % 6) + 1;
            } else {
                d1 = Math.floor(Math.random() * 3 + 1);
                d2 = Math.floor(Math.random() * 3 + 1);
                d3 = Math.floor(Math.random() * 4 + 1);
                if (d1 === d2 && d2 === d3) d1 = (d1 % 3) + 1;
            }
        } else {
            if (Math.random() < 0.15) {
                const bVal = Math.floor(Math.random() * 6 + 1);
                d1 = bVal; d2 = bVal; d3 = bVal;
                isBao = true;
                actual = (d1 * 3) <= 10 ? 'xiu' : 'tai';
            } else {
                actual = userChoice === 'tai' ? 'xiu' : 'tai';
                if (actual === 'tai') {
                    d1 = Math.floor(Math.random() * 4 + 3);
                    d2 = Math.floor(Math.random() * 3 + 4);
                    d3 = Math.floor(Math.random() * 3 + 4);
                    if (d1 === d2 && d2 === d3) d1 = (d1 % 6) + 1;
                } else {
                    d1 = Math.floor(Math.random() * 3 + 1);
                    d2 = Math.floor(Math.random() * 3 + 1);
                    d3 = Math.floor(Math.random() * 4 + 1);
                    if (d1 === d2 && d2 === d3) d1 = (d1 % 3) + 1;
                }
            }
        }

        const total = d1 + d2 + d3;
        const dStr = `🎲 \`${d1}\` + \`${d2}\` + \`${d3}\` = **${total} điểm**`;

        let msg = "";
        let color = 0x5865F2;

        if (isBao) {
            u.wallet = Number(BigInt(u.wallet) - betVal);
            recordGame(u, false, -betVal);
            msg = `🌪️ **BÃO XÚC XẮC 3 CON ${d1}!**\n💀 Nhà cái hốt trọn ổ cả làng! Mất **-${formatMoney(betVal)}** ${COIN}!`;
            color = 0xED4245;
        } else if (userWon) {
            const tax = (betVal * 10n) / 100n;
            const netWin = betVal - tax;
            u.wallet = Number(BigInt(u.wallet) + netWin);
            recordGame(u, true, netWin);
            addTreasury(data, tax);
            msg = `🎉 **BẠN ĐOÁN ĐÚNG (${actual.toUpperCase()})!**\n🏆 Thắng: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!`;
            color = 0x57F287;
        } else {
            u.wallet = Number(BigInt(u.wallet) - betVal);
            recordGame(u, false, -betVal);
            msg = `💀 **BẠN ĐOÁN SAI (${actual.toUpperCase()})!**\n💸 Mất **-${formatMoney(betVal)}** ${COIN}!`;
            color = 0xED4245;
        }

        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("🎲 SÒNG BẠC TÀI XỈU 🎲")
            .setDescription(`**Người chơi:** <@${user.id}> | **Cược:** **${formatMoney(betVal)}** ${COIN} vào **${userChoice.toUpperCase()}**\n\n` +
                            `${dStr}\n\n${msg}\n💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
            .setColor(color)
            .setFooter({ text: "Thuế thắng cược: 10% nộp vào Kho Bạc Bot" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    // ================= 2. XÌ DÁCH BLACKJACK =================
    async bj(interactionOrMsg, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        if (activeBjPlayers.has(user.id)) {
            const msg = "❌ Bạn đang có 1 ván Xì Dách đang chạy! Hãy hoàn thành ván đó hoặc đợi hết 30s đếm ngược.";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const betVal = parseAmount(amountStr, u.wallet || 0);
        if (betVal <= 0n) {
            const msg = "❌ Tiền cược không hợp lệ! (Ví dụ: `!bj 10m`, `!bj 5b`, `!bj all`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { isLocked, totalDebt } = checkCasinoLockout(data, user.id);
        if (isLocked) {
            const msg = `🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n💀 Bạn đang có nợ quá hạn **${formatMoney(totalDebt)}** ${COIN}!\n👉 Bắt buộc phải trả nợ (\`!trano\`, \`!laodong\`) mới được mở lại sòng bạc.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.wallet || 0) < betVal) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Ví: **${formatMoney(u.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        // 🚨 TRỪ TIỀN CƯỢC NGAY LẬP TỨC ĐỂ CHỐNG THOÁT VÁN
        u.wallet = Number(BigInt(u.wallet) - betVal);
        saveDb(data);
        activeBjPlayers.add(user.id);

        const playerHand = [drawCard(), drawCard()];
        const dealerHand = [drawCard(), drawCard()];

        const pXb = isXiBang(playerHand);
        const pXd = isXiDach(playerHand);
        const dXb = isXiBang(dealerHand);
        const dXd = isXiDach(dealerHand);

        // Xử lý các thế bài đặc biệt ban đầu
        if (pXb || pXd || dXb || dXd) {
            activeBjPlayers.delete(user.id);
            const pCardsStr = getHandDisplay(playerHand);
            const dCardsStr = getHandDisplay(dealerHand);

            if (pXb && dXb) {
                // Cả 2 Xì Bàng -> Hòa hoàn cược gốc
                u.wallet = Number(BigInt(u.wallet) + betVal);
                saveDb(data);
                const embed = new EmbedBuilder()
                    .setTitle("🃏 SONG LONG XÌ BÀNG HÒA NHAU! 🤝")
                    .setDescription(`• **Bài Của Bạn:** ${pCardsStr}\n• **Bài Nhà Cái:** ${dCardsStr}\n\n🤝 Cả 2 đều có Xì Bàng! Hoàn lại tiền cược **+${formatMoney(betVal)}** ${COIN}.\n💰 Ví: **${formatMoney(u.wallet)}** ${COIN}`)
                    .setColor(0xFEE75C);
                return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
            } else if (pXb) {
                // Thắng Xì Bàng x2
                const rawProfit = betVal * 2n;
                const tax = (rawProfit * 10n) / 100n;
                const netProfit = rawProfit - tax;
                const totalReturn = betVal + netProfit;
                u.wallet = Number(BigInt(u.wallet) + totalReturn);
                recordGame(u, true, netProfit);
                addTreasury(data, tax);
                saveDb(data);

                const embed = new EmbedBuilder()
                    .setTitle("🌟 XÌ BÀNG THẦN THÁNH (2 CÂY ÁT)! 👑")
                    .setDescription(`• **Bài Của Bạn:** ${pCardsStr}\n• **Bài Nhà Cái:** ${dCardsStr}\n\n🏆 Bạn đã hạ gục Nhà Cái! Thắng gấp đôi: Hoàn cược + Lãi **+${formatMoney(totalReturn)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!\n💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
                    .setColor(0xFEE75C);
                return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
            } else if (dXb) {
                recordGame(u, false, -betVal);
                saveDb(data);

                const embed = new EmbedBuilder()
                    .setTitle("💀 NHÀ CÁI XÌ BÀNG ĂN SẠCH! 🎰")
                    .setDescription(`• **Bài Của Bạn:** ${pCardsStr}\n• **Bài Nhà Cái:** ${dCardsStr}\n\n💸 Bạn đã mất **-${formatMoney(betVal)}** ${COIN}!\n💰 Ví còn: **${formatMoney(u.wallet)}** ${COIN}`)
                    .setColor(0xED4245);
                return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
            } else if (pXd && dXd) {
                u.wallet = Number(BigInt(u.wallet) + betVal);
                saveDb(data);
                const embed = new EmbedBuilder()
                    .setTitle("🃏 CẢ HAI CÙNG XÌ DÁCH HÒA NHAU! 🤝")
                    .setDescription(`• **Bài Của Bạn:** ${pCardsStr}\n• **Bài Nhà Cái:** ${dCardsStr}\n\n🤝 Hòa nhau! Hoàn lại tiền cược **+${formatMoney(betVal)}** ${COIN}.\n💰 Ví: **${formatMoney(u.wallet)}** ${COIN}`)
                    .setColor(0xFEE75C);
                return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
            } else if (pXd) {
                const rawProfit = (betVal * 15n) / 10n;
                const tax = (rawProfit * 10n) / 100n;
                const netProfit = rawProfit - tax;
                const totalReturn = betVal + netProfit;
                u.wallet = Number(BigInt(u.wallet) + totalReturn);
                recordGame(u, true, netProfit);
                addTreasury(data, tax);
                saveDb(data);

                const embed = new EmbedBuilder()
                    .setTitle("🃏 XÌ DÁCH TỰ NHIÊN (BLACKJACK 21)! 🌟")
                    .setDescription(`• **Bài Của Bạn:** ${pCardsStr}\n• **Bài Nhà Cái:** ${dCardsStr}\n\n🏆 Thắng gấp rưỡi! Hoàn cược + Lãi: **+${formatMoney(totalReturn)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!\n💰 Ví: **${formatMoney(u.wallet)}** ${COIN}`)
                    .setColor(0xFEE75C);
                return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
            } else if (dXd) {
                recordGame(u, false, -betVal);
                saveDb(data);

                const embed = new EmbedBuilder()
                    .setTitle("💀 NHÀ CÁI XÌ DÁCH! 🎰")
                    .setDescription(`• **Bài Của Bạn:** ${pCardsStr}\n• **Bài Nhà Cái:** ${dCardsStr}\n\n💸 Bạn đã mất **-${formatMoney(betVal)}** ${COIN}!\n💰 Ví còn: **${formatMoney(u.wallet)}** ${COIN}`)
                    .setColor(0xED4245);
                return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
            }
        }

        // Tạo UI View tương tác với timeout 30s
        function buildEmbed(showDealer = false, outcome = "", color = 0x5865F2) {
            const pDisplay = getHandDisplay(playerHand);
            const dDisplay = showDealer ? getHandDisplay(dealerHand) : `${cardToStr(dealerHand[0])} \`🂠\` \`(? điểm)\``;

            return new EmbedBuilder()
                .setTitle("🃏 SÒNG BẠC XÌ DÁCH (BLACKJACK) 🎰")
                .setDescription(`**Người chơi:** <@${user.id}> | **Tiền cược:** **${formatMoney(betVal)}** ${COIN}\n\n` +
                                `**Bài Nhà Cái:** ${dDisplay}\n` +
                                `**Bài Của Bạn:** ${pDisplay}\n\n` +
                                `${outcome}`)
                .setColor(color)
                .setFooter({ text: "⏳ Đếm ngược: 30 Giây • Bấm 'Rút Bài' hoặc 'Dằn Bài' (Quá 30s bỏ ván bị xử thua mất cược!)" });
        }

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('bj_hit').setLabel('🃏 Rút Bài (Hit)').setStyle(ButtonStyle.Success),
            new ButtonBuilder().setCustomId('bj_stand').setLabel('🛑 Dằn Bài (Stand)').setStyle(ButtonStyle.Danger)
        );

        const initialEmbed = buildEmbed();
        let message;
        if (isSlash) {
            message = await interactionOrMsg.reply({ embeds: [initialEmbed], components: [row], fetchReply: true });
        } else {
            message = await interactionOrMsg.channel.send({ embeds: [initialEmbed], components: [row] });
        }

        const collector = message.createMessageComponentCollector({
            componentType: ComponentType.Button,
            time: 30000
        });

        let finished = false;

        collector.on('collect', async (btnInt) => {
            if (btnInt.user.id !== user.id) {
                return btnInt.reply({ content: "❌ Bàn bài này không phải của bạn!", ephemeral: true });
            }

            const currentDb = loadDb();
            const currentU = getUser(currentDb, user.id);

            if (btnInt.customId === 'bj_hit') {
                playerHand.push(drawCard());
                const pVal = calculateHand(playerHand);

                if (pVal > 21) {
                    finished = true;
                    activeBjPlayers.delete(user.id);
                    collector.stop();

                    recordGame(currentU, false, -betVal);
                    saveDb(currentDb);

                    const endEmbed = buildEmbed(true, `💥 **BẠN ĐÃ BỊ QUẮC (${pVal} > 21 điểm)!**\n💸 Bạn đã mất **-${formatMoney(betVal)}** ${COIN}! Ví còn: **${formatMoney(currentU.wallet)}** ${COIN}.`, 0xED4245);
                    return btnInt.update({ embeds: [endEmbed], components: [] });
                } else if (playerHand.length === 5) {
                    finished = true;
                    activeBjPlayers.delete(user.id);
                    collector.stop();

                    const rawProfit = (betVal * 15n) / 10n;
                    const tax = (rawProfit * 10n) / 100n;
                    const netProfit = rawProfit - tax;
                    const totalReturn = betVal + netProfit;

                    currentU.wallet = Number(BigInt(currentU.wallet) + totalReturn);
                    recordGame(currentU, true, netProfit);
                    addTreasury(currentDb, tax);
                    saveDb(currentDb);

                    const endEmbed = buildEmbed(true, `🌟 **NGŨ LINH THẦN THÁNH (5 LÁ <= 21)!**\n🏆 Hoàn cược **+${formatMoney(betVal)}** + Thắng lãi: **+${formatMoney(netProfit)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!\n💰 Tổng nhận về ví: **+${formatMoney(totalReturn)}** ${COIN} • Ví hiện tại: **${formatMoney(currentU.wallet)}** ${COIN}.`, 0xFEE75C);
                    return btnInt.update({ embeds: [endEmbed], components: [] });
                } else {
                    return btnInt.update({ embeds: [buildEmbed()], components: [row] });
                }
            } else if (btnInt.customId === 'bj_stand') {
                finished = true;
                activeBjPlayers.delete(user.id);
                collector.stop();

                const pVal = calculateHand(playerHand);
                const pNguLinh = isNguLinh(playerHand);

                while (calculateHand(dealerHand) < 17 && dealerHand.length < 5) {
                    dealerHand.push(drawCard());
                }
                const dVal = calculateHand(dealerHand);
                const dNguLinh = isNguLinh(dealerHand);

                let outcome = "";
                let color = 0x5865F2;

                if (pNguLinh && dNguLinh) {
                    if (pVal < dVal) {
                        const rawProfit = (betVal * 15n) / 10n;
                        const tax = (rawProfit * 10n) / 100n;
                        const netProfit = rawProfit - tax;
                        const totalReturn = betVal + netProfit;
                        currentU.wallet = Number(BigInt(currentU.wallet) + totalReturn);
                        recordGame(currentU, true, netProfit);
                        addTreasury(currentDb, tax);
                        outcome = `🌟 **CẢ HAI ĐỀU NGŨ LINH — BẠN THẮNG DO ÍT ĐIỂM HƠN (${pVal} < ${dVal})!**\n🏆 Hoàn cược + Thắng lãi: **+${formatMoney(totalReturn)}** ${COIN}! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0xFEE75C;
                    } else if (pVal > dVal) {
                        recordGame(currentU, false, -betVal);
                        outcome = `💀 **CẢ HAI ĐỀU NGŨ LINH — NHÀ CÁI THẮNG DO ÍT ĐIỂM HƠN (${dVal} < ${pVal})!**\n💸 Mất **-${formatMoney(betVal)}** ${COIN}! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0xED4245;
                    } else {
                        currentU.wallet = Number(BigInt(currentU.wallet) + betVal);
                        outcome = `🤝 **CẢ HAI CÙNG NGŨ LINH BẰNG ĐIỂM (${pVal} ĐIỂM) — HÒA NHAU!**\n✨ Hoàn lại tiền cược **+${formatMoney(betVal)}** ${COIN}! Ví giữ nguyên: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0xFEE75C;
                    }
                } else if (pNguLinh) {
                    const rawProfit = (betVal * 15n) / 10n;
                    const tax = (rawProfit * 10n) / 100n;
                    const netProfit = rawProfit - tax;
                    const totalReturn = betVal + netProfit;
                    currentU.wallet = Number(BigInt(currentU.wallet) + totalReturn);
                    recordGame(currentU, true, netProfit);
                    addTreasury(currentDb, tax);
                    outcome = `🌟 **NGŨ LINH THẦN THÁNH (5 LÁ <= 21)!**\n🏆 Hoàn cược + Thắng lãi: **+${formatMoney(totalReturn)}** ${COIN}! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                    color = 0xFEE75C;
                } else if (dNguLinh) {
                    recordGame(currentU, false, -betVal);
                    outcome = `💀 **NHÀ CÁI ĐẠT NGŨ LINH (5 LÁ <= 21)!**\n💸 Bạn mất **-${formatMoney(betVal)}** ${COIN}! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                    color = 0xED4245;
                } else {
                    if (dVal > 21) {
                        const rawProfit = betVal;
                        const tax = (rawProfit * 10n) / 100n;
                        const netProfit = rawProfit - tax;
                        const totalReturn = betVal + netProfit;
                        currentU.wallet = Number(BigInt(currentU.wallet) + totalReturn);
                        recordGame(currentU, true, netProfit);
                        addTreasury(currentDb, tax);
                        outcome = `🎉 **NHÀ CÁI ĐÃ BỊ QUẮC (${dVal} > 21) — BẠN CHIẾN THẮNG!**\n🏆 Hoàn cược **+${formatMoney(betVal)}** + Thắng nhận: **+${formatMoney(netProfit)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0x57F287;
                    } else if (pVal > dVal) {
                        const rawProfit = betVal;
                        const tax = (rawProfit * 10n) / 100n;
                        const netProfit = rawProfit - tax;
                        const totalReturn = betVal + netProfit;
                        currentU.wallet = Number(BigInt(currentU.wallet) + totalReturn);
                        recordGame(currentU, true, netProfit);
                        addTreasury(currentDb, tax);
                        outcome = `🎉 **BẠN ĐÃ CHIẾN THẮNG (${pVal} vs ${dVal})!**\n🏆 Hoàn cược **+${formatMoney(betVal)}** + Thắng nhận: **+${formatMoney(netProfit)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0x57F287;
                    } else if (pVal === dVal) {
                        currentU.wallet = Number(BigInt(currentU.wallet) + betVal);
                        outcome = `🤝 **HÒA NHAU VỚI NHÀ CÁI (${pVal} vs ${dVal})!**\n✨ Hoàn lại tiền cược **+${formatMoney(betVal)}** ${COIN}! Số dư ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0xFEE75C;
                    } else {
                        recordGame(currentU, false, -betVal);
                        outcome = `💀 **NHÀ CÁI THẮNG (${dVal} vs ${pVal})!**\n💸 Bạn mất **-${formatMoney(betVal)}** ${COIN}! Ví: **${formatMoney(currentU.wallet)}** ${COIN}.`;
                        color = 0xED4245;
                    }
                }

                saveDb(currentDb);
                const endEmbed = buildEmbed(true, outcome, color);
                return btnInt.update({ embeds: [endEmbed], components: [] });
            }
        });

        collector.on('end', async () => {
            if (!finished) {
                activeBjPlayers.delete(user.id);
                const endDb = loadDb();
                const endU = getUser(endDb, user.id);
                recordGame(endU, false, -betVal);
                saveDb(endDb);

                const timeoutEmbed = buildEmbed(true, `⏰ **HẾT GIỜ (30 GIÂY)! BẠN ĐÃ BỎ VÁN — XỬ THUA!**\n💸 Bạn đã mất trắng tiền cược **-${formatMoney(betVal)}** ${COIN} do bỏ ván!\n💰 Ví hiện tại: **${formatMoney(endU.wallet)}** ${COIN}.`, 0x992D22);
                try {
                    await message.edit({ embeds: [timeoutEmbed], components: [] });
                } catch {}
            }
        });
    },

    // ================= 3. TUNG ĐỒNG XU COINFLIP =================
    async cf(interactionOrMsg, amountStr, choice) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const betVal = parseAmount(amountStr, u.wallet || 0);
        if (betVal <= 0n) {
            const msg = "❌ Tiền cược không hợp lệ! (Ví dụ: `!cf 10m s`, `!cf 5b n`, `!cf all s`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const c = String(choice).toLowerCase();
        let userChoice = "";
        if (['s', 'sap', 'sấp'].includes(c)) userChoice = "sap";
        else if (['n', 'ngua', 'ngửa'].includes(c)) userChoice = "ngua";
        else {
            const msg = "❌ Chọn `s` (Sấp) hoặc `n` (Ngửa)!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { isLocked, totalDebt } = checkCasinoLockout(data, user.id);
        if (isLocked) {
            const msg = `🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n💀 Bạn đang có nợ quá hạn **${formatMoney(totalDebt)}** ${COIN}!\n👉 Bắt buộc phải trả nợ trước.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.wallet || 0) < betVal) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Ví: **${formatMoney(u.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const winProb = calculateWinRate(data, user.id, betVal);
        const userWon = Math.random() < winProb;
        const actual = userWon ? userChoice : (userChoice === 'sap' ? 'ngua' : 'sap');
        const coinIcon = actual === 'sap' ? '⚪ **MẶT SẤP**' : '🟡 **MẶT NGỬA**';

        let msg = "";
        let color = 0x5865F2;

        if (userWon) {
            const tax = (betVal * 10n) / 100n;
            const netWin = betVal - tax;
            u.wallet = Number(BigInt(u.wallet) + netWin);
            recordGame(u, true, netWin);
            addTreasury(data, tax);
            msg = `🎉 **ĐOÁN ĐÚNG!** Thắng: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!`;
            color = 0x57F287;
        } else {
            u.wallet = Number(BigInt(u.wallet) - betVal);
            recordGame(u, false, -betVal);
            msg = `💀 **ĐOÁN SAI!** Mất **-${formatMoney(betVal)}** ${COIN}!`;
            color = 0xED4245;
        }

        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("🪙 TUNG ĐỒNG XU MAY RỦI 🪙")
            .setDescription(`Kết quả rơi xuống: ${coinIcon}\n\n${msg}\n💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
            .setColor(color)
            .setFooter({ text: "Thuế thắng: 10% • Tỷ lệ thắng giảm khi cược to!" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    // ================= 4. QUAY HŨ SLOTS =================
    async slot(interactionOrMsg, amountStr) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const betVal = parseAmount(amountStr, u.wallet || 0);
        if (betVal <= 0n) {
            const msg = "❌ Tiền cược không hợp lệ! (Ví dụ: `!slot 10m`, `!slot 5b`, `!slot all`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { isLocked, totalDebt } = checkCasinoLockout(data, user.id);
        if (isLocked) {
            const msg = `🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n💀 Bạn đang có nợ quá hạn **${formatMoney(totalDebt)}** ${COIN}!\n👉 Bắt buộc phải trả nợ trước.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.wallet || 0) < betVal) {
            const msg = `❌ Bạn không đủ tiền trong ví! (Ví: **${formatMoney(u.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const winProb = calculateWinRate(data, user.id, betVal);
        const userWon = Math.random() < winProb;

        const symbols = ["🍎", "🍋", "🍇", "💎", "7️⃣", "👑", "💀", "💩", "🤡"];
        const isAbove10b = betVal > 10_000_000_000n;

        let s1, s2, s3;
        if (userWon) {
            if (!isAbove10b && Math.random() < 0.15) {
                s1 = Math.random() < 0.5 ? "7️⃣" : "👑";
                s2 = s1; s3 = s1;
            } else {
                const fruits = ["🍎", "🍋", "🍇", "💎"];
                s1 = fruits[Math.floor(Math.random() * fruits.length)];
                s2 = s1;
                s3 = Math.random() < 0.35 ? s1 : symbols.filter(s => s !== s1)[Math.floor(Math.random() * (symbols.length - 1))];
            }
        } else {
            const shuffled = [...symbols].sort(() => 0.5 - Math.random());
            s1 = shuffled[0]; s2 = shuffled[1]; s3 = shuffled[2];
            if (['7️⃣', '👑'].includes(s1) && s1 === s2 && s2 === s3) s3 = '🍎';
        }

        const slotStr = `╭──────────╮\n│  ${s1} │ ${s2} │ ${s3}  │\n╰──────────╯`;

        let msg = "";
        let color = 0x5865F2;

        if (s1 === s2 && s2 === s3) {
            const mult = (['7️⃣', '👑'].includes(s1) && !isAbove10b) ? 10n : 5n;
            const rawWin = betVal * mult;
            const tax = (rawWin * 10n) / 100n;
            const netWin = rawWin - tax;
            u.wallet = Number(BigInt(u.wallet) + netWin);
            recordGame(u, true, netWin);
            addTreasury(data, tax);
            const tag = (['7️⃣', '👑'].includes(s1) && !isAbove10b) ? "💥 **JACKPOT NỔ HŨ THẦN THÁNH (X10)!**" : `🌟 **TRÚNG 3 HÌNH ${s1} (X5)!**`;
            msg = `${tag}\n🎉 Thắng nhận: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!`;
            color = 0xFEE75C;
        } else if (s1 === s2 || s2 === s3 || s1 === s3) {
            const rawWin = (betVal * 15n) / 10n;
            const tax = (rawWin * 10n) / 100n;
            const netWin = rawWin - tax;
            u.wallet = Number(BigInt(u.wallet) + netWin);
            recordGame(u, true, netWin);
            addTreasury(data, tax);
            msg = `✨ **TRÚNG 2 HÌNH (X1.5)!**\n🎉 Thắng nhận: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!`;
            color = 0x57F287;
        } else {
            u.wallet = Number(BigInt(u.wallet) - betVal);
            recordGame(u, false, -betVal);
            msg = `💀 Không trúng hình nào! Mất **-${formatMoney(betVal)}** ${COIN}.`;
            color = 0xED4245;
        }

        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("🎰 MÁY XÈNG QUAY HŨ (SLOTS) 🎰")
            .setDescription(`${slotStr}\n\n${msg}\n💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
            .setColor(color)
            .setFooter({ text: "Thuế thắng: 10% nộp vào Kho Bạc Bot" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    // ================= 5. BẦU CUA =================
    async baucua(interactionOrMsg, amountStr, choice) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const user = isSlash ? interactionOrMsg.user : interactionOrMsg.author;

        const data = loadDb();
        applyBankTax(data);
        const u = getUser(data, user.id);

        const betVal = parseAmount(amountStr, u.wallet || 0);
        if (betVal <= 0n) {
            const msg = "❌ Tiền cược không hợp lệ! (Ví dụ: `!bc 10m bau`, `!bc 5b cua`, `!bc all tom`)";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const bcMap = {
            "bau": "🍐 Bầu", "bầu": "🍐 Bầu",
            "cua": "🦀 Cua",
            "tom": "🦐 Tôm", "tôm": "🦐 Tôm",
            "ca": "🐟 Cá", "cá": "🐟 Cá",
            "ga": "🐔 Gà", "gà": "🐔 Gà",
            "nai": "🦌 Nai"
        };
        const choiceKey = String(choice).toLowerCase();
        if (!bcMap[choiceKey]) {
            const msg = "❌ Chọn: `bau`, `cua`, `tom`, `ca`, `ga`, `nai`!";
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const { isLocked, totalDebt } = checkCasinoLockout(data, user.id);
        if (isLocked) {
            const msg = `🚨 **TÀI KHOẢN SÒNG BẠC ĐÃ BỊ PHONG TỎA!**\n💀 Bạn đang có nợ quá hạn **${formatMoney(totalDebt)}** ${COIN}!\n👉 Bắt buộc phải trả nợ trước.`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        if (BigInt(u.wallet || 0) < betVal) {
            const msg = `❌ Ví không đủ tiền! (Ví: **${formatMoney(u.wallet || 0)}** ${COIN})`;
            return isSlash ? interactionOrMsg.reply({ content: msg, ephemeral: true }) : interactionOrMsg.channel.send(msg);
        }

        const allAnimals = ["🍐 Bầu", "🦀 Cua", "🦐 Tôm", "🐟 Cá", "🐔 Gà", "🦌 Nai"];
        const chosenAnimal = bcMap[choiceKey];

        const winProb = calculateWinRate(data, user.id, betVal);
        const userWon = Math.random() < winProb;

        let matchCount = 0;
        let dices = [];

        if (userWon) {
            const rand = Math.random();
            matchCount = rand < 0.80 ? 1 : (rand < 0.98 ? 2 : 3);
            for (let i = 0; i < matchCount; i++) dices.push(chosenAnimal);
            while (dices.length < 3) {
                const others = allAnimals.filter(a => a !== chosenAnimal);
                dices.push(others[Math.floor(Math.random() * others.length)]);
            }
            dices.sort(() => 0.5 - Math.random());
        } else {
            matchCount = 0;
            const others = allAnimals.filter(a => a !== chosenAnimal);
            dices = [
                others[Math.floor(Math.random() * others.length)],
                others[Math.floor(Math.random() * others.length)],
                others[Math.floor(Math.random() * others.length)]
            ];
        }

        const dStr = dices.join(" | ");
        let msg = "";
        let color = 0x5865F2;

        if (matchCount > 0) {
            const rawWin = betVal * BigInt(matchCount);
            const tax = (rawWin * 10n) / 100n;
            const netWin = rawWin - tax;
            u.wallet = Number(BigInt(u.wallet) + netWin);
            recordGame(u, true, netWin);
            addTreasury(data, tax);
            msg = `🎉 **TRÚNG ${matchCount} CON ${chosenAnimal}!**\n🏆 Thắng: **+${formatMoney(netWin)}** ${COIN} *(Thuế 10%: -${formatMoney(tax)} ${COIN})*!`;
            color = 0x57F287;
        } else {
            u.wallet = Number(BigInt(u.wallet) - betVal);
            recordGame(u, false, -betVal);
            msg = `💀 **TRẬT LẤT!** Mất **-${formatMoney(betVal)}** ${COIN}.`;
            color = 0xED4245;
        }

        saveDb(data);

        const embed = new EmbedBuilder()
            .setTitle("🦞 SÒNG BẠC BẦU CUA TÔM CÁ 🎲")
            .setDescription(`**Người chơi:** <@${user.id}> | **Cược:** **${formatMoney(betVal)}** ${COIN} vào **${chosenAnimal}**\n\n` +
                            `🎲 **Kết quả:** [ ${dStr} ]\n\n${msg}\n💰 Ví hiện tại: **${formatMoney(u.wallet)}** ${COIN}`)
            .setColor(color)
            .setFooter({ text: "Thuế thắng: 10% nộp vào Kho Bạc Bot" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    },

    // ================= 6. TOP WIN RATE =================
    async topwin(interactionOrMsg) {
        const isSlash = interactionOrMsg.isChatInputCommand?.();
        const data = loadDb();

        const players = [];
        for (const uid in data.users) {
            const u = data.users[uid];
            const games = u.casino_games || 0;
            const wins = u.casino_wins || 0;
            const profit = u.casino_profit || 0;

            if (games >= 5) {
                const winRate = ((wins / games) * 100).toFixed(1);
                players.push({ uid, games, wins, winRate: parseFloat(winRate), profit });
            }
        }

        players.sort((a, b) => b.winRate - a.winRate || b.games - a.games);
        const top10 = players.slice(0, 10);

        let desc = top10.length === 0 ? "Chưa có đủ dữ liệu sòng bạc (Cần tối thiểu 5 ván chơi)!" : "";
        const medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"];

        top10.forEach((p, idx) => {
            const profitTag = p.profit >= 0 ? `+${formatMoney(p.profit)}` : `-${formatMoney(Math.abs(p.profit))}`;
            desc += `${medals[idx]} <@${p.uid}> — **${p.winRate}%** Win Rate\n` +
                    `   *(Thắng: ${p.wins}/${p.games} ván • Lãi ròng: ${profitTag} ${COIN})*\n`;
        });

        const embed = new EmbedBuilder()
            .setTitle("🏆 BẢNG PHONG THẦN THẦN BÀI (TOP TỶ LỆ THẮNG)")
            .setDescription(desc)
            .setColor(0xFEE75C)
            .setFooter({ text: "Yêu cầu: Tối thiểu 5 ván cược tại sòng bạc" });

        return isSlash ? interactionOrMsg.reply({ embeds: [embed] }) : interactionOrMsg.channel.send({ embeds: [embed] });
    }
};
