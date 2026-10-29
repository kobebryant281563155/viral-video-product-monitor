import os
import sys
import json
import time
import subprocess
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    from socketserver import ThreadingMixIn
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
import urllib.parse

# 确保控制台支持 UTF-8
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PORT = 8768
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
MATERIALS_DIR = BASE_DIR / "materials"

CURRENT_PROCESS = None
CURRENT_TASK_TYPE = None
LOG_BUFFER = []
MAX_LOGS = 500

def append_log(line: str):
    global LOG_BUFFER
    timestamp = time.strftime("[%H:%M:%S] ")
    LOG_BUFFER.append(timestamp + line.strip())
    if len(LOG_BUFFER) > MAX_LOGS:
        LOG_BUFFER = LOG_BUFFER[-MAX_LOGS:]

class ViralMonitorWebHandler(SimpleHTTPRequestHandler):
    """爆款监控与电商选品轻量后端 API"""

    def __init__(self, *args, **kwargs):
        web_dir = str(Path(__file__).resolve().parent)
        super().__init__(*args, directory=web_dir, **kwargs)

    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. 获取短视频监控配置
        if path == "/api/video/config":
            cfg_file = CONFIG_DIR / "competitors.json"
            if cfg_file.exists():
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        self._send_json({"code": 0, "data": json.load(f)})
                        return
                except Exception as e:
                    self._send_json({"code": -1, "msg": str(e)}, 500)
                    return
            self._send_json({"code": -1, "msg": "competitors.json 不存在"}, 404)
            return

        # 2. 获取电商监控配置
        elif path == "/api/ecom/config":
            cfg_file = CONFIG_DIR / "ecommerce.json"
            if cfg_file.exists():
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        self._send_json({"code": 0, "data": json.load(f)})
                        return
                except Exception as e:
                    self._send_json({"code": -1, "msg": str(e)}, 500)
                    return
            self._send_json({"code": -1, "msg": "ecommerce.json 不存在"}, 404)
            return

        # 3. 获取任务状态与实时日志
        elif path == "/api/task/status":
            global CURRENT_PROCESS, CURRENT_TASK_TYPE, LOG_BUFFER
            is_running = False
            if CURRENT_PROCESS is not None:
                poll = CURRENT_PROCESS.poll()
                is_running = (poll is None)
                if not is_running:
                    CURRENT_PROCESS = None
                    CURRENT_TASK_TYPE = None

            self._send_json({
                "code": 0,
                "running": is_running,
                "task_type": CURRENT_TASK_TYPE,
                "logs": LOG_BUFFER
            })
            return

        # 静态文件正常处理 (index.html, css, js)
        super().do_GET()

    def do_POST(self):
        global CURRENT_PROCESS, CURRENT_TASK_TYPE, LOG_BUFFER
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            req_data = {}

        # 1. 保存短视频配置
        if path == "/api/video/config":
            cfg_file = CONFIG_DIR / "competitors.json"
            try:
                with open(cfg_file, "w", encoding="utf-8") as f:
                    json.dump(req_data, f, ensure_ascii=False, indent=2)
                self._send_json({"code": 0, "msg": "短视频配置已成功保存！"})
            except Exception as e:
                self._send_json({"code": -1, "msg": f"保存失败: {e}"}, 500)
            return

        # 2. 保存电商配置
        elif path == "/api/ecom/config":
            cfg_file = CONFIG_DIR / "ecommerce.json"
            try:
                with open(cfg_file, "w", encoding="utf-8") as f:
                    json.dump(req_data, f, ensure_ascii=False, indent=2)
                self._send_json({"code": 0, "msg": "电商配置已成功保存！"})
            except Exception as e:
                self._send_json({"code": -1, "msg": f"保存失败: {e}"}, 500)
            return

        # 3. 启动任务
        elif path == "/api/task/start":
            if CURRENT_PROCESS is not None and CURRENT_PROCESS.poll() is None:
                self._send_json({"code": -1, "msg": f"任务已在运行中 ({CURRENT_TASK_TYPE})"})
                return

            task_type = req_data.get("task_type", "video")  # "video" 或 "ecom"
            LOG_BUFFER = []
            append_log(f"=== 正在启动任务: {'短视频爆款监控' if task_type == 'video' else '电商爆款选品抓取'} ===")

            script_name = "main.py" if task_type == "video" else "main_ecommerce.py"
            py_exe = sys.executable
            if not getattr(sys, "frozen", False):
                for cand in [sys.executable, r"C:\Users\Jackie-Zhang\anaconda3\python.exe"]:
                    if os.path.exists(cand):
                        py_exe = cand
                        break

            cmd = [py_exe, script_name]

            def run_worker():
                global CURRENT_PROCESS
                try:
                    CURRENT_PROCESS = subprocess.Popen(
                        cmd,
                        cwd=str(BASE_DIR),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1
                    )
                    for line in CURRENT_PROCESS.stdout:
                        if line:
                            append_log(line)
                    CURRENT_PROCESS.wait()
                    append_log("=== 任务执行结束 ===")
                except Exception as err:
                    append_log(f"[异常终止] {err}")

            CURRENT_TASK_TYPE = task_type
            threading.Thread(target=run_worker, daemon=True).start()
            self._send_json({"code": 0, "msg": "任务启动成功！", "task_type": task_type})
            return

        # 4. 停止任务
        elif path == "/api/task/stop":
            if CURRENT_PROCESS is not None and CURRENT_PROCESS.poll() is None:
                try:
                    CURRENT_PROCESS.terminate()
                    time.sleep(0.5)
                    if CURRENT_PROCESS.poll() is None:
                        CURRENT_PROCESS.kill()
                    append_log(">>> 用户已手动中止任务。")
                except Exception as e:
                    append_log(f">>> 中止任务异常: {e}")
                CURRENT_PROCESS = None
                CURRENT_TASK_TYPE = None
                self._send_json({"code": 0, "msg": "任务已停止"})
            else:
                self._send_json({"code": 0, "msg": "当前没有正在运行的任务"})
            return

        # 5. 打开文件夹 / 打开 Excel
        elif path == "/api/open_folder":
            target = req_data.get("target", "video_folder")
            try:
                if target == "video_folder":
                    p = MATERIALS_DIR / "viral_competitors"
                    os.makedirs(p, exist_ok=True)
                    subprocess.Popen(f'explorer "{p}"', shell=True)
                elif target == "ecom_folder":
                    p = MATERIALS_DIR / "ecommerce_products"
                    os.makedirs(p, exist_ok=True)
                    subprocess.Popen(f'explorer "{p}"', shell=True)
                elif target == "excel_file":
                    p = MATERIALS_DIR / "ecommerce_products" / "爆款选品汇总.xlsx"
                    if p.exists():
                        subprocess.Popen(f'start "" "{p}"', shell=True)
                    else:
                        self._send_json({"code": -1, "msg": "选品汇总表格尚未生成，请先执行一次电商采集！"})
                        return
                self._send_json({"code": 0, "msg": "已唤起打开！"})
            except Exception as e:
                self._send_json({"code": -1, "msg": f"唤起失败: {e}"}, 500)
            return

        self._send_json({"code": -1, "msg": "未知接口"}, 404)

def run_server():
    server_address = ("0.0.0.0", PORT)
    try:
        ThreadingHTTPServer.allow_reuse_address = True
        httpd = ThreadingHTTPServer(server_address, ViralMonitorWebHandler)
    except OSError as e:
        if "10048" in str(e) or "Address already in use" in str(e):
            print(f"[提示] 检测到端口 {PORT} 监控服务已在后台运行中: http://127.0.0.1:{PORT}/")
            return
        raise e

    print(f"[SUCCESS] 全网爆款监控与电商选品 Web 服务启动在: http://127.0.0.1:{PORT}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] 服务已退出。")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
