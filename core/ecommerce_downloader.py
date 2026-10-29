import os
import re
import json
import time
import requests
from typing import Dict, Any, List, Optional
from core.ecommerce_utils import sanitize_product_title

class EcommerceDownloader:
    """电商多媒体素材下载引擎 (主图包、商品视频、详情页长图)"""

    def __init__(self, base_dir: str = "materials/ecommerce_products"):
        self.base_dir = base_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        os.makedirs(self.base_dir, exist_ok=True)

    def download_product_materials(self, product: Dict[str, Any], download_images: bool = True, download_videos: bool = True) -> str:
        """为单个商品建立专属素材文件夹并下载对应媒体文件"""
        p_name = product.get("platform_name", "电商")
        sales = product.get("sales", 0)
        title = product.get("title", "product")
        safe_title = sanitize_product_title(title, max_length=25)

        # 文件夹规范: [平台]_[销量件]_[商品名]
        dir_name = f"[{p_name}]_[{sales}件]_{safe_title}"
        product_folder = os.path.join(self.base_dir, dir_name)
        os.makedirs(product_folder, exist_ok=True)

        # 1. 保存商品元数据 JSON
        info_json = os.path.join(product_folder, "商品详情.json")
        try:
            with open(info_json, "w", encoding="utf-8") as f:
                json.dump(product, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 2. 下载主图 / 轮播图片
        image_urls = product.get("images", [])
        if download_images and image_urls:
            img_dir = os.path.join(product_folder, "主图轮播包")
            os.makedirs(img_dir, exist_ok=True)
            for idx, img_url in enumerate(image_urls[:8], start=1):
                try:
                    if not img_url.startswith("http"):
                        img_url = "https:" + img_url if img_url.startswith("//") else img_url
                    ext = ".jpg"
                    if ".png" in img_url.lower():
                        ext = ".png"
                    save_img = os.path.join(img_dir, f"主图_{idx}{ext}")
                    if not os.path.exists(save_img):
                        resp = self.session.get(img_url, timeout=12)
                        if resp.status_code == 200 and len(resp.content) > 1024:
                            with open(save_img, "wb") as f:
                                f.write(resp.content)
                except Exception:
                    pass

        # 3. 下载商品视频 / 带货视频
        video_url = product.get("video_url")
        if download_videos and video_url and video_url.startswith("http"):
            try:
                vid_path = os.path.join(product_folder, "商品主图带货视频.mp4")
                if not os.path.exists(vid_path):
                    resp = self.session.get(video_url, stream=True, timeout=25)
                    if resp.status_code == 200:
                        with open(vid_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                        if os.path.exists(vid_path) and os.path.getsize(vid_path) < 10240:
                            os.remove(vid_path)
            except Exception:
                pass

        return product_folder
