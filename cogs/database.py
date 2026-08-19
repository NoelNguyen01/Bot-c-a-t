# -*- coding: utf-8 -*-
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "neko_data.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_db(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user(data, user_id: int):
    u_id = str(user_id)
    if "users" not in data:
        data["users"] = {}
    if u_id not in data["users"]:
        data["users"][u_id] = {
            "wallet": 1000,
            "bank": 0,
            "bank_max": 50000,
            "last_daily": 0,
            "streak": 0,
            "last_work": 0,
            "last_beg": 0,
            "last_rob": 0,
            "inventory": {},
            "pet": None,
            "married_to": None,
            "married_date": None,
            "rep": 0,
            "shield_until": 0
        }
        save_db(data)
    return data["users"][u_id]
