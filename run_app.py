"""COD 审核系统 — 桌面启动器

双击 .exe 后自动启动 Streamlit 服务器并在浏览器打开。
同事无需安装 Python，直接使用。
"""

import os
import sys
import subprocess
import webbrowser
import socket
import time


def find_app_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    app = os.path.join(base, "app.py")
    if os.path.exists(app):
        return app
    app = os.path.join(base, "_internal", "app.py")
    if os.path.exists(app):
        return app
    return ""


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def main():
    app_path = find_app_path()
    if not app_path:
        print("错误: 找不到 app.py，请确认程序文件完整。")
        input("按回车键退出...")
        sys.exit(1)

    port = 8501
    url = f"http://localhost:{port}"

    if port_in_use(port):
        print("Streamlit 已在运行，直接打开浏览器...")
        webbrowser.open(url)
        return

    print("COD 审核系统启动中...")
    print(f"浏览器打开 {url} 即可使用")

    cmd = [
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.enableXsrfProtection", "false",
        "--server.fileWatcherType", "none",
    ]

    p = subprocess.Popen(cmd)
    time.sleep(3)
    webbrowser.open(url)
    p.wait()


if __name__ == "__main__":
    main()
