import os
import sys
import time
import json
import random
from typing import Dict, Any

from core.platform_inspector import PlatformInspector
from core.downloader import MultiPlatformDownloader
from core.history_manager import HistoryManager

class CompetitorMonitorApp:
    """四大平台 (TikTok / 抖音 / 小红书 / Instagram) 巡检协调控制器"""

    def __init__(self, config_path: str = "config/competitors.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        storage_conf = self.config.get("storage", {})
        download_dir = storage_conf.get("download_dir", "materials/viral_competitors")
        save_meta = storage_conf.get("save_metadata_json", True)
        
        self.downloader = MultiPlatformDownloader(download_dir=download_dir, save_metadata=save_meta)
        self.history = HistoryManager(history_file="data/viral_history.json")
        self.inspector = PlatformInspector(config=self.config)

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"找不到配置文件: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_once(self) -> Dict[str, int]:
        """执行单轮全量巡检"""
        print("\n" + "="*65)
        print("     国内外四大平台 (抖音/小红书/TikTok/Instagram) 爆款监控系统     ")
        print("="*65)

        connected = self.inspector.connect()
        if not connected:
            print("[FATAL] 无法连接到浏览器环境，本轮巡检终止。")
            return {"scanned": 0, "viral_found": 0, "downloaded": 0}

        creators = self.config.get("creators", [])
        schedule_conf = self.config.get("schedule", {})
        jitter_min = schedule_conf.get("jitter_seconds_min", 4)
        jitter_max = schedule_conf.get("jitter_seconds_max", 8)

        stats = {
            "creators_count": len(creators),
            "viral_found": 0,
            "downloaded": 0,
            "skipped": 0
        }

        try:
            for idx, creator in enumerate(creators, 1):
                c_name = creator.get("name")
                print(f"\n>>> 进度 [{idx}/{len(creators)}]: 准备巡检 {c_name}...")

                viral_videos = self.inspector.inspect_creator(
                    creator, 
                    max_videos=self.config.get("filter_rules", {}).get("max_videos_per_creator", 15)
                )

                stats["viral_found"] += len(viral_videos)

                for v in viral_videos:
                    vid = str(v["id"])
                    if self.history.is_downloaded(vid):
                        print(f"[SKIP] 视频 [{vid}] 历史库中已存在，跳过。")
                        stats["skipped"] += 1
                        continue

                    # 执行下载
                    saved_path = self.downloader.download_video(v)
                    if saved_path:
                        self.history.record_download(
                            video_id=vid,
                            creator_name=c_name,
                            title=v.get("title", ""),
                            likes=v.get("likes", 0),
                            views=v.get("views", 0),
                            file_path=saved_path,
                            raw_meta=v
                        )
                        stats["downloaded"] += 1

                # 拟人随机延时
                if idx < len(creators):
                    sleep_time = random.uniform(jitter_min, jitter_max)
                    print(f"[WAIT] 拟人防风控等待 {sleep_time:.1f} 秒后巡检下一个博主...")
                    time.sleep(sleep_time)

        finally:
            self.inspector.close()

        # 输出统计卡片
        print("\n" + "="*65)
        print("                        全网巡检统计                        ")
        print("="*65)
        print(f" 巡检博主总数: {stats['creators_count']}")
        print(f" 命中爆款总数: {stats['viral_found']}")
        print(f" 历史去重跳过: {stats['skipped']}")
        print(f" 本次成功下载: {stats['downloaded']}")
        print(f" 历史库视频总存量: {self.history.get_total_count()}")
        print("="*65)

        return stats

    def run_daemon(self, interval_hours: int = 4):
        print(f"[DAEMON] 启动后台定时轮询模式，每 {interval_hours} 小时巡检一次...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[ERROR] 巡检异常: {e}")
            
            sleep_seconds = interval_hours * 3600
            next_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + sleep_seconds))
            print(f"\n[SLEEP] 本轮结束，下一次巡检时间: {next_time}")
            time.sleep(sleep_seconds)
