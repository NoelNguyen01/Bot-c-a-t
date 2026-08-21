require('dotenv').config();
const {
    Client,
    GatewayIntentBits,
    Partials,
    REST,
    Routes,
    SlashCommandBuilder,
    ActivityType
} = require('discord.js');

const economy = require('./src/commands/economy');
const casino = require('./src/commands/casino');
const multiplayer = require('./src/commands/multiplayer');
const admin = require('./src/commands/admin');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ],
    partials: [Partials.Channel, Partials.Message, Partials.User]
});

// ================= SLASH COMMAND DEFINITIONS =================
const slashCommands = [
    // Economy
    new SlashCommandBuilder().setName('bal').setDescription('Xem ví tiền, bank & nợ vay').addUserOption(opt => opt.setName('user').setDescription('Thành viên muốn xem')),
    new SlashCommandBuilder().setName('dep').setDescription('Gửi tiền vào ngân hàng').addStringOption(opt => opt.setName('so_tien').setDescription('Số tiền gửi (500k, 10m, all)').setRequired(true)),
    new SlashCommandBuilder().setName('with').setDescription('Rút tiền từ ngân hàng ra ví').addStringOption(opt => opt.setName('so_tien').setDescription('Số tiền rút (500k, 10m, all)').setRequired(true)),
    new SlashCommandBuilder().setName('vay').setDescription('Vay vốn ngân hàng (Tối đa 100M, lãi 2%/phút)').addStringOption(opt => opt.setName('so_tien').setDescription('Số tiền vay (10m, 50m, 100m)').setRequired(true)),
    new SlashCommandBuilder().setName('trano').setDescription('Trả nợ ngân hàng (Ưu đãi giảm 0.5% lãi mỗi 10% nợ trả)').addStringOption(opt => opt.setName('so_tien').setDescription('Số tiền trả (hoặc all)').setRequired(false)),
    new SlashCommandBuilder().setName('laodong').setDescription('Lao động công ích chuộc nợ ngân hàng (15 phút/lần, trừ 5% - 15% nợ)'),
    new SlashCommandBuilder().setName('daily').setDescription('Điểm danh hàng ngày nhận tiền thưởng & streak'),
    new SlashCommandBuilder().setName('work').setDescription('Đi làm kiếm tiền lương mỗi 30 phút'),
    new SlashCommandBuilder().setName('beg').setDescription('Ăn xin tiền lẻ mỗi 5 phút'),
    new SlashCommandBuilder().setName('rob').setDescription('Trộm tiền ví của thành viên khác').addUserOption(opt => opt.setName('user').setDescription('Nạn nhân').setRequired(true)),
    new SlashCommandBuilder().setName('pay').setDescription('Chuyển tiền cho người khác (Phí 20% nộp Kho Bạc)').addUserOption(opt => opt.setName('nguoi_nhan').setDescription('Người nhận').setRequired(true)).addStringOption(opt => opt.setName('so_tien').setDescription('Số tiền chuyển').setRequired(true)),
    new SlashCommandBuilder().setName('top').setDescription('Bảng xếp hạng đại gia server'),
    new SlashCommandBuilder().setName('topno').setDescription('Bảng phong thần con nợ ngập đầu'),

    // Casino
    new SlashCommandBuilder().setName('taixiu').setDescription('Đổ xúc xắc Tài Xỉu (3 con 1-6, bão nhà cái ăn sạch)')
        .addStringOption(opt => opt.setName('tien_cuoc').setDescription('Tiền cược (100k, 10m, all)').setRequired(true))
        .addStringOption(opt => opt.setName('lua_chon').setDescription('Chọn Tài hoặc Xỉu').setRequired(true).addChoices(
            { name: '🟢 Xỉu (4 - 10 điểm)', value: 'xiu' },
            { name: '🔴 Tài (11 - 17 điểm)', value: 'tai' }
        )),
    new SlashCommandBuilder().setName('blackjack').setDescription('Đánh bài Xì Dách Blackjack (30s đếm ngược, chống thoát ván)')
        .addStringOption(opt => opt.setName('tien_cuoc').setDescription('Tiền cược (100k, 10m, all)').setRequired(true)),
    new SlashCommandBuilder().setName('coinflip').setDescription('Tung đồng xu may rủi Sấp/Ngửa')
        .addStringOption(opt => opt.setName('tien_cuoc').setDescription('Tiền cược (100k, 10m, all)').setRequired(true))
        .addStringOption(opt => opt.setName('lua_chon').setDescription('Chọn Sấp hoặc Ngửa').setRequired(true).addChoices(
            { name: '⚪ Mặt Sấp', value: 'sap' },
            { name: '🟡 Mặt Ngửa', value: 'ngua' }
        )),
    new SlashCommandBuilder().setName('slots').setDescription('Quay hũ máy xèng hoa quả trúng Jackpot')
        .addStringOption(opt => opt.setName('tien_cuoc').setDescription('Tiền cược (100k, 10m, all)').setRequired(true)),
    new SlashCommandBuilder().setName('baucua').setDescription('Đổ xúc xắc Bầu Cua Tôm Cá')
        .addStringOption(opt => opt.setName('tien_cuoc').setDescription('Tiền cược (100k, 10m, all)').setRequired(true))
        .addStringOption(opt => opt.setName('con_vat').setDescription('Chọn con vật đặt cược').setRequired(true).addChoices(
            { name: '🍐 Bầu', value: 'bau' },
            { name: '🦀 Cua', value: 'cua' },
            { name: '🦐 Tôm', value: 'tom' },
            { name: '🐟 Cá', value: 'ca' },
            { name: '🐔 Gà', value: 'ga' },
            { name: '🦌 Nai', value: 'nai' }
        )),
    new SlashCommandBuilder().setName('topwin').setDescription('Bảng phong thần Thần Bài (Top tỷ lệ thắng casino)'),

    // PvP & Lì xì
    new SlashCommandBuilder().setName('rps').setDescription('Thách đấu Kéo Búa Bao solo 1v1')
        .addUserOption(opt => opt.setName('doi_thu').setDescription('Người muốn solo').setRequired(true))
        .addStringOption(opt => opt.setName('tien_cuoc').setDescription('Tiền cược').setRequired(true)),
    new SlashCommandBuilder().setName('lixi').setDescription('Ném bao lì xì toàn server giật thưởng')
        .addStringOption(opt => opt.setName('tong_tien').setDescription('Tổng tiền phát lì xì').setRequired(true))
        .addStringOption(opt => opt.setName('so_nguoi').setDescription('Số người được nhận (1-50)').setRequired(true)),

    // Admin & Help
    new SlashCommandBuilder().setName('help').setDescription('Xem hướng dẫn toàn bộ lệnh bot'),
    new SlashCommandBuilder().setName('cheat').setDescription('Chỉnh chế độ tỷ lệ thắng casino (Admin only)')
        .addStringOption(opt => opt.setName('mode').setDescription('Chế độ').setRequired(true).addChoices(
            { name: 'Generous (60% win)', value: 'generous' },
            { name: 'Hardcore (25% win)', value: 'hardcore' },
            { name: 'Drain (10% win)', value: 'drain' },
            { name: 'Default (Tự động theo cược)', value: 'default' }
        ))
];

