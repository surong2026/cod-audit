"""COD 审核系统 — 桌面启动器

双击 .exe 后自动启动 Streamlit 服务器并在浏览器打开。
同事无需安装 Python，直接使用。
"""

import os
import sys
import subprocess
import webbrowser
import threading
import time


def find_app_path() -> str:
    """在 exe 同目录或 _internal 目录下查找 app.py"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    # 先在同目录找
    app = os.path.join(base, "app.py")
    if os.path.exists(app):
        return app

    # 再在 _internal 找
    app = os.path.join(base, "_internal", "app.py")
    if os.path.exists(app):
        return app

    return ""


def main():
    app_path = find_app_path()
    if not app_path:
        print("错误: 找不到 app.py，请确认程序文件完整。")
        input("按回车键退出...")
        sys.exit(1)

    port = 8501
    url = f"http://localhost:{port}"

    # 后台打开浏览器
    def _open_browser():
        time.sleep(3)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"COD 审核系统启动中...")
    print(f"浏览器打开 {url} 即可使用")
    print(f"按 Ctrl+C 停止服务")

    cmd = [
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.enableXsrfProtection", "false",
        "--server.fileWatcherType", "none",
    ]

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
