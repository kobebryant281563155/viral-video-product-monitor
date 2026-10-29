import os
import sys
import argparse
from core.competitor_monitor import CompetitorMonitorApp
from core.downloader import VideoDownloader

def main():
    parser = argparse.ArgumentParser(description="TikTok 竞品爆款监控与无水印自动下载系统")
    parser.add_argument("--mode", choices=["once", "daemon", "test-download"], default="once",
                        help="运行模式: once(单次巡检), daemon(定时轮询), test-download(测试下载器)")
    parser.add_argument("--config", default="config/competitors.json", help="配置文件路径")
    parser.add_argument("--hours", type=int, default=4, help="定时模式下的巡检间隔(小时)")
    parser.add_argument("--test-url", default="https://www.tiktok.com/@tiktok/video/7200000000000000000", help="测试下载视频URL")

    args = parser.parse_args()

    # 确保当前目录为工作区根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    if args.mode == "test-download":
        print("[TEST] 正在测试无水印下载引擎...")
        dl = VideoDownloader(download_dir="materials/viral_competitors")
        sample_meta = {
            "id": "test_sample_001",
            "url": args.test_url,
            "creator": "OfficialTikTok",
            "title": "TikTok官方测试视频",
            "likes": 88888,
            "views": 666666
        }
        res = dl.download_video(sample_meta)
        if res:
            print(f"[TEST SUCCESS] 测试下载成功，保存至: {res}")
        else:
            print("[TEST FAIL] 测试下载失败，请检查网络或该测试视频链接是否有效。")
        return

    app = CompetitorMonitorApp(config_path=args.config)
    
    if args.mode == "daemon":
        interval = args.hours or app.config.get("schedule", {}).get("interval_hours", 4)
        app.run_daemon(interval_hours=interval)
    else:
        app.run_once()

if __name__ == "__main__":
    main()
