import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

POS_CSV = DATA_DIR / "restaurant_pos_transactions.csv"
INVENTORY_CSV = DATA_DIR / "restaurant_inventory_logs.csv"
SUPPLY_CSV = DATA_DIR / "restaurant_supply_network.csv"


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
    NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
