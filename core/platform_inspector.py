import os
import json
import time
import random
from typing import List, Dict, Any, Optional
from core.utils import parse_number, is_within_days, detect_platform

class PlatformInspector:
    """跨平台 (TikTok / 抖音 / 小红书 / Instagram) 巡检核心引擎 (支持国内直连 + 海外 AdsPower 智能双通道)"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_conf = config.get("browser", {})
        self.filter_conf = config.get("filter_rules", {})
        self.cdp_endpoint = self.browser_conf.get("cdp_endpoint", "http://127.0.0.1:65209")
        
        self.playwright = None
        
        # 海外通道 (AdsPower 指纹代理)
        self.adspower_browser = None
        self.adspower_page = None

        # 国内通道 (本地直连网络，不走境外代理)
        self.local_browser = None
        self.local_page = None

    def _ensure_playwright(self):
        if not self.playwright:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()

    def _detect_active_cdp_port(self) -> Optional[int]:
        """自动扫描当前正在运行的 AdsPower 实例并提取调试端口"""
        import subprocess
        try:
            cmd = "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--remote-debugging-port=*' } | Select-Object -ExpandProperty CommandLine"
            output = subprocess.check_output(["powershell", "-Command", cmd], text=True, errors="ignore")
            import re
            m = re.search(r"--remote-debugging-port=(\d+)", output)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return None

    def get_page_for_platform(self, platform: str):
        """
        根据平台自动切换通道：
        - 国内平台 (douyin, xhs): 使用本地中国网络直连浏览器，防境外IP滑块风控
        - 海外平台 (tiktok, instagram): 使用 AdsPower 海外指纹浏览器环境
        """
        self._ensure_playwright()

        # 1. 国内平台 -> 本地直连网络
        if platform in ["douyin", "xhs"]:
            if not self.local_page or self.local_page.is_closed():
                print(f"[通道调度] 检测到国内平台【{platform}】，自动启用【本地直连网络通道】(避开境外IP拦截)...")
                try:
                    # 优先调用本地已安装的 Chrome，体验与真人无异
                    self.local_browser = self.playwright.chromium.launch(
                        headless=self.browser_conf.get("headless", False),
                        channel="chrome",
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                except Exception:
                    # 备用轻量内置 chromium
                    self.local_browser = self.playwright.chromium.launch(
                        headless=self.browser_conf.get("headless", False),
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                ctx = self.local_browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                self.local_page = ctx.new_page()
            return self.local_page

        # 2. 海外平台 -> AdsPower 海外代理指纹环境
        else:
            if not self.adspower_page or self.adspower_page.is_closed():
                print(f"[通道调度] 检测到海外平台【{platform}】，自动切换至【AdsPower 海外代理指纹通道】...")
                target_endpoint = self.cdp_endpoint
                connected = False

                try:
                    self.adspower_browser = self.playwright.chromium.connect_over_cdp(target_endpoint, timeout=3000)
                    connected = True
                except Exception:
                    detected_port = self._detect_active_cdp_port()
                    if detected_port:
                        target_endpoint = f"http://127.0.0.1:{detected_port}"
                        self.adspower_browser = self.playwright.chromium.connect_over_cdp(target_endpoint, timeout=5000)
                        connected = True
                    else:
                        raise RuntimeError(
                            f"检测到有海外平台({platform})需要巡检，但未找到已开启的 AdsPower 海外环境！\n"
                            "请在 AdsPower 客户端中点击【打开】任意一个海外代理浏览器窗口。"
                        )

                contexts = self.adspower_browser.contexts
                ctx = contexts[0] if contexts else self.adspower_browser.new_context()
                pages = ctx.pages
                self.adspower_page = pages[0] if pages else ctx.new_page()

            return self.adspower_page

    def connect(self) -> bool:
        """预检初始化"""
        return True

    def close(self):
        """释放所有通道的浏览器资源"""
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

    def inspect_creator(self, creator_info: Dict[str, str], max_videos: int = 15) -> List[Dict[str, Any]]:
        """巡检单个博主主页，自动路由到对应平台"""
        creator_name = creator_info.get("name", "Unknown")
        creator_url = creator_info.get("url", "")
        platform = detect_platform(creator_url)

        platform_names = {
            "douyin": "抖音",
            "xhs": "小红书",
            "tiktok": "TikTok",
            "instagram": "Instagram",
            "unknown": "未知平台"
        }
        p_label = platform_names.get(platform, platform)

        print(f"\n=======================================================")
        print(f"[CRUISE] 开始巡检【{p_label}】博主: {creator_name} -> {creator_url}")
        print(f"=======================================================")

        try:
            page = self.get_page_for_platform(platform)
        except Exception as e:
            print(f"[ERROR] 获取【{p_label}】浏览器通道失败: {e}")
            return []

        if not page:
            return []

        intercepted_videos: Dict[str, Dict[str, Any]] = {}

        # 统一网络包监听器
        def on_response(response):
            try:
                url = response.url
                if response.status != 200:
                    return

                # 1. TikTok 接口
                if platform == "tiktok" and ("item_list" in url or "post/item_list" in url):
                    data = response.json()
                    item_list = data.get("itemList") or data.get("items") or []
                    for item in item_list:
                        vid = str(item.get("id", ""))
                        if not vid:
                            continue
                        stats = item.get("stats", {})
                        video_meta = item.get("video", {})
                        author = item.get("author", {})
                        intercepted_videos[vid] = {
                            "id": vid,
                            "platform": "tiktok",
                            "url": f"https://www.tiktok.com/@{author.get('uniqueId', 'user')}/video/{vid}",
                            "creator": creator_name,
                            "title": item.get("desc", ""),
                            "likes": int(stats.get("diggCount", 0)),
                            "views": int(stats.get("playCount", 0)),
                            "comments": int(stats.get("commentCount", 0)),
                            "create_time": int(item.get("createTime", 0)),
                            "is_top": bool(item.get("isTop", False)),
                            "direct_download_url": video_meta.get("downloadAddr") or video_meta.get("playAddr")
                        }

                # 2. 抖音 接口
                elif platform == "douyin" and ("aweme/post" in url or "aweme/favorite" in url):
                    data = response.json()
                    aweme_list = data.get("aweme_list", [])
                    for aweme in aweme_list:
                        vid = str(aweme.get("aweme_id", ""))
                        if not vid:
                            continue
                        stats = aweme.get("statistics", {})
                        v_obj = aweme.get("video", {})
                        play_addr = v_obj.get("play_addr", {}).get("url_list", [])
                        direct = play_addr[0].replace("playwm", "play") if play_addr else None
                        
                        intercepted_videos[vid] = {
                            "id": vid,
                            "platform": "douyin",
                            "url": f"https://www.douyin.com/video/{vid}",
                            "creator": creator_name,
                            "title": aweme.get("desc", ""),
                            "likes": int(stats.get("digg_count", 0)),
                            "views": int(stats.get("play_count", 0)),
                            "comments": int(stats.get("comment_count", 0)),
                            "create_time": int(aweme.get("create_time", 0)),
                            "is_top": bool(aweme.get("is_top", False)),
                            "direct_download_url": direct
                        }

                # 3. 小红书 接口
                elif platform == "xhs" and "api/sns/web/v1/user_posted" in url:
                    data = response.json()
                    notes = data.get("data", {}).get("notes", [])
                    for note in notes:
                        vid = str(note.get("note_id") or note.get("id", ""))
                        if not vid:
                            continue
                        # 只筛选视频笔记，或者包含视频的笔记
                        interact = note.get("interact_info", {})
                        likes_cnt = parse_number(interact.get("liked_count", 0))
                        title = note.get("display_title", "")
                        intercepted_videos[vid] = {
                            "id": vid,
                            "platform": "xhs",
                            "url": f"https://www.xiaohongshu.com/explore/{vid}",
                            "creator": creator_name,
                            "title": title,
                            "likes": likes_cnt,
                            "views": 0,
                            "comments": 0,
                            "create_time": int(time.time()),
                            "is_top": False,
                            "direct_download_url": None
                        }
            except Exception:
                pass

        page.on("response", on_response)

        try:
            page.goto(creator_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(3.0, 5.0))

            # 滚动触发更多卡片加载
            for _ in range(3):
                if len(intercepted_videos) >= max_videos:
                    break
                page.evaluate("window.scrollBy(0, 1000);")
                time.sleep(random.uniform(1.5, 2.5))

            # DOM 兜底
            if not intercepted_videos:
                print(f"[INFO] 网络 API 未触发，启用【{p_label}】DOM 兜底提取...")
                dom_items = self._fallback_dom_inspect(page, platform, creator_name)
                for item in dom_items:
                    intercepted_videos[item["id"]] = item

        except Exception as e:
            print(f"[ERROR] 访问博主页面异常: {e}")
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

        all_videos = list(intercepted_videos.values())
        print(f"[INFO] 该博主主页共探测到 {len(all_videos)} 条视频。")

        viral_candidates = self._filter_viral_videos(all_videos)
        print(f"[FILTER] 经过爆款规则过滤，筛选出 {len(viral_candidates)} 条潜力爆款视频！")
        return viral_candidates

    def _fallback_dom_inspect(self, page, platform: str, creator_name: str) -> List[Dict[str, Any]]:
        """跨平台 DOM 兜底提取"""
        results = []
        try:
            # 抖音卡片
            if platform == "douyin":
                links = page.query_selector_all("a[href*='/video/']")
                for link in links:
                    href = link.get_attribute("href") or ""
                    vid = href.split("/video/")[-1].split("?")[0].strip("/")
                    if vid and len(vid) > 5:
                        txt = link.inner_text() or ""
                        results.append({
                            "id": vid,
                            "platform": "douyin",
                            "url": f"https://www.douyin.com/video/{vid}",
                            "creator": creator_name,
                            "title": f"douyin_{vid}",
                            "likes": parse_number(txt),
                            "views": 0,
                            "create_time": 0,
                            "is_top": False,
                            "direct_download_url": None
                        })

            # 小红书卡片
            elif platform == "xhs":
                cards = page.query_selector_all("section.note-item, a[href*='/explore/']")
                for card in cards:
                    href = card.get_attribute("href") or ""
                    if not href:
                        a_tag = card.query_selector("a[href*='/explore/']")
                        if a_tag:
                            href = a_tag.get_attribute("href") or ""
                    vid = href.split("/explore/")[-1].split("?")[0].strip("/")
                    if vid:
                        txt = card.inner_text() or ""
                        results.append({
                            "id": vid,
                            "platform": "xhs",
                            "url": f"https://www.xiaohongshu.com/explore/{vid}",
                            "creator": creator_name,
                            "title": f"xhs_{vid}",
                            "likes": parse_number(txt),
                            "views": 0,
                            "create_time": 0,
                            "is_top": False,
                            "direct_download_url": None
                        })

            # Instagram Reels 卡片
            elif platform == "instagram":
                links = page.query_selector_all("a[href*='/reel/'], a[href*='/p/']")
                for link in links:
                    href = link.get_attribute("href") or ""
                    shortcode = href.split("/")[-2] if href.endswith("/") else href.split("/")[-1]
                    if shortcode:
                        results.append({
                            "id": shortcode,
                            "platform": "instagram",
                            "url": f"https://www.instagram.com/reel/{shortcode}/",
                            "creator": creator_name,
                            "title": f"instagram_{shortcode}",
                            "likes": 0,
                            "views": 0,
                            "create_time": 0,
                            "is_top": False,
                            "direct_download_url": None
                        })

            # TikTok 卡片
            elif platform == "tiktok":
                links = page.query_selector_all("a[href*='/video/']")
                for link in links:
                    href = link.get_attribute("href") or ""
                    parts = href.split("/video/")
                    if len(parts) >= 2:
                        vid = parts[1].split("?")[0].strip("/")
                        txt = link.inner_text() or ""
                        results.append({
                            "id": vid,
                            "platform": "tiktok",
                            "url": href if href.startswith("http") else f"https://www.tiktok.com{href}",
                            "creator": creator_name,
                            "title": f"tiktok_{vid}",
                            "likes": 0,
                            "views": parse_number(txt),
                            "create_time": 0,
                            "is_top": False,
                            "direct_download_url": None
                        })
        except Exception as e:
            print(f"[WARN] DOM 兜底解析异常: {e}")

        return results

    def _filter_viral_videos(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        min_likes = self.filter_conf.get("min_likes", 10000)
        min_views = self.filter_conf.get("min_views", 0)
        max_age_days = self.filter_conf.get("max_age_days", 30)
        ignore_pinned = self.filter_conf.get("ignore_pinned", True)

        viral_list = []
        for v in videos:
            if ignore_pinned and v.get("is_top"):
                continue

            if max_age_days > 0 and v.get("create_time", 0) > 0:
                if not is_within_days(v["create_time"], max_age_days):
                    continue

            likes = v.get("likes", 0)
            views = v.get("views", 0)

            # 只要点赞数或播放数达到阈值，或门槛设为0（全抓）
            if min_likes == 0:
                viral_list.append(v)
            elif likes >= min_likes:
                viral_list.append(v)
            elif likes == 0 and min_views > 0 and views >= min_views:
                viral_list.append(v)

        return viral_list
