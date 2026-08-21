const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '../../data');
const DB_FILE = path.join(DATA_DIR, 'neko_data.json');

const MAX_GLOBAL_LIMIT = 999999999999999999999999999999999999999999999999999n;
const MAX_LOAN_LIMIT = 100_000_000n; // Hạn mức vay tối đa 100M

function loadDb() {
    if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
    }
    if (!fs.existsSync(DB_FILE)) {
        const initData = {
            users: {},
            loans: {},
            debts: {},
            treasury: { balance: 0 },
            cheat_config: { global_mode: 'default', user_overrides: {} },
            bank_tax: { last_tax_timestamp: Math.floor(Date.now() / 1000) }
        };
        fs.writeFileSync(DB_FILE, JSON.stringify(initData, null, 4), 'utf8');
        return initData;
    }
    try {
        const raw = fs.readFileSync(DB_FILE, 'utf8');
        const data = JSON.parse(raw);
        if (!data.users) data.users = {};
        if (!data.loans) data.loans = {};
        if (!data.debts) data.debts = {};
        if (!data.treasury) data.treasury = { balance: 0 };
        if (!data.cheat_config) data.cheat_config = { global_mode: 'default', user_overrides: {} };
        if (!data.bank_tax) data.bank_tax = { last_tax_timestamp: Math.floor(Date.now() / 1000) };
        return data;
    } catch (err) {
        return {
            users: {},
            loans: {},
            debts: {},
            treasury: { balance: 0 },
            cheat_config: { global_mode: 'default', user_overrides: {} },
            bank_tax: { last_tax_timestamp: Math.floor(Date.now() / 1000) }
        };
    }
}

function saveDb(data) {
    if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
    }
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 4), 'utf8');
}

function getUser(data, userId) {
    const uid = String(userId);
    if (!data.users[uid]) {
        data.users[uid] = {
            wallet: 1000,
            bank: 0,
            streak: 0,
            last_daily: 0,
            last_work: 0,
            last_beg: 0,
            last_rob: 0,
            last_laodong: 0,
            casino_wins: 0,
            casino_games: 0,
            casino_profit: 0
        };
    } else {
        if (data.users[uid].casino_wins === undefined) data.users[uid].casino_wins = 0;
        if (data.users[uid].casino_games === undefined) data.users[uid].casino_games = 0;
        if (data.users[uid].casino_profit === undefined) data.users[uid].casino_profit = 0;
        if (data.users[uid].last_laodong === undefined) data.users[uid].last_laodong = 0;
    }
    return data.users[uid];
}

function parseAmount(val, currentBalance = 0) {
    if (val === null || val === undefined) return 0n;
    if (typeof val === 'number') return BigInt(Math.floor(val));
    if (typeof val === 'bigint') return val;

    let s = String(val).trim().toLowerCase().replace(/,/g, '').replace(/ /g, '');
    if (['all', 'max', 'tatca', 'het', 'allin'].includes(s)) {
        return BigInt(Math.max(0, Number(currentBalance)));
    }
    if (['inf', 'infinity'].includes(s)) {
        return MAX_GLOBAL_LIMIT;
    }

    let multiplier = 1n;
    const suffixes = [
        { keys: ['ngantỷ', 'nganti', 'tril', 't'], mult: 1_000_000_000_000n },
        { keys: ['tỷ', 'ty', 'bil', 'b'], mult: 1_000_000_000n },
        { keys: ['triệu', 'trieu', 'tr', 'mil', 'm'], mult: 1_000_000n },
        { keys: ['nghìn', 'nghin', 'ngàn', 'ngan', 'k'], mult: 1_000n }
    ];

    for (const group of suffixes) {
        for (const key of group.keys) {
            if (s.endsWith(key)) {
                multiplier = group.mult;
                s = s.slice(0, -key.length);
                break;
            }
        }
        if (multiplier !== 1n) break;
    }

    try {
        if (s.includes('.')) {
            const num = parseFloat(s);
            if (isNaN(num)) return -1n;
            return BigInt(Math.floor(num * Number(multiplier)));
        } else {
            const res = BigInt(s) * multiplier;
            return res < 0n ? -1n : (res > MAX_GLOBAL_LIMIT ? MAX_GLOBAL_LIMIT : res);
        }
    } catch {
        return -1n;
    }
}

