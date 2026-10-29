# TikTok 竞品主页爆款监控与无水印自动下载系统

一套轻量、稳定、抗风控的自动化短视频监控下载工具。

---

## 核心特性

1. **AdsPower 海外指纹浏览器环境复用**：通过 CDP 端口连接干净的海外独立环境，解决原生 IP 封锁与滑块验证码风控。
2. **网络层 API 数据拦截**：基于 Playwright 监听 TikTok 官方数据包，准确获取真实**点赞数（diggCount）**、**播放量（playCount）** 与**发布时间**，彻底避开前端网格卡片混淆和 DOM 改版失效。
3. **精准爆款筛选模型**：
   - 支持设置点赞门槛（如 `>= 10,000` 赞）；
   - 支持时效性过滤（默认近 30 天内发布，自动剔除陈旧视频）；
   - 自动跳过置顶（Pinned）门面视频。
4. **无水印多源下载引擎**：
   - 优先原画直链提取，备用 TikWM 高清解析；
   - 自动清洗 Windows 非法文件名字符（Emoji、标点过滤）；
   - 同步保存包含标题、文案、标签、BGM 和互动数据的同名 `.json` 元数据文件。
5. **本地去重历史库**：基于 `data/viral_history.json` 自动排重，避免重复下载浪费流量。
6. **一键双击运行**：提供 `run_competitor_monitor.bat`，运行完毕后自动打开素材下载文件夹。

---

## 目录结构

```text
├── config/
│   └── competitors.json         # 监控账号、爆款过滤阈值与配置
├── core/
│   ├── competitor_monitor.py    # 巡检主调度控制器
│   ├── tiktok_inspector.py      # CDP 网络监听与卡片解析引擎
│   ├── downloader.py            # 无水印视频下载器 (带文件名清洗与元数据留存)
│   ├── history_manager.py       # 本地已下载去重历史库
│   └── utils.py                 # 数值换算(12.5K/1.2M)与时效工具
├── data/
│   └── viral_history.json       # 历史下载去重记录
├── materials/
│   └── viral_competitors/       # 无水印高清原片与伴生文案保存目录
├── main.py                      # 命令行执行主入口
├── run_competitor_monitor.bat   # 桌面双击一键运行批处理
├── test_suite.py                # 自动化测试脚本
└── requirements.txt             # Python 依赖清单
```

---

## 快速上手

### 1. 修改监控博主主页
打开 `config/competitors.json`，在 `creators` 中填入你想监控的同行账号：
```json
"creators": [
  { "name": "同行A_重磅毛衫", "url": "https://www.tiktok.com/@tiktok" },
  { "name": "同行B_老钱穿搭", "url": "https://www.tiktok.com/@competitor_2" }
]
```

### 2. 启动 AdsPower
确保 AdsPower 处于打开状态，并开启对应的海外代理指纹窗口（默认 CDP 端口为 `127.0.0.1:65209`）。

### 3. 一键启动监控
直接双击运行根目录下的 **`run_competitor_monitor.bat`**：
* 终端将打印每位博主的巡检进度与爆款识别日志；
* 自动下载符合条件的无水印视频至 `materials/viral_competitors/`；
* 巡检完成后，系统会自动弹窗打开素材文件夹。

---

## 高级命令

如果需要通过命令行执行更细粒度的控制：

```bash
# 1. 运行单次巡检（默认）
python main.py --mode once

# 2. 运行后台定时轮询（每 4 小时巡检一次）
python main.py --mode daemon --hours 4

# 3. 运行基础组件单测
python test_suite.py
```
