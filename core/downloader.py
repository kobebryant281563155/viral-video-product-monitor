import os
import re
import json
import time
import requests
from typing import Dict, Any, Optional

def sanitize_filename(name: str, max_length: int = 50) -> str:
    """清洗 Windows 非法字符，截断长度，防止路径错误"""
    clean = re.sub(r'[\\/*?:"<>|\r\n\t]', "_", name)
    clean = clean.strip(". ")
    if not clean:
        clean = "video"
    return clean[:max_length]

class MultiPlatformDownloader:
    """四大平台 (TikTok / 抖音 / 小红书 / Instagram) 无水印视频下载核心引擎"""

    def __init__(self, download_dir: str = "materials/viral_competitors", save_metadata: bool = True):
        self.download_dir = download_dir
        self.save_metadata = save_metadata
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        os.makedirs(self.download_dir, exist_ok=True)

    def resolve_no_watermark_url(self, platform: str, video_url: str, direct_url: Optional[str] = None) -> Optional[str]:
        """按平台策略智能提取无水印原画直链"""
        # 1. 如果已有直链且有效
        if direct_url and direct_url.startswith("http"):
            # 抖音去水印逻辑：如果链接含 playwm，替换为 play 即为纯净无水印直链
            if "douyin" in platform or "douyin.com" in direct_url:
                direct_url = direct_url.replace("playwm", "play")
            return direct_url

        # 2. 根据不同平台采用专业多源解析策略
        if platform == "tiktok":
            return self._resolve_tiktok(video_url)
        elif platform == "douyin":
            return self._resolve_douyin(video_url)
        elif platform == "xhs":
            return self._resolve_xhs(video_url)
        elif platform == "instagram":
            return self._resolve_instagram(video_url)
        
        # 兜底尝试多平台解析
        return self._resolve_tiktok(video_url) or self._resolve_douyin(video_url)

    def _resolve_tiktok(self, video_url: str) -> Optional[str]:
        """TikTok 无水印解析"""
        try:
            resp = self.session.post("https://www.tikwm.com/api/", data={"url": video_url, "hd": 1}, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return data.get("hdplay") or data.get("play")
        except Exception:
            pass
        return None

    def _resolve_douyin(self, video_url: str) -> Optional[str]:
        """抖音无水印解析"""
        try:
            # 方案1: 提取抖音真实 ID 并请求移动端无水印接口
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
            }
            resp = self.session.get(video_url, headers=headers, allow_redirects=True, timeout=10)
            final_url = resp.url
            # 从重定向后的链接中提取视频 ID
            match = re.search(r"/video/(\d+)", final_url)
            if match:
                item_id = match.group(1)
                api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={item_id}"
                api_resp = self.session.get(api_url, headers=headers, timeout=10)
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    item_list = data.get("item_list", [])
                    if item_list:
                        play_addr = item_list[0].get("video", {}).get("play_addr", {}).get("url_list", [])
                        if play_addr:
                            # 替换 playwm 为 play 即为官方无水印地址
                            return play_addr[0].replace("playwm", "play")
        except Exception:
            pass

        # 方案2: 备用通用第三方解析
        try:
            resp = self.session.get(f"https://api.douyin.wtf/douyin/video?url={video_url}", timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("video_data", {}).get("nwm_video_url_1080p") or data.get("video_data", {}).get("nwm_video_url")
        except Exception:
            pass
        return None

    def _resolve_xhs(self, video_url: str) -> Optional[str]:
        """小红书视频原画解析（小红书 CDN 视频本身无水印）"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = self.session.get(video_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                # 在 HTML 源码中查找 xhscdn 视频地址
                m = re.search(r'https?://[a-zA-Z0-9\.-]*xhscdn\.com/[a-zA-Z0-9_\-\.\/]+\.mp4', resp.text)
                if m:
                    return m.group(0)
        except Exception:
            pass
        return None

    def _resolve_instagram(self, video_url: str) -> Optional[str]:
        """Instagram Reels / 视频无水印解析"""
        try:
            # 尝试通过公开提取服务提取 Instagram 视频直链
            api_url = f"https://api.vkrdown.com/api/instagram?url={video_url}"
            resp = self.session.get(api_url, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    return data["data"][0].get("url")
        except Exception:
            pass
        return None

    def download_video(self, video_info: Dict[str, Any]) -> Optional[str]:
        """
        跨平台下载视频核心逻辑
        video_info 包含:
          - id: 视频ID
          - platform: 平台标识 (tiktok / douyin / xhs / instagram)
          - url: 视频网页URL
          - creator: 博主名称
          - title: 视频标题/描述
          - likes: 点赞数
          - views: 播放数
          - direct_download_url: 原生抓取到的直链
        """
        platform = video_info.get("platform", "unknown")
        platform_labels = {
            "douyin": "抖音",
            "xhs": "小红书",
            "tiktok": "TikTok",
            "instagram": "Instagram",
            "unknown": "视频"
        }
        platform_name = platform_labels.get(platform, platform)
        video_id = str(video_info.get("id"))
        creator = sanitize_filename(str(video_info.get("creator", "creator")), max_length=20)
        likes = video_info.get("likes", 0)
        title_raw = video_info.get("title", "") or f"video_{video_id}"
        safe_title = sanitize_filename(title_raw, max_length=25)

        # 规范命名: [平台]_[点赞数赞]_[博主名]_[标题前25字].mp4
        filename = f"[{platform_name}]_[{likes}赞]_{creator}_{safe_title}.mp4"
        save_path = os.path.join(self.download_dir, filename)

        if len(save_path) > 240:
            filename = f"[{platform_name}]_[{likes}赞]_{creator}_{video_id}.mp4"
            save_path = os.path.join(self.download_dir, filename)

        web_url = video_info.get("url", "")
        direct_url = video_info.get("direct_download_url")
        print(f"[INFO] 正在解析【{platform_name}】无水印直链: {web_url or video_id}...")

        play_url = self.resolve_no_watermark_url(platform, web_url, direct_url)
        if not play_url:
            print(f"[ERROR] 无法解析无水印直链，跳过视频: {video_id}")
            return None

        print(f"[INFO] 开始下载无水印视频: {filename}")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            if "douyin" in platform:
                headers["Referer"] = "https://www.douyin.com/"
            elif "tiktok" in platform:
                headers["Referer"] = "https://www.tiktok.com/"
            elif "xhs" in platform:
                headers["Referer"] = "https://www.xiaohongshu.com/"
            elif "instagram" in platform:
                headers["Referer"] = "https://www.instagram.com/"

            resp = self.session.get(play_url, stream=True, headers=headers, timeout=30)
            resp.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)

            file_size_mb = os.path.getsize(save_path) / (1024 * 1024)
            if file_size_mb < 0.1:
                print(f"[ERROR] 下载文件过小 ({file_size_mb:.2f} MB)，可能链接失效，已删除。")
                if os.path.exists(save_path):
                    os.remove(save_path)
                return None

            print(f"[SUCCESS] 【{platform_name}】无水印视频下载完成: {filename} ({file_size_mb:.2f} MB)")

            if self.save_metadata:
                meta_path = os.path.splitext(save_path)[0] + ".json"
                try:
                    with open(meta_path, "w", encoding="utf-8") as mf:
                        json.dump(video_info, mf, ensure_ascii=False, indent=2)
                except Exception as me:
                    print(f"[WARN] 伴生元数据保存失败: {me}")

            return save_path

        except Exception as e:
            print(f"[ERROR] 下载失败: {e}")
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            return None

# 保持对旧类名的兼容
VideoDownloader = MultiPlatformDownloader
