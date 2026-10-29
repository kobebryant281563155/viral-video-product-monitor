import os
import sys
import time
import json
import random
import argparse
from typing import Dict, Any, List

from core.ecommerce_inspector import EcommerceInspector
from core.ecommerce_downloader import EcommerceDownloader
from core.ecommerce_exporter import EcommerceExporter
from core.ecommerce_history import EcommerceHistoryManager

class EcommerceMonitorApp:
    """6 大电商平台 (拼多多/淘宝/抖音电商 + TikTok Shop/Amazon/Temu) 爆款监控控制器"""

    def __init__(self, config_path: str = "config/ecommerce.json"):
        self.config_path = config_path
        self.config = self._load_config()

        storage_conf = self.config.get("storage", {})
        self.output_dir = storage_conf.get("output_dir", "materials/ecommerce_products")
        self.download_images = storage_conf.get("download_images", True)
        self.download_videos = storage_conf.get("download_videos", True)

        self.downloader = EcommerceDownloader(base_dir=self.output_dir)
        self.exporter = EcommerceExporter(output_dir=self.output_dir)
        self.history = EcommerceHistoryManager(history_file="data/ecommerce_history.json")
        self.inspector = EcommerceInspector(config=self.config)

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"找不到配置文件: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run(self):
        print("\n" + "="*70)
        print("    国内外 6 大电商平台 (拼多多/淘宝/抖音电商 + TikTok/Amazon/Temu) 爆款监控    ")
        print("="*70)

        sources = self.config.get("sources", [])
        schedule_conf = self.config.get("schedule", {})
        jitter_min = schedule_conf.get("jitter_seconds_min", 3)
        jitter_max = schedule_conf.get("jitter_seconds_max", 6)
        max_items = self.config.get("filter_rules", {}).get("max_items_per_source", 10)

        all_collected_products: List[Dict[str, Any]] = []
        stats = {
            "sources_count": len(sources),
            "found_products": 0,
            "new_downloaded": 0,
            "skipped": 0
        }

        try:
            for idx, source in enumerate(sources, 1):
                s_name = source.get("name")
                print(f"\n>>> 进度 [{idx}/{len(sources)}]: 正在采集 {s_name}...")

                products = self.inspector.inspect_source(source, max_items=max_items)
                stats["found_products"] += len(products)

                for p in products:
                    item_id = str(p.get("id"))
                    
                    # 检查历史库排重
                    if self.history.is_recorded(item_id):
                        print(f"[SKIP] 商品 [{item_id}] 历史库中已记录，跳过。")
                        stats["skipped"] += 1
                        continue

                    # 下载商品主图包与商品带货短视频
                    saved_folder = self.downloader.download_product_materials(
                        p, 
                        download_images=self.download_images, 
                        download_videos=self.download_videos
                    )
                    p["material_dir"] = os.path.basename(saved_folder)

                    # 记录进历史库
                    self.history.record_product(
                        item_id=item_id,
                        platform=p.get("platform", "ecommerce"),
                        title=p.get("title", ""),
                        price=p.get("price", 0.0),
                        sales=p.get("sales", 0),
                        folder=saved_folder
                    )

                    all_collected_products.append(p)
                    stats["new_downloaded"] += 1

                # 拟人防爬随机延时
                if idx < len(sources):
                    sleep_time = random.uniform(jitter_min, jitter_max)
                    print(f"[WAIT] 拟人防风控休眠 {sleep_time:.1f} 秒后采集下一个电商页面...")
                    time.sleep(sleep_time)

        finally:
            self.inspector.close()

        # 生成 Excel 选品报表
        excel_file = None
        if all_collected_products:
            excel_file = self.exporter.export_excel(all_collected_products)

        # 输出汇总看板
        print("\n" + "="*70)
        print("                          电商爆款采集结果汇总                          ")
        print("="*70)
        print(f" 巡检电商来源数: {stats['sources_count']}")
        print(f" 发现商品总件数: {stats['found_products']}")
        print(f" 历史去重跳过数: {stats['skipped']}")
        print(f" 本次新增抓取数: {stats['new_downloaded']}")
        print(f" 历史库商品总数: {self.history.get_total_count()}")
        if excel_file:
            print(f" 📊 选品报表生成: {excel_file}")
        print("="*70)

        return excel_file

def main():
    parser = argparse.ArgumentParser(description="国内外6大电商平台爆款监控与素材抓取系统")
    parser.add_argument("--config", default="config/ecommerce.json", help="配置文件路径")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    app = EcommerceMonitorApp(config_path=args.config)
    app.run()

if __name__ == "__main__":
    main()