client.once('ready', async () => {
    console.log(`========================================`);
    console.log(`🤖 Bot logged in as ${client.user.tag}!`);
    console.log(`🚀 JavaScript (discord.js v14) Engine Active!`);
    console.log(`========================================`);

    client.user.setActivity('!help | Casino & Economy 💵', { type: ActivityType.Playing });

    // Register Slash commands globally
    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
    try {
        console.log('🔄 Đang đồng bộ Slash Commands...');
        await rest.put(
            Routes.applicationCommands(client.user.id),
            { body: slashCommands.map(c => c.toJSON()) }
        );
        console.log('✅ Đã đồng bộ toàn bộ Slash Commands thành công!');
    } catch (err) {
        console.error('❌ Lỗi khi đồng bộ Slash Commands:', err);
    }
});

// ================= INTERACTION HANDLER (SLASH COMMANDS) =================
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;

    const { commandName, options } = interaction;

    try {
        switch (commandName) {
            // Economy
            case 'bal':
                await economy.bal(interaction, options.getUser('user'));
                break;
            case 'dep':
                await economy.dep(interaction, options.getString('so_tien'));
                break;
            case 'with':
                await economy.with(interaction, options.getString('so_tien'));
                break;
            case 'vay':
                await economy.vay(interaction, options.getString('so_tien'));
                break;
            case 'trano':
                await economy.trano(interaction, options.getString('so_tien') || 'all');
                break;
            case 'laodong':
                await economy.laodong(interaction);
                break;
            case 'daily':
                await economy.daily(interaction);
                break;
            case 'work':
                await economy.work(interaction);
                break;
            case 'beg':
                await economy.beg(interaction);
                break;
            case 'rob':
                await economy.rob(interaction, options.getUser('user'));
                break;
            case 'pay':
                await economy.pay(interaction, options.getUser('nguoi_nhan'), options.getString('so_tien'));
                break;
            case 'top':
                await economy.top(interaction);
                break;
            case 'topno':
                await economy.topno(interaction);
                break;

            // Casino
            case 'taixiu':
                await casino.tx(interaction, options.getString('tien_cuoc'), options.getString('lua_chon'));
                break;
            case 'blackjack':
                await casino.bj(interaction, options.getString('tien_cuoc'));
                break;
            case 'coinflip':
                await casino.cf(interaction, options.getString('tien_cuoc'), options.getString('lua_chon'));
                break;
            case 'slots':
                await casino.slot(interaction, options.getString('tien_cuoc'));
                break;
            case 'baucua':
                await casino.baucua(interaction, options.getString('tien_cuoc'), options.getString('con_vat'));
                break;
            case 'topwin':
                await casino.topwin(interaction);
                break;

            // PvP & Lì xì
            case 'rps':
                await multiplayer.rps(interaction, options.getUser('doi_thu'), options.getString('tien_cuoc'));
                break;
            case 'lixi':
                await multiplayer.lixi(interaction, options.getString('tong_tien'), options.getString('so_nguoi'));
                break;

            // Admin & Help
            case 'help':
                await admin.help(interaction);
                break;
            case 'cheat':
                await admin.cheat(interaction, options.getString('mode'));
                break;
        }
    } catch (err) {
        console.error(`❌ Error executing slash command /${commandName}:`, err);
        const errMsg = "❌ Đã xảy ra lỗi khi thực thi lệnh!";
        if (interaction.replied || interaction.deferred) {
            await interaction.followUp({ content: errMsg, ephemeral: true }).catch(() => {});
        } else {
            await interaction.reply({ content: errMsg, ephemeral: true }).catch(() => {});
        }
    }
});

