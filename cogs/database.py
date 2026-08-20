# -*- coding: utf-8 -*-
import json
import os
import time
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "neko_data.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {},
            "loans": {},
            "debts": {},
            "treasury": {"balance": 0},
            "cheat_config": {
                "global_mode": "default",
                "user_overrides": {}  # user_id: int (0 to 100)
            },
            "bank_tax": {
                "last_tax_timestamp": time.time()
            }
        }
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            # Đảm bảo có đầy đủ schema
            if "users" not in data: data["users"] = {}
            if "loans" not in data: data["loans"] = {}
            if "debts" not in data: data["debts"] = {}
            if "treasury" not in data: data["treasury"] = {"balance": 0}
            if "cheat_config" not in data: data["cheat_config"] = {"global_mode": "default", "user_overrides": {}}
            if "bank_tax" not in data: data["bank_tax"] = {"last_tax_timestamp": time.time()}
            return data
        except json.JSONDecodeError:
            return {"users": {}, "loans": {}, "debts": {}, "treasury": {"balance": 0}, "cheat_config": {"global_mode": "default", "user_overrides": {}}, "bank_tax": {"last_tax_timestamp": time.time()}}

def save_db(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "wallet": 1000,
            "bank": 0,
            "streak": 0,
            "last_daily": 0,
            "last_work": 0,
            "last_beg": 0,
            "last_rob": 0,
            "shield_until": 0,
            "inventory": {},
            "pet": None,
            "partner_id": None,
            "marry_time": 0
        }
    return data["users"][uid]

def add_to_treasury(data, amount: int):
    """Cộng tiền vào Kho Bạc Bot từ các nguồn thuế"""
    if amount <= 0:
        return
    if "treasury" not in data:
        data["treasury"] = {"balance": 0}
    data["treasury"]["balance"] = data["treasury"].get("balance", 0) + amount

def apply_bank_tax(data):
    """Tự động tính và thu 5% thuế trên số dư Bank của tất cả thành viên sau mỗi 5 tiếng"""
    now = time.time()
    last_tax = data.get("bank_tax", {}).get("last_tax_timestamp", now)
    diff = now - last_tax
    cycle_seconds = 18000  # 5 tiếng = 18,000 giây

    if diff >= cycle_seconds:
        cycles = int(diff // cycle_seconds)
        total_tax_collected = 0

        for uid, udata in data.get("users", {}).items():
            bank_balance = udata.get("bank", 0)
            if bank_balance > 0:
                # Trừ 5% cho mỗi chu kỳ 5h đã trôi qua
                new_balance = bank_balance
                for _ in range(cycles):
                    tax = int(new_balance * 0.05)
                    if tax > 0:
                        new_balance -= tax
                        total_tax_collected += tax
                udata["bank"] = max(0, new_balance)

        add_to_treasury(data, total_tax_collected)
        data["bank_tax"]["last_tax_timestamp"] = last_tax + (cycles * cycle_seconds)
        save_db(data)

def calculate_loan_debt(data, user_id) -> tuple[int, int, int, bool]:
    """
    Tính toán số nợ hiện tại của user.
    Trả về: (total_debt, principal, interest, is_overdue)
    - Trong 30 phút: Lãi 2% / phút.
    - Sau 30 phút (quá hạn): Gia hạn 18 phút (60%), Lãi 4% / phút.
    - Trần nợ tối đa: 300% gốc (gấp 3 lần gốc).
    """
    uid = str(user_id)
    loans = data.get("loans", {})
    if uid not in loans:
        return 0, 0, 0, False

    loan_info = loans[uid]
    principal = loan_info.get("principal", 0)
    loan_time = loan_info.get("timestamp", time.time())

    now = time.time()
    elapsed_minutes = int((now - loan_time) // 60)

    if elapsed_minutes <= 0:
        return principal, principal, 0, False

    # 30 phút đầu: 2%/phút
    regular_mins = min(elapsed_minutes, 30)
    overdue_mins = max(0, elapsed_minutes - 30)
    is_overdue = (overdue_mins > 0)

    # Tính lãi kép 2%/phút cho 30 phút đầu
    debt = float(principal)
    for _ in range(regular_mins):
        debt *= 1.02

    # Tính lãi phạt 4%/phút cho thời gian quá hạn
    for _ in range(overdue_mins):
        debt *= 1.04

    total_debt = int(debt)

    # Khống chế trần nợ tối đa 300% gốc
    max_debt_cap = principal * 3
    if total_debt > max_debt_cap:
        total_debt = max_debt_cap

    interest = max(0, total_debt - principal)
    return total_debt, principal, interest, is_overdue

def calculate_win_rate(data, user_id, amount: int) -> float:
    """
    Tính toán tỷ lệ thắng dựa trên:
    1. Cấu hình Cheat đích danh cho user (!setwin @user X)
    2. Cấu hình Global Mode (!nhacai)
    3. Mức tiền cược (Càng cược to tỷ lệ thắng càng tụt thảm hại)
    """
    uid = str(user_id)
    cheat_cfg = data.get("cheat_config", {})
    user_overrides = cheat_cfg.get("user_overrides", {})

    # 1. Can thiệp đích danh user
    if uid in user_overrides:
        custom_rate = user_overrides[uid]
        return float(custom_rate) / 100.0

    # 2. Can thiệp Global Mode
    global_mode = cheat_cfg.get("global_mode", "default")
    if global_mode == "generous":  # Mồi chài
        base_rate = 0.60
    elif global_mode == "hardcore":  # Hút máu
        base_rate = 0.25
    elif global_mode == "drain":     # Tận thu
        base_rate = 0.10
    else:  # Mặc định theo bậc tiền cược
        if amount <= 50000:
            base_rate = 0.48
        elif amount <= 500000:
            base_rate = 0.40
        elif amount <= 5000000:
            base_rate = 0.28
        elif amount <= 20000000:
            base_rate = 0.18
        else:
            base_rate = 0.09

    return base_rate
