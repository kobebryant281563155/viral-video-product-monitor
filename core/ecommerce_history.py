import os
import json
import time
from typing import Dict, Any

class EcommerceHistoryManager:
    """电商爆款抓取历史排重库"""

    def __init__(self, history_file: str = "data/ecommerce_history.json"):
        self.history_file = history_file
        self._ensure_dir()
        self.history = self._load()

    def _ensure_dir(self):
        folder = os.path.dirname(self.history_file)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.history_file):
            return {}
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def is_recorded(self, item_id: str) -> bool:
        return str(item_id) in self.history

    def record_product(self, item_id: str, platform: str, title: str, price: float, sales: int, folder: str):
        self.history[str(item_id)] = {
            "id": str(item_id),
            "platform": platform,
            "title": title,
            "price": price,
            "sales": sales,
            "folder": folder,
            "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save()

    def get_total_count(self) -> int:
        return len(self.history)
