"""Loads the three source CSVs once and caches them in memory."""

import threading

import pandas as pd

from config import INVENTORY_CSV, POS_CSV, SUPPLY_CSV

_lock = threading.Lock()
_cache = {}


def _load():
    pos = pd.read_csv(POS_CSV, parse_dates=["Date"])
    pos["Hour"] = pos["Time"].str.slice(0, 2).astype(int)
    pos["Margin_Per_Unit"] = pos["Unit_Price"] - pos["Discount_Applied"] - pos["Unit_Cost"]
    pos["Total_Cost"] = pos["Unit_Cost"] * pos["Quantity"]
    pos["Profit"] = pos["Total_Amount"] - pos["Total_Cost"]

    inventory = pd.read_csv(INVENTORY_CSV, parse_dates=["Date"])
    inventory["Spoilage_Cost"] = inventory["Spoiled_Qty"] * inventory["Unit_Cost"] - inventory["Salvage_Value"]
    inventory["Waste_Pct"] = (inventory["Spoiled_Qty"] / inventory["Forecasted_Prep_Qty"]) * 100

    supply = pd.read_csv(SUPPLY_CSV)

    return {"pos": pos, "inventory": inventory, "supply": supply}


def get_data():
    if not _cache:
        with _lock:
            if not _cache:
                _cache.update(_load())
    return _cache
