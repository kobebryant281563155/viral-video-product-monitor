import re
import os
from typing import Union, Tuple, Optional

def detect_ecommerce_platform(url: str) -> str:
    """自动识别 6 大电商平台"""
    u = url.lower()
    if "pinduoduo.com" in u or "yangkeduo.com" in u:
        return "pdd"
    elif "taobao.com" in u or "tmall.com" in u:
        return "taobao"
    elif "jinritemai.com" in u or ("douyin.com" in u and ("shop" in u or "goods" in u or "product" in u)):
        return "douyin_ec"
    elif "shop.tiktok.com" in u or ("tiktok.com" in u and ("product" in u or "shop" in u)):
        return "tiktok_shop"
    elif "amazon." in u or "amzn.to" in u:
        return "amazon"
    elif "temu.com" in u or "temu.to" in u:
        return "temu"
    
    # 默认兜底根据域名特征判断
    if "douyin.com" in u:
        return "douyin_ec"
    if "tiktok.com" in u:
        return "tiktok_shop"

    return "unknown"

def parse_sales_number(text: Union[str, int, float]) -> int:
    """
    解析各电商平台销量文本：
    - "已拼10万+件" -> 100000
    - "已售1.5万件" -> 15000
    - "50K+ bought in past month" -> 50000
    - "100K+ sold" -> 100000
    - "月销 3000+" -> 3000
    - "300+人付款" -> 300
    """
    if isinstance(text, (int, float)):
        return int(text)
    if not text:
        return 0

    s = str(text).strip().upper().replace(",", "")

    # 中文销量解析 (万, 亿, W)
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

    # 英文销量解析 (K, M) 如 50K+
    m_en = re.search(r"([\d\.]+)\s*([KM])", s)
    if m_en:
        num_str, unit = m_en.groups()
        try:
            val = float(num_str)
            if unit == "K":
                return int(val * 1000)
            elif unit == "M":
                return int(val * 1000000)
        except ValueError:
            pass

    # 提取纯数字 如 300+ / 850
    m_num = re.search(r"(\d+)", s)
    if m_num:
        try:
            return int(m_num.group(1))
        except ValueError:
            pass

    return 0

def parse_price(text: Union[str, int, float]) -> float:
    """
    解析各电商货币价格：
    - "￥89.90" -> 89.9
    - "$29.99" -> 29.99
    - "券后 59.9" -> 59.9
    - "$19.99 - $29.99" -> 19.99
    """
    if isinstance(text, (int, float)):
        return float(text)
    if not text:
        return 0.0

    s = str(text).strip()
    # 查找第一个浮点数或整数
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 0.0

def sanitize_product_title(title: str, max_length: int = 35) -> str:
    """清洗商品标题非法字符"""
    clean = re.sub(r'[\\/*?:"<>|\r\n\t]', "_", title)
    clean = clean.strip(". ")
    if not clean:
        clean = "product_item"
    return clean[:max_length]