function formatMoney(num) {
    if (num === undefined || num === null) return "0";
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function addTreasury(data, amount) {
    const amt = BigInt(amount);
    if (amt <= 0n) return;
    if (!data.treasury) data.treasury = { balance: 0 };
    const current = BigInt(data.treasury.balance || 0);
    data.treasury.balance = Number(current + amt > MAX_GLOBAL_LIMIT ? MAX_GLOBAL_LIMIT : current + amt);
}

function applyBankTax(data) {
    const now = Math.floor(Date.now() / 1000);
    const lastTax = data.bank_tax?.last_tax_timestamp || now;
    const diff = now - lastTax;
    const cycleSeconds = 18000; // 5 tiếng = 18,000s

    if (diff >= cycleSeconds) {
        const cycles = Math.floor(diff / cycleSeconds);
        let totalTaxCollected = 0n;

        for (const uid in data.users) {
            let bank = BigInt(data.users[uid].bank || 0);
            if (bank > 0n) {
                for (let i = 0; i < Math.min(cycles, 50); i++) {
                    const tax = (bank * 5n) / 100n;
                    if (tax > 0n) {
                        bank -= tax;
                        totalTaxCollected += tax;
                    }
                }
                data.users[uid].bank = Number(bank);
            }
        }
        addTreasury(data, totalTaxCollected);
        data.bank_tax.last_tax_timestamp = lastTax + (cycles * cycleSeconds);
        saveDb(data);
    }
}

function calculateLoanDebt(data, userId) {
    const uid = String(userId);
    const loans = data.loans || {};
    if (!loans[uid]) {
        return { totalDebt: 0n, principal: 0n, interest: 0n, isOverdue: false };
    }

    const loanInfo = loans[uid];
    const principal = BigInt(loanInfo.principal || 0);
    const loanTime = loanInfo.timestamp || Math.floor(Date.now() / 1000);
    const rateDiscount = loanInfo.rate_discount || 0.0;

    const now = Math.floor(Date.now() / 1000);
    const elapsedMinutes = Math.floor((now - loanTime) / 60);

    if (elapsedMinutes <= 0) {
        return { totalDebt: principal, principal, interest: 0n, isOverdue: false };
    }

    const regularMins = Math.min(elapsedMinutes, 30);
    const overdueMins = Math.max(0, elapsedMinutes - 30);
    const isOverdue = overdueMins > 0;

    const regRate = Math.max(0.005, 0.02 - (rateDiscount / 100.0));
    const overdueRate = Math.max(0.01, 0.04 - (rateDiscount / 100.0));

    const regMult = BigInt(Math.round((1.0 + regRate) * 10000));
    const overdueMult = BigInt(Math.round((1.0 + overdueRate) * 10000));

    let debt = principal;
    for (let i = 0; i < regularMins; i++) {
        debt = (debt * regMult) / 10000n;
    }
    for (let i = 0; i < overdueMins; i++) {
        debt = (debt * overdueMult) / 10000n;
    }

    const maxDebtCap = principal * 3n;
    if (debt > maxDebtCap) debt = maxDebtCap;
    if (debt > MAX_GLOBAL_LIMIT) debt = MAX_GLOBAL_LIMIT;

    const interest = debt > principal ? debt - principal : 0n;
    return { totalDebt: debt, principal, interest, isOverdue };
}

function deductLoanDebt(data, userId, payAmount) {
    const uid = String(userId);
    const { totalDebt, principal, interest } = calculateLoanDebt(data, userId);
    const payAmt = BigInt(payAmount);

    if (totalDebt <= 0n || payAmt <= 0n) {
        return { actualPaid: 0n, remDebt: 0n, cleared: false };
    }

    const actualPaid = payAmt >= totalDebt ? totalDebt : payAmt;

    if (actualPaid >= totalDebt) {
        delete data.loans[uid];
        addTreasury(data, interest);
        saveDb(data);
        return { actualPaid, remDebt: 0n, cleared: true };
    } else {
        const milestones = Number((actualPaid * 10n) / totalDebt);
        let discountBonus = 0n;
        let discountPct = 0.0;
        if (milestones >= 1) {
            discountPct = milestones * 0.5;
            discountBonus = (totalDebt * BigInt(Math.floor(discountPct * 10))) / 1000n;
        }

        let remDebt = totalDebt - actualPaid - discountBonus;
        if (remDebt < 0n) remDebt = 0n;

        const currentDiscount = data.loans[uid]?.rate_discount || 0.0;
        const newDiscount = Math.min(1.5, currentDiscount + discountPct);

        if (remDebt === 0n) {
            delete data.loans[uid];
            addTreasury(data, interest);
            saveDb(data);
            return { actualPaid, remDebt: 0n, cleared: true };
        } else {
            data.loans[uid] = {
                principal: Number(remDebt),
                timestamp: Math.floor(Date.now() / 1000),
                rate_discount: newDiscount
            };
            addTreasury(data, (actualPaid * 20n) / 100n);
            saveDb(data);
            return { actualPaid, remDebt, cleared: false };
        }
    }
}

function calculateWinRate(data, userId, amount) {
    const uid = String(userId);
    const cheatCfg = data.cheat_config || {};
    const userOverrides = cheatCfg.user_overrides || {};

    if (userOverrides[uid] !== undefined) {
        return Number(userOverrides[uid]) / 100.0;
    }

    const mode = cheatCfg.global_mode || 'default';
    if (mode === 'generous') return 0.60;
    if (mode === 'hardcore') return 0.25;
    if (mode === 'drain') return 0.10;

    const amt = BigInt(amount);
    if (amt <= 500_000n) return 0.48;
    if (amt <= 50_000_000n) return 0.40;
    if (amt <= 1_000_000_000n) return 0.30;
    if (amt <= 10_000_000_000n) return 0.20;
    if (amt <= 100_000_000_000n) return 0.12;
    if (amt <= 1_000_000_000_000n) return 0.08;
    return 0.05;
}

// ================= USER TRANSACTION LOCK (ANTI-RACE CONDITION) =================
const USER_LOCKS = new Map();

function acquireUserLock(userId, timeoutMs = 1500) {
    const uid = String(userId);
    const now = Date.now();
    const existingLock = USER_LOCKS.get(uid);

    if (existingLock && existingLock > now) {
        return false; // Đang có giao dịch chưa hoàn tất
    }

    USER_LOCKS.set(uid, now + timeoutMs);
    return true;
}

function releaseUserLock(userId) {
    const uid = String(userId);
    USER_LOCKS.delete(uid);
}

module.exports = {
    loadDb,
    saveDb,
    getUser,
    parseAmount,
    formatMoney,
    addTreasury,
    applyBankTax,
    calculateLoanDebt,
    deductLoanDebt,
    calculateWinRate,
    checkCasinoLockout,
    acquireUserLock,
    releaseUserLock,
    MAX_GLOBAL_LIMIT,
    MAX_LOAN_LIMIT
};
