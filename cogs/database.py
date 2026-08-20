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

def parse_amount(val, current_balance: int = 0) -> int:
    """
    Chuyển đổi các định dạng nhập tiền tệ (k, m, b, t, all, dấu phẩy/chấm) thành số nguyên int.
    Hỗ trợ lạm phát ngàn tỷ:
    - 10k -> 10,000
    - 5m / 5tr -> 5,000,000
    - 10b / 10ty / 10tỷ -> 10,000,000,000 (10 Tỷ)
    - 5t / 5tril / 5nganti -> 5,000,000,000,000 (5 Ngàn Tỷ)
    - all / max / tatca -> current_balance
    """
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)

    s = str(val).strip().lower().replace(",", "").replace(" ", "")
    if s in ["all", "max", "tatca", "het", "allin"]:
        return max(0, int(current_balance))

    multiplier = 1
    if s.endswith("ngantỷ") or s.endswith("nganti") or s.endswith("tril") or s.endswith("t"):
        multiplier = 1_000_000_000_000  # Ngàn tỷ / Trillion
        for suf in ["ngantỷ", "nganti", "tril", "t"]:
            if s.endswith(suf):
                s = s[:-len(suf)]
                break
    elif s.endswith("tỷ") or s.endswith("ty") or s.endswith("bil") or s.endswith("b"):
        multiplier = 1_000_000_000  # Tỷ / Billion
        for suf in ["tỷ", "ty", "bil", "b"]:
            if s.endswith(suf):
                s = s[:-len(suf)]
                break
    elif s.endswith("triệu") or s.endswith("trieu") or s.endswith("tr") or s.endswith("mil") or s.endswith("m"):
        multiplier = 1_000_000  # Triệu / Million
        for suf in ["triệu", "trieu", "tr", "mil", "m"]:
            if s.endswith(suf):
                s = s[:-len(suf)]
                break
    elif s.endswith("nghìn") or s.endswith("nghin") or s.endswith("ngàn") or s.endswith("ngan") or s.endswith("k"):
        multiplier = 1_000  # Ngàn / Thousand
        for suf in ["nghìn", "nghin", "ngàn", "ngan", "k"]:
            if s.endswith(suf):
                s = s[:-len(suf)]
                break

    try:
        return int(float(s) * multiplier)
    except (ValueError, TypeError):
        return -1

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
            "last_laodong": 0,
            "casino_wins": 0,
            "casino_games": 0,
            "casino_profit": 0
        }
    else:
        if "casino_wins" not in data["users"][uid]: data["users"][uid]["casino_wins"] = 0
        if "casino_games" not in data["users"][uid]: data["users"][uid]["casino_games"] = 0
        if "casino_profit" not in data["users"][uid]: data["users"][uid]["casino_profit"] = 0
        if "last_laodong" not in data["users"][uid]: data["users"][uid]["last_laodong"] = 0
    return data["users"][uid]