// ================= PREFIX COMMAND HANDLER (! and n!) =================
client.on('messageCreate', async (message) => {
    if (message.author.bot) return;

    let prefix = null;
    if (message.content.startsWith('!')) prefix = '!';
    else if (message.content.startsWith('n!')) prefix = 'n!';

    if (!prefix) return;

    const args = message.content.slice(prefix.length).trim().split(/ +/);
    const cmd = args.shift()?.toLowerCase();
    if (!cmd) return;

    try {
        switch (cmd) {
            // Economy
            case 'bal': case 'balance': case 'tien': case 'vi':
                const target = message.mentions.users.first() || message.author;
                await economy.bal(message, target);
                break;
            case 'dep': case 'deposit':
                if (!args[0]) return message.channel.send("❌ Vui lòng nhập số tiền gửi (Ví dụ: `!dep 500k`, `!dep all`)");
                await economy.dep(message, args[0]);
                break;
            case 'with': case 'withdraw':
                if (!args[0]) return message.channel.send("❌ Vui lòng nhập số tiền rút (Ví dụ: `!with 500k`, `!with all`)");
                await economy.with(message, args[0]);
                break;
            case 'vay': case 'loan':
                if (!args[0]) return message.channel.send("❌ Vui lòng nhập số tiền vay (Ví dụ: `!vay 10m`, `!vay 50m`, tối đa 100M)");
                await economy.vay(message, args[0]);
                break;
            case 'trano': case 'payloan':
                await economy.trano(message, args[0] || 'all');
                break;
            case 'laodong': case 'chuocno':
                await economy.laodong(message);
                break;
            case 'daily': case 'diemdanh':
                await economy.daily(message);
                break;
            case 'work': case 'lamviec':
                await economy.work(message);
                break;
            case 'beg': case 'anxin':
                await economy.beg(message);
                break;
            case 'rob': case 'trom':
                const victim = message.mentions.members.first();
                if (!victim) return message.channel.send("❌ Vui lòng tag người muốn trộm (Ví dụ: `!rob @user`)");
                await economy.rob(message, victim);
                break;
            case 'pay': case 'chuyen':
                const receiver = message.mentions.members.first();
                const payAmt = args[1];
                if (!receiver || !payAmt) return message.channel.send("❌ Cú pháp: `!pay @user <tiền>`");
                await economy.pay(message, receiver, payAmt);
                break;
            case 'top': case 'leaderboard':
                await economy.top(message);
                break;
            case 'topno':
                await economy.topno(message);
                break;

            // Casino
            case 'tx': case 'taixiu':
                if (!args[0] || !args[1]) return message.channel.send("❌ Cú pháp: `!tx <tiền> <t/x>` (Ví dụ: `!tx 500k t`)");
                await casino.tx(message, args[0], args[1]);
                break;
            case 'bj': case 'blackjack': case 'xidach':
                if (!args[0]) return message.channel.send("❌ Cú pháp: `!bj <tiền>` (Ví dụ: `!bj 10m`)");
                await casino.bj(message, args[0]);
                break;
            case 'cf': case 'coinflip': case 'flip':
                if (!args[0] || !args[1]) return message.channel.send("❌ Cú pháp: `!cf <tiền> <s/n>` (Ví dụ: `!cf 10m s`)");
                await casino.cf(message, args[0], args[1]);
                break;
            case 'slot': case 'slots':
                if (!args[0]) return message.channel.send("❌ Cú pháp: `!slot <tiền>` (Ví dụ: `!slot 10m`)");
                await casino.slot(message, args[0]);
                break;
            case 'bc': case 'baucua':
                if (!args[0] || !args[1]) return message.channel.send("❌ Cú pháp: `!bc <tiền> <con>` (Ví dụ: `!bc 10m bau`)");
                await casino.baucua(message, args[0], args[1]);
                break;
            case 'topwin':
                await casino.topwin(message);
                break;

            // PvP & Lì xì
            case 'rps':
                const opp = message.mentions.members.first();
                const rpsBet = args[1];
                if (!opp || !rpsBet) return message.channel.send("❌ Cú pháp: `!rps @user <tiền>`");
                await multiplayer.rps(message, opp, rpsBet);
                break;
            case 'lixi':
                if (!args[0] || !args[1]) return message.channel.send("❌ Cú pháp: `!lixi <tổng tiền> <số người>` (Ví dụ: `!lixi 100m 5`)");
                await multiplayer.lixi(message, args[0], args[1]);
                break;

            // Admin & Help
            case 'help': case 'hien': case 'menu':
                await admin.help(message);
                break;
            case 'buffme':
                if (!args[0]) return message.channel.send("❌ Cú pháp: `!buffme <tiền>`");
                await admin.buffme(message, args[0]);
                break;
            case 'setmoney':
                const smTarget = message.mentions.members.first();
                if (!smTarget || !args[1]) return message.channel.send("❌ Cú pháp: `!setmoney @user <tiền>`");
                await admin.setmoney(message, smTarget, args[1]);
                break;
            case 'addmoney':
                const amTarget = message.mentions.members.first();
                if (!amTarget || !args[1]) return message.channel.send("❌ Cú pháp: `!addmoney @user <tiền>`");
                await admin.addmoney(message, amTarget, args[1]);
                break;
            case 'trutien':
                const ttTarget = message.mentions.members.first();
                if (!ttTarget || !args[1]) return message.channel.send("❌ Cú pháp: `!trutien @user <tiền>`");
                await admin.trutien(message, ttTarget, args[1]);
                break;
            case 'cheat':
                if (!args[0]) return message.channel.send("❌ Cú pháp: `!cheat <generous/hardcore/drain/default>`");
                await admin.cheat(message, args[0]);
                break;
        }
    } catch (err) {
        console.error(`❌ Error executing prefix command !${cmd}:`, err);
        message.channel.send("❌ Đã xảy ra lỗi khi thực thi lệnh!").catch(() => {});
    }
});

// Login Bot
if (!process.env.DISCORD_TOKEN) {
    console.error("❌ LỖI: Chưa có DISCORD_TOKEN trong file .env!");
} else {
    client.login(process.env.DISCORD_TOKEN);
}
