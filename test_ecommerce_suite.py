import os
import sys
import time
from core.ecommerce_utils import detect_ecommerce_platform, parse_sales_number, parse_price, sanitize_product_title
from core.ecommerce_exporter import EcommerceExporter
from core.ecommerce_history import EcommerceHistoryManager

def run_tests():
    print("========== 开始 6 大电商爆款监控系统自动化单测 ==========")

    # 1. 6 大电商平台智能识别单测
    print("[1] 测试 6 大电商平台 URL 智能识别 (detect_ecommerce_platform)...")
    assert detect_ecommerce_platform("https://mobile.yangkeduo.com/goods.html?goods_id=123") == "pdd", "拼多多识别失败"
    assert detect_ecommerce_platform("https://item.taobao.com/item.htm?id=654321") == "taobao", "淘宝识别失败"
    assert detect_ecommerce_platform("https://haohuo.jinritemai.com/views/product/item2?id=111") == "douyin_ec", "抖音电商识别失败"
    assert detect_ecommerce_platform("https://shop.tiktok.com/view/product/172938472") == "tiktok_shop", "TikTok Shop识别失败"
    assert detect_ecommerce_platform("https://www.amazon.com/dp/B08N5WRWNW") == "amazon", "Amazon识别失败"
    assert detect_ecommerce_platform("https://www.temu.com/goods.html?goods_id=8888") == "temu", "Temu识别失败"
    print(" -> [PASS] 6 大电商平台识别 100% 通过！")

    # 2. 销量文本清洗单测
    print("[2] 测试各电商销量解析 (parse_sales_number)...")
    assert parse_sales_number("已拼10万+件") == 100000, "拼多多销量解析失败"
    assert parse_sales_number("已售1.5万件") == 15000, "抖音销量解析失败"
    assert parse_sales_number("月销 3000+") == 3000, "淘宝月销解析失败"
    assert parse_sales_number("50K+ bought in past month") == 50000, "亚马逊销量解析失败"
    assert parse_sales_number("100K+ sold") == 100000, "Temu销量解析失败"
    assert parse_sales_number("850件") == 850, "纯数字销量解析失败"
    print(" -> [PASS] 国内外销量格式清洗 100% 通过！")

    # 3. 价格提取单测
    print("[3] 测试多币种价格解析 (parse_price)...")
    assert parse_price("￥89.90") == 89.9, "人民币价格解析失败"
    assert parse_price("$29.99") == 29.99, "美元价格解析失败"
    assert parse_price("券后 59.9") == 59.9, "券后价格解析失败"
    assert parse_price("$19.99 - $29.99") == 19.99, "价格区间解析失败"
    print(" -> [PASS] 多币种价格解析 100% 通过！")

    # 4. Excel 报表生成单测
    print("[4] 测试 Excel 选品报表生成 (EcommerceExporter)...")
    test_out = "materials/test_ecommerce"
    exporter = EcommerceExporter(output_dir=test_out)
    dummy_products = [
        {
            "platform_name": "拼多多",
            "title": "爆款重磅加厚毛衫",
            "price": 49.9,
            "sales": 100000,
            "rating": "4.9分",
            "store_name": "源头工厂店",
            "url": "https://mobile.yangkeduo.com/goods.html?goods_id=1",
            "material_dir": "materials/test/pdd_01",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "platform_name": "Amazon",
            "title": "Mens Heavyweight Hoodie",
            "price": 28.5,
            "sales": 50000,
            "rating": "4.6★",
            "store_name": "Amazon US Store",
            "url": "https://www.amazon.com/dp/B001",
            "material_dir": "materials/test/amz_01",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    res_path = exporter.export_excel(dummy_products, filename="test_export.xlsx")
    assert os.path.exists(res_path), "Excel 生成失败"
    print(f" -> [PASS] Excel 报表生成成功: {res_path}")

    # 清理测试文件
    if os.path.exists(res_path):
        os.remove(res_path)
    if os.path.exists(test_out):
        try:
            os.rmdir(test_out)
        except Exception:
            pass

    # 5. 历史排重测试
    print("[5] 测试电商排重库 (EcommerceHistoryManager)...")
    test_db = "data/test_ecom_history.json"
    if os.path.exists(test_db):
        os.remove(test_db)
    hm = EcommerceHistoryManager(test_db)
    hm.record_product("item_999", "pdd", "测试商品", 39.9, 5000, "materials/test")
    assert hm.is_recorded("item_999") is True
    assert hm.is_recorded("item_not_exist") is False
    if os.path.exists(test_db):
        os.remove(test_db)
    print(" -> [PASS] 电商历史排重库通过！")

    print("\n========== 6 大电商系统核心单测 100% 全部通过！ ==========")

if __name__ == "__main__":
    run_tests()
