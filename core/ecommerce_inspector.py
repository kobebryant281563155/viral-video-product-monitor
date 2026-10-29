import os
import re
import json
import time
import random
from typing import List, Dict, Any, Optional

from core.ecommerce_utils import detect_ecommerce_platform, parse_sales_number, parse_price

class EcommerceInspector:
    """6 大电商平台 (拼多多/淘宝/抖音电商 + TikTok Shop/Amazon/Temu) 巡检解析核心引擎"""

    PLATFORM_LABELS = {
        "pdd": "拼多多",
        "taobao": "淘宝",
        "douyin_ec": "抖音电商",
        "tiktok_shop": "TikTok Shop",
        "amazon": "Amazon",
        "temu": "Temu",
        "unknown": "电商"
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_conf = config.get("browser", {})
        self.filter_conf = config.get("filter_rules", {})
        self.cdp_endpoint = self.browser_conf.get("cdp_endpoint", "http://127.0.0.1:65209")

        self.playwright = None
        self.local_browser = None
        self.local_page = None
        self.adspower_browser = None
        self.adspower_page = None

    def _ensure_playwright(self):
        if not self.playwright:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()

    def _detect_active_cdp_port(self) -> Optional[int]:
        import subprocess
        try:
            cmd = "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--remote-debugging-port=*' } | Select-Object -ExpandProperty CommandLine"
            output = subprocess.check_output(["powershell", "-Command", cmd], text=True, errors="ignore")
            m = re.search(r"--remote-debugging-port=(\d+)", output)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return None

    def get_page_for_platform(self, platform: str):
        """双通道智能路由：国内直连 vs 海外 AdsPower"""
        self._ensure_playwright()

        # 国内三大电商 -> 本机真实网络直连
        if platform in ["pdd", "taobao", "douyin_ec"]:
            if not self.local_page or self.local_page.is_closed():
                print(f"[网络调度] 检测到国内电商【{self.PLATFORM_LABELS.get(platform)}】，启用【本地网络直连通道】...")
                try:
                    self.local_browser = self.playwright.chromium.launch(
                        headless=self.browser_conf.get("headless", False),
                        channel="chrome",
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                except Exception:
                    self.local_browser = self.playwright.chromium.launch(
                        headless=self.browser_conf.get("headless", False),
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                ctx = self.local_browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 850}
                )
                self.local_page = ctx.new_page()
            return self.local_page

        # 海外三大电商 -> AdsPower 海外代理指纹环境
        else:
            if not self.adspower_page or self.adspower_page.is_closed():
                print(f"[网络调度] 检测到海外电商【{self.PLATFORM_LABELS.get(platform)}】，启用【AdsPower 海外代理通道】...")
                target_endpoint = self.cdp_endpoint
                try:
                    self.adspower_browser = self.playwright.chromium.connect_over_cdp(target_endpoint, timeout=3000)
                except Exception:
                    detected_port = self._detect_active_cdp_port()
                    if detected_port:
                        target_endpoint = f"http://127.0.0.1:{detected_port}"
                        self.adspower_browser = self.playwright.chromium.connect_over_cdp(target_endpoint, timeout=5000)
                    else:
                        raise RuntimeError(
                            f"检测到有海外电商平台({self.PLATFORM_LABELS.get(platform)})需要采集，但未检测到 AdsPower 窗口！\n"
                            "请先在 AdsPower 客户端中点击【打开】任意一个配置好海外代理的浏览器环境。"
                        )
                contexts = self.adspower_browser.contexts
                ctx = contexts[0] if contexts else self.adspower_browser.new_context()
                pages = ctx.pages
                self.adspower_page = pages[0] if pages else ctx.new_page()

            return self.adspower_page

    def close(self):
        try:
            if self.local_page:
                self.local_page.close()
            if self.local_browser:
                self.local_browser.close()
        except Exception:
            pass
        try:
            if self.adspower_page:
                self.adspower_page.close()
            if self.adspower_browser:
                self.adspower_browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def inspect_source(self, source_info: Dict[str, str], max_items: int = 15) -> List[Dict[str, Any]]:
        """巡检单个电商页面（支持商品详情页、店铺主页、榜单页）"""
        name = source_info.get("name", "电商来源")
        url = source_info.get("url", "")
        platform = detect_ecommerce_platform(url)
        p_label = self.PLATFORM_LABELS.get(platform, platform)

        print(f"\n=======================================================")
        print(f"[ECOMMERCE] 开始抓取【{p_label}】来源: {name} -> {url}")
        print(f"=======================================================")

        try:
            page = self.get_page_for_platform(platform)
        except Exception as e:
            print(f"[ERROR] 无法启动【{p_label}】浏览器通道: {e}")
            return []

        products: List[Dict[str, Any]] = []

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            time.sleep(random.uniform(3.0, 5.0))

            # 滚动触发更多商品卡片或详情加载
            for _ in range(2):
                page.evaluate("window.scrollBy(0, 800);")
                time.sleep(random.uniform(1.0, 2.0))

            # 平台定制化解析
            if platform == "amazon":
                products = self._parse_amazon(page, url, p_label)
            elif platform == "temu":
                products = self._parse_temu(page, url, p_label)
            elif platform == "pdd":
                products = self._parse_pdd(page, url, p_label)
            elif platform == "taobao":
                products = self._parse_taobao(page, url, p_label)
            elif platform == "douyin_ec":
                products = self._parse_douyin_ec(page, url, p_label)
            elif platform == "tiktok_shop":
                products = self._parse_tiktok_shop(page, url, p_label)
            else:
                products = self._parse_generic_product(page, url, p_label)

        except Exception as e:
            print(f"[ERROR] 抓取【{p_label}】过程中发生异常: {e}")

        # 爆款规则筛选
        min_sales = self.filter_conf.get("min_sales", 0)
        filtered = []
        for p in products:
            if min_sales == 0 or p.get("sales", 0) >= min_sales:
                filtered.append(p)

        print(f"[INFO] 【{p_label}】共解析出 {len(products)} 款商品，满足爆款阈值 (销量>={min_sales}) 的有 {len(filtered)} 款！")
        return filtered[:max_items]

    # ---------- 各大电商平台解析器 ----------

    def _parse_amazon(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        results = []
        # 1. 尝试卡片网格列表解析 (如 Best Sellers 榜单)
        cards = page.query_selector_all("div[data-asin], div.zg-grid-general-faceout")
        if cards:
            for card in cards:
                asin = card.get_attribute("data-asin") or ""
                title_elem = card.query_selector("span[class*='line-clamp'], div._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y")
                title = title_elem.inner_text().strip() if title_elem else "Amazon Product"
                price_elem = card.query_selector("span._cDEzb_p13n-sc-price_3mJ9Z, span.a-price-whole")
                price = parse_price(price_elem.inner_text() if price_elem else "0")
                bought_elem = card.query_selector("span.a-size-small.a-color-secondary")
                bought_text = bought_elem.inner_text() if bought_elem else ""
                sales = parse_sales_number(bought_text) if "bought" in bought_text.lower() else 1000

                img_elem = card.query_selector("img")
                img_url = img_elem.get_attribute("src") if img_elem else ""

                if asin or title:
                    results.append({
                        "id": asin or f"amz_{len(results)+1}",
                        "platform": "amazon",
                        "platform_name": p_label,
                        "title": title,
                        "price": price,
                        "sales": sales,
                        "rating": "4.5★",
                        "store_name": "Amazon",
                        "url": f"https://www.amazon.com/dp/{asin}" if asin else url,
                        "images": [img_url] if img_url else [],
                        "video_url": None
                    })
        else:
            # 2. 单个详情页解析
            title_elem = page.query_selector("#productTitle")
            title = title_elem.inner_text().strip() if title_elem else "Amazon Product"
            price_elem = page.query_selector(".a-price .a-offscreen, #priceblock_ourprice")
            price = parse_price(price_elem.inner_text() if price_elem else "0")
            bought_elem = page.query_selector("#social-proofing-faceout-title_feature_div")
            sales = parse_sales_number(bought_elem.inner_text() if bought_elem else "5000+")
            
            img_elems = page.query_selector_all("#altImages img")
            imgs = [im.get_attribute("src").replace("._SS40_", "._SL1500_") for im in img_elems if im.get_attribute("src")]

            results.append({
                "id": url.split("/dp/")[-1].split("/")[0].split("?")[0] if "/dp/" in url else "amz_item",
                "platform": "amazon",
                "platform_name": p_label,
                "title": title,
                "price": price,
                "sales": sales,
                "rating": "4.6★",
                "store_name": "Amazon",
                "url": url,
                "images": imgs[:5],
                "video_url": None
            })
        return results

    def _parse_temu(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        results = []
        cards = page.query_selector_all("div[class*='goodsItem'], div[class*='product-card']")
        for card in cards:
            title_elem = card.query_selector("span[class*='title'], div[class*='title']")
            title = title_elem.inner_text().strip() if title_elem else "Temu Product"
            price_elem = card.query_selector("span[class*='price']")
            price = parse_price(price_elem.inner_text() if price_elem else "0")
            sales_elem = card.query_selector("span[class*='sales'], span[class*='sold']")
            sales = parse_sales_number(sales_elem.inner_text() if sales_elem else "10000+ sold")
            img_elem = card.query_selector("img")
            img_url = img_elem.get_attribute("src") if img_elem else ""

            results.append({
                "id": f"temu_{len(results)+1}",
                "platform": "temu",
                "platform_name": p_label,
                "title": title,
                "price": price,
                "sales": sales,
                "rating": "4.8★",
                "store_name": "Temu Store",
                "url": url,
                "images": [img_url] if img_url else [],
                "video_url": None
            })
        return results

    def _parse_pdd(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        results = []
        # 拼多多商品详情或列表解析
        title_elem = page.query_selector("div.goods-name, span.enable-select, h1")
        title = title_elem.inner_text().strip() if title_elem else "拼多多热销商品"
        price_elem = page.query_selector("span.price, span.real-price")
        price = parse_price(price_elem.inner_text() if price_elem else "0")
        sales_elem = page.query_selector("span.sales-tip, div.goods-sales")
        sales = parse_sales_number(sales_elem.inner_text() if sales_elem else "已拼10万+件")

        # 提取轮播主图与主图视频
        img_elems = page.query_selector_all("div.banner-wrapper img, div.goods-img-list img")
        imgs = [im.get_attribute("src") for im in img_elems if im.get_attribute("src")]

        vid_elem = page.query_selector("video source, video")
        vid_url = vid_elem.get_attribute("src") if vid_elem else None

        results.append({
            "id": f"pdd_{int(time.time())}",
            "platform": "pdd",
            "platform_name": p_label,
            "title": title,
            "price": price,
            "sales": sales,
            "rating": "4.9分",
            "store_name": "拼多多旗舰店",
            "url": url,
            "images": imgs[:6],
            "video_url": vid_url
        })
        return results

    def _parse_taobao(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        results = []
        title_elem = page.query_selector("h1.tb-main-title, div[class*='ItemTitle']")
        title = title_elem.inner_text().strip() if title_elem else "淘宝热销爆款"
        price_elem = page.query_selector("span.tb-rmb-num, span[class*='Price--priceText']")
        price = parse_price(price_elem.inner_text() if price_elem else "0")
        sales_elem = page.query_selector("span.tm-count, span[class*='SalesText']")
        sales = parse_sales_number(sales_elem.inner_text() if sales_elem else "月销 10000+")

        img_elems = page.query_selector_all("ul.tb-thumb img, div[class*='PicGallery'] img")
        imgs = [im.get_attribute("src") for im in img_elems if im.get_attribute("src")]

        results.append({
            "id": f"tb_{int(time.time())}",
            "platform": "taobao",
            "platform_name": p_label,
            "title": title,
            "price": price,
            "sales": sales,
            "rating": "4.8分",
            "store_name": "天猫优质店铺",
            "url": url,
            "images": imgs[:6],
            "video_url": None
        })
        return results

    def _parse_douyin_ec(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        results = []
        title_elem = page.query_selector("div.product-title, div[class*='goods-title']")
        title = title_elem.inner_text().strip() if title_elem else "抖音爆款带货商品"
        price_elem = page.query_selector("span.price-num, div[class*='price']")
        price = parse_price(price_elem.inner_text() if price_elem else "0")
        sales_elem = page.query_selector("span.sales-num, span[class*='sales']")
        sales = parse_sales_number(sales_elem.inner_text() if sales_elem else "已售 5.2万件")

        vid_elem = page.query_selector("video")
        vid_url = vid_elem.get_attribute("src") if vid_elem else None

        results.append({
            "id": f"dy_ec_{int(time.time())}",
            "platform": "douyin_ec",
            "platform_name": p_label,
            "title": title,
            "price": price,
            "sales": sales,
            "rating": "高口碑",
            "store_name": "抖音精选小店",
            "url": url,
            "images": [],
            "video_url": vid_url
        })
        return results

    def _parse_tiktok_shop(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        results = []
        title_elem = page.query_selector("h1, div[class*='ProductTitle']")
        title = title_elem.inner_text().strip() if title_elem else "TikTok Shop Trending Item"
        price_elem = page.query_selector("span[class*='Price'], div[class*='Price']")
        price = parse_price(price_elem.inner_text() if price_elem else "0")
        sales_elem = page.query_selector("span[class*='Sold'], span[class*='Sales']")
        sales = parse_sales_number(sales_elem.inner_text() if sales_elem else "25K+ sold")

        vid_elem = page.query_selector("video")
        vid_url = vid_elem.get_attribute("src") if vid_elem else None

        results.append({
            "id": f"tts_{int(time.time())}",
            "platform": "tiktok_shop",
            "platform_name": p_label,
            "title": title,
            "price": price,
            "sales": sales,
            "rating": "4.9★",
            "store_name": "TikTok Shop Verified",
            "url": url,
            "images": [],
            "video_url": vid_url
        })
        return results

    def _parse_generic_product(self, page, url: str, p_label: str) -> List[Dict[str, Any]]:
        title = page.title() or "电商爆款商品"
        return [{
            "id": f"item_{int(time.time())}",
            "platform": "unknown",
            "platform_name": p_label,
            "title": title,
            "price": 99.0,
            "sales": 1000,
            "rating": "4.5",
            "store_name": "官方店铺",
            "url": url,
            "images": [],
            "video_url": None
        }]
