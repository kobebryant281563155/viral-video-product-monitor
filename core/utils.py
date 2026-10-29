import re
import time
from typing import Union

def detect_platform(url: str) -> str:
    """根据 URL 自动识别平台"""
    u = url.lower()
    if "douyin.com" in u or "iesdouyin.com" in u:
        return "douyin"
    elif "xiaohongshu.com" in u or "xhslink.com" in u:
        return "xhs"
    elif "instagram.com" in u or "instagr.am" in u:
        return "instagram"
    elif "tiktok.com" in u:
        return "tiktok"
    return "unknown"

def parse_number(text: Union[str, int, float]) -> int:
    """
    将 12.5K, 1.2M, 1.5万, 9999, 12,345 等格式转换为绝对整数
    支持中英文计数单位（K, M, B, 万, 亿, W）
    """
    if isinstance(text, (int, float)):
        return int(text)

    if not text:
        return 0

    s = str(text).strip().upper().replace(",", "")
    
    # 匹配中文单位：万、亿、W
    m_cn = re.search(r"([\d\.]+)\s*([万亿W])", s)
    if m_cn:
        num_str, unit = m_cn.groups()
        try:
            val = float(num_str)
            if unit in ["万", "W"]:
                return int(val * 10000)
            elif unit == "亿":
                return int(val * 100000000)
        except ValueError:
            pass

    # 匹配英文单位：K, M, B
    m_en = re.search(r"([\d\.]+)\s*([KMB]?)", s)
    if m_en:
        num_str, unit = m_en.groups()
        try:
            val = float(num_str)
            if unit == "K":
                return int(val * 1000)
            elif unit == "M":
                return int(val * 1000000)
            elif unit == "B":
                return int(val * 1000000000)
            return int(val)
        except ValueError:
            pass

    return 0

def is_within_days(timestamp: int, max_days: int) -> bool:
    """判断时间戳是否在近 max_days 天内"""
    if max_days <= 0 or not timestamp:
        return True
    now = time.time()
    diff_days = (now - timestamp) / 86400.0
    return diff_days <= max_days
