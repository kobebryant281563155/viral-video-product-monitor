import os
import json
import time
import random
from typing import List, Dict, Any, Optional
from core.utils import parse_number, is_within_days

class TikTokInspector:
    """TikTok 账号巡检器：基于 Playwright CDP 网络拦截与自动化操作"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_conf = config.get("browser", {})
        self.filter_conf = config.get("filter_rules", {})
        self.cdp_endpoint = self.browser_conf.get("cdp_endpoint", "http://127.0.0.1:65209")
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _detect_active_cdp_port(self) -> Optional[int]:
        """自动扫描当前正在运行的 AdsPower / Chrome 实例并提取调试端口"""
        import subprocess
        try:
            cmd = "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--remote-debugging-port=*' } | Select-Object -ExpandProperty CommandLine"
            output = subprocess.check_output(["powershell", "-Command", cmd], text=True, errors="ignore")
            import re
            m = re.search(r"--remote-debugging-port=(\d+)", output)
            if m:
                port = int(m.group(1))
                return port
        except Exception:
            pass
        return None

    def connect(self) -> bool:
        """连接到 AdsPower 浏览器的 CDP 端口，或启动本地独立浏览器"""
        from playwright.sync_api import sync_playwright

        try:
            self.playwright = sync_playwright().start()
            
            # 1. 尝试配置中的默认端口
            target_endpoint = self.cdp_endpoint
            connected = False

            try:
                print(f"[INFO] 正在尝试通过 CDP 连接指纹浏览器: {target_endpoint}...")
                self.browser = self.playwright.chromium.connect_over_cdp(target_endpoint, timeout=3000)
                connected = True
            except Exception:
                # 2. 如果连接失败，自动嗅探当前电脑上打开的 AdsPower 窗口的实际端口
                print(f"[INFO] 默认端口未响应，正在自动搜索电脑上已打开的 AdsPower 窗口...")
                detected_port = self._detect_active_cdp_port()
                if detected_port:
                    target_endpoint = f"http://127.0.0.1:{detected_port}"
                    print(f"[INFO] 发现已开启的 AdsPower 浏览器，实际调试端口为: {detected_port}，正在连接...")
                    self.browser = self.playwright.chromium.connect_over_cdp(target_endpoint, timeout=5000)
                    connected = True
                else:
                    raise RuntimeError("未检测到已打开的 AdsPower 窗口。请先在 AdsPower 客户端中点击【打开】任意一个浏览器环境！")

            if connected:
                # 复用已有的 context 或创建新的
                contexts = self.browser.contexts
                if contexts:
                    self.context = contexts[0]
                else:
                    self.context = self.browser.new_context()

                pages = self.context.pages
                self.page = pages[0] if pages else self.context.new_page()
                print("[SUCCESS] 成功接入 AdsPower 指纹浏览器环境！")
                return True

        except Exception as e:
            print(f"\n[提示] 连接指纹浏览器失败: {e}")
            print("【操作指引】:")
            print(" 1. 打开桌面上的 AdsPower 软件；")
            print(" 2. 在账号列表里，随便找一个配置好代理的环境，点击【打开】按钮；")
            print(" 3. 浏览器窗口弹出来后，重新双击运行脚本即可自动连接！\n")
            return False

    def close(self):
        """释放资源"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def inspect_creator(self, creator_info: Dict[str, str], max_videos: int = 15) -> List[Dict[str, Any]]:
        """
        巡检单个博主主页，返回符合条件的爆款视频列表
        """
        creator_name = creator_info.get("name", "Unknown")
        creator_url = creator_info.get("url", "")
        print(f"\n=======================================================")
        print(f"[CRUISE] 开始巡检博主: 【{creator_name}】 -> {creator_url}")
        print(f"=======================================================")

        if not self.page:
            print("[ERROR] 浏览器页面未初始化，无法巡检。")
            return []

        intercepted_videos: Dict[str, Dict[str, Any]] = {}

        # 核心机制：监听官方 API 响应包
        def on_response(response):
            try:
                url = response.url
                if ("item_list" in url or "post/item_list" in url) and response.status == 200:
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
                            "url": f"https://www.tiktok.com/@{author.get('uniqueId', 'user')}/video/{vid}",
                            "creator": creator_name,
                            "title": item.get("desc", ""),
                            "likes": int(stats.get("diggCount", 0)),
                            "views": int(stats.get("playCount", 0)),
                            "comments": int(stats.get("commentCount", 0)),
                            "shares": int(stats.get("shareCount", 0)),
                            "create_time": int(item.get("createTime", 0)),
                            "is_top": bool(item.get("isTop", False)),
                            "direct_download_url": video_meta.get("downloadAddr") or video_meta.get("playAddr"),
                            "cover_url": video_meta.get("cover")
                        }
            except Exception:
                pass

        self.page.on("response", on_response)

        try:
            # 访问主页
            self.page.goto(creator_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(3.0, 5.0))

            # 平滑滚动 2~3 次以触发视频加载
            for scroll_idx in range(3):
                if len(intercepted_videos) >= max_videos:
                    break
                self.page.evaluate("window.scrollBy(0, 1000);")
                time.sleep(random.uniform(1.5, 2.5))

            # 如果网络包未能拦截到，兜底从 DOM 解析可见卡片
            if not intercepted_videos:
                print("[INFO] 网络 API 未直接触发，启用 DOM 兜底卡片探测...")
                dom_videos = self._fallback_dom_inspect(creator_name)
                for v in dom_videos:
                    intercepted_videos[v["id"]] = v

        except Exception as e:
            print(f"[ERROR] 访问博主主页异常: {e}")
        finally:
            try:
                self.page.remove_listener("response", on_response)
            except Exception:
                pass

        all_videos = list(intercepted_videos.values())
        print(f"[INFO] 该博主主页共探测到 {len(all_videos)} 条视频。")

        # 应用爆款过滤规则
        viral_candidates = self._filter_viral_videos(all_videos)
        print(f"[FILTER] 经过爆款阈值过滤，筛选出 {len(viral_candidates)} 条潜力爆款视频！")
        return viral_candidates

    def _fallback_dom_inspect(self, creator_name: str) -> List[Dict[str, Any]]:
        """DOM 兜底卡片提取器"""
        results = []
        try:
            # 定位常见的视频卡片元素
            links = self.page.query_selector_all("a[href*='/video/']")
            seen_ids = set()
            for link in links:
                href = link.get_attribute("href") or ""
                if "/video/" not in href:
                    continue
                parts = href.split("/video/")
                if len(parts) < 2:
                    continue
                vid = parts[1].split("?")[0].strip("/")
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)

                # 提取卡片内文字（通常是播放量）
                card_text = link.inner_text() or ""
                view_count = parse_number(card_text)

                results.append({
                    "id": vid,
                    "url": href if href.startswith("http") else f"https://www.tiktok.com{href}",
                    "creator": creator_name,
                    "title": f"video_{vid}",
                    "likes": 0,  # DOM卡片上默认只有播放数
                    "views": view_count,
                    "comments": 0,
                    "shares": 0,
                    "create_time": 0,
                    "is_top": False,
                    "direct_download_url": None
                })
        except Exception as e:
            print(f"[WARN] DOM 兜底解析失败: {e}")
        return results

    def _filter_viral_videos(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """依据配置过滤爆款"""
        min_likes = self.filter_conf.get("min_likes", 10000)
        min_views = self.filter_conf.get("min_views", 0)
        max_age_days = self.filter_conf.get("max_age_days", 30)
        ignore_pinned = self.filter_conf.get("ignore_pinned", True)

        viral_list = []
        for v in videos:
            # 1. 过滤置顶
            if ignore_pinned and v.get("is_top"):
                continue

            # 2. 过滤时效（超期老视频排除）
            if max_age_days > 0 and v.get("create_time", 0) > 0:
                if not is_within_days(v["create_time"], max_age_days):
                    continue

            # 3. 爆款阈值检查
            # 如果点赞数满足，或者通过DOM初筛播放数满足
            likes = v.get("likes", 0)
            views = v.get("views", 0)

            # 命中标准：点赞 >= min_likes，或者播放 >= min_views (当点赞未抓到时用播放兜底)
            is_viral = False
            if likes >= min_likes:
                is_viral = True
            elif likes == 0 and min_views > 0 and views >= min_views:
                is_viral = True

            if is_viral:
                viral_list.append(v)

        return viral_list
