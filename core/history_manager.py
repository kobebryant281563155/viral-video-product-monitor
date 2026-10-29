import json
import os
import time
from typing import Dict, Any, Optional

class HistoryManager:
    """管理已下载视频的历史记录库，避免重复下载与流量浪费"""

    def __init__(self, history_file: str = "data/viral_history.json"):
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
        except Exception as e:
            print(f"[WARN] 历史记录读取失败，将初始化空记录: {e}")
            return {}

    def _save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 历史记录保存失败: {e}")

    def is_downloaded(self, video_id: str) -> bool:
        """检查视频是否已被下载过"""
        return str(video_id) in self.history

    def record_download(self, video_id: str, creator_name: str, title: str, 
                        likes: int, views: int, file_path: str, raw_meta: Optional[Dict] = None):
        """记录已下载的视频"""
        self.history[str(video_id)] = {
            "video_id": str(video_id),
            "creator_name": creator_name,
            "title": title,
            "likes": likes,
            "views": views,
            "file_path": file_path,
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "raw_meta": raw_meta or {}
        }
        self._save()

    def get_total_count(self) -> int:
        return len(self.history)