def add_to_treasury(data, amount: int):
    """Cộng tiền vào Kho Bạc Bot từ các nguồn thuế"""
    if amount <= 0:
        return
    if "treasury" not in data:
        data["treasury"] = {"balance": 0}
    data["treasury"]["balance"] = data["treasury"].get("balance", 0) + int(amount)

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
    uid = str(user_id)
    loans = data.get("loans", {})
    if uid not in loans:
        return 0, 0, 0, False

    loan_info = loans[uid]
    principal = loan_info.get("principal", 0)
    loan_time = loan_info.get("timestamp", time.time())
    rate_discount = loan_info.get("rate_discount", 0.0)

    now = time.time()
    elapsed_minutes = int((now - loan_time) // 60)

    if elapsed_minutes <= 0:
        return principal, principal, 0, False

    regular_mins = min(elapsed_minutes, 30)
    overdue_mins = max(0, elapsed_minutes - 30)
    is_overdue = (overdue_mins > 0)

    # Lãi suất gốc 2%/phút (được trừ rate_discount), tối thiểu 0.5%/phút
    reg_rate = max(0.005, 0.02 - (rate_discount / 100.0))
    # Lãi suất quá hạn 4%/phút (được trừ rate_discount), tối thiểu 1.0%/phút
    overdue_rate = max(0.01, 0.04 - (rate_discount / 100.0))

    debt = float(principal)
    for _ in range(regular_mins):
        debt *= (1.0 + reg_rate)

    for _ in range(overdue_mins):
        debt *= (1.0 + overdue_rate)

    total_debt = int(debt)
    max_debt_cap = principal * 3
    if total_debt > max_debt_cap:
        total_debt = max_debt_cap

    interest = max(0, total_debt - principal)
    return total_debt, principal, interest, is_overdue

def deduct_loan_debt(data, user_id, pay_amount: int) -> tuple[int, int, bool]:
    """
    Trừ nợ vay ngân hàng (có tính ưu đãi trả góp: giảm 0.5% lãi cho mỗi 10% nợ trả).
    Trả về: (số tiền thực trả, số nợ còn lại, đã trả hết nợ hay chưa)
    """
    uid = str(user_id)
    total_debt, principal, interest, is_overdue = calculate_loan_debt(data, user_id)
    if total_debt <= 0 or pay_amount <= 0:
        return 0, 0, False

    loan_info = data.get("loans", {}).get(uid, {})
    actual_paid = min(pay_amount, total_debt)

    if actual_paid >= total_debt:
        if uid in data.get("loans", {}):
            del data["loans"][uid]
        add_to_treasury(data, interest)
        save_db(data)
        return actual_paid, 0, True
    else:
        # Tính chiết khấu trả góp: mỗi 10% nợ trả được giảm thêm 0.5% dư nợ
        pct_paid = (actual_paid / total_debt) * 100.0
        milestones = int(pct_paid // 10)
        discount_bonus = 0
        discount_pct = 0.0
        if milestones >= 1:
            discount_pct = milestones * 0.5
            discount_bonus = int(total_debt * (discount_pct / 100.0))

        rem_debt = max(0, total_debt - actual_paid - discount_bonus)
        current_discount = loan_info.get("rate_discount", 0.0)
        new_discount = min(1.5, current_discount + discount_pct)

        if rem_debt == 0:
            if uid in data.get("loans", {}):
                del data["loans"][uid]
            add_to_treasury(data, interest)
            save_db(data)
            return actual_paid, 0, True
        else:
            data["loans"][uid] = {
                "principal": rem_debt,
                "timestamp": time.time(),
                "rate_discount": new_discount
            }
            add_to_treasury(data, int(actual_paid * 0.20))
            save_db(data)
            return actual_paid, rem_debt, False

def calculate_win_rate(data, user_id, amount: int) -> float:
    uid = str(user_id)
    cheat_cfg = data.get("cheat_config", {})
    user_overrides = cheat_cfg.get("user_overrides", {})

    if uid in user_overrides:
        custom_rate = user_overrides[uid]
        return float(custom_rate) / 100.0

    global_mode = cheat_cfg.get("global_mode", "default")
    if global_mode == "generous":
        base_rate = 0.60
    elif global_mode == "hardcore":
        base_rate = 0.25
    elif global_mode == "drain":
        base_rate = 0.10
    else:
        # Tỷ lệ thích ứng với quy mô ngàn tỷ
        if amount <= 500000:          # <= 500k
            base_rate = 0.48
        elif amount <= 50000000:      # <= 50M
            base_rate = 0.40
        elif amount <= 1000000000:    # <= 1B (1 Tỷ)
            base_rate = 0.30
        elif amount <= 10000000000:   # <= 10B (10 Tỷ)
            base_rate = 0.20
        elif amount <= 100000000000:  # <= 100B (100 Tỷ)
            base_rate = 0.12
        elif amount <= 1000000000000: # <= 1,000B (1 Ngàn Tỷ)
            base_rate = 0.08
        else:                         # > 1 Ngàn Tỷ
            base_rate = 0.05

    return base_rate
