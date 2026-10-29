import os
import sys
import time
from core.utils import parse_number, is_within_days, detect_platform
from core.downloader import sanitize_filename, MultiPlatformDownloader
from core.history_manager import HistoryManager

def run_tests():
    print("========== 开始四大平台 (抖音/小红书/TikTok/Instagram) 自动化单测 ==========")
    
    # 1. 平台自动识别测试
    print("[1] 测试平台识别 (detect_platform)...")
    assert detect_platform("https://www.douyin.com/user/MS4wLjABAAAA...") == "douyin", "抖音识别失败"
    assert detect_platform("https://www.xiaohongshu.com/user/profile/5b...") == "xhs", "小红书识别失败"
    assert detect_platform("https://www.tiktok.com/@tiktok") == "tiktok", "TikTok识别失败"
    assert detect_platform("https://www.instagram.com/zara/") == "instagram", "Instagram识别失败"
    print(" -> [PASS] 4大平台 URL 智能识别 100% 通过！")

    # 2. 中英文数值解析测试
    print("[2] 测试中英文数值解析器 (parse_number)...")
    assert parse_number("1.5万") == 15000, "1.5万 解析失败"
    assert parse_number("2.3W") == 23000, "2.3W 解析失败"
    assert parse_number("10.5K") == 10500, "10.5K 解析失败"
    assert parse_number("1.2M") == 1200000, "1.2M 解析失败"
    assert parse_number("9999") == 9999, "9999 解析失败"
    assert parse_number("12,345") == 12345, "逗号数字解析失败"
    print(" -> [PASS] 中英文计数单位 (万/W/K/M) 解析通过！")

    # 3. 文件名安全清洗测试
    print("[3] 测试 Windows 文件名安全清洗 (sanitize_filename)...")
    unsafe_title = '抖音爆款毛衫:新款?超帅/推荐|必须买*<绝了> "高质量" #穿搭'
    cleaned = sanitize_filename(unsafe_title, max_length=30)
    for bad_char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        assert bad_char not in cleaned, f"仍包含非法字符: {bad_char}"
    print(f" -> 清洗后: {cleaned}")
    print(" -> [PASS] 文件名安全清洗通过！")

    # 4. 历史记录库去重测试
    print("[4] 测试历史去重库 (HistoryManager)...")
    test_db = "data/test_history.json"
    if os.path.exists(test_db):
        os.remove(test_db)
    hm = HistoryManager(test_db)
    hm.record_download("douyin_7123456", "抖音博主A", "爆款毛衫视频", 25000, 150000, "materials/viral_competitors/dummy.mp4")
    assert hm.is_downloaded("douyin_7123456") is True, "抖音视频查重失败"
    assert hm.is_downloaded("xhs_9999999") is False, "未录入视频不应查重命中"
    if os.path.exists(test_db):
        os.remove(test_db)
    print(" -> [PASS] 跨平台历史排重库测试通过！")

    print("\n========== 四大平台架构所有测试用例 100% 验证通过！ ==========")

if __name__ == "__main__":
    run_tests()
