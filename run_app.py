"""COD 审核系统 — 桌面启动器

双击 .exe 后自动启动 Streamlit 服务器并在浏览器打开。
同事无需安装 Python，直接使用。
"""

import os
import sys
import tempfile
import time
import threading
import webbrowser

LOG_FILE = os.path.join(tempfile.gettempdir(), "cod_audit_launcher.log")
LOCK_FILE = os.path.join(tempfile.gettempdir(), "cod_audit_streamlit.lock")
PORT = 8501
URL = f"http://localhost:{PORT}"


def log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def find_app_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    app = os.path.join(base, "app.py")
    if os.path.exists(app):
        log(f"找到 app.py: {app}")
        return app
    app = os.path.join(base, "_internal", "app.py")
    if os.path.exists(app):
        log(f"找到 app.py (_internal): {app}")
        return app

    log(f"错误: 找不到 app.py, base={base}")
    if os.path.isdir(base):
        log(f"base 目录内容: {os.listdir(base)}")
    return ""


def lock_owner_alive() -> bool:
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    log("=== COD 审核系统启动 ===")

    app_path = find_app_path()
    if not app_path:
        input("错误: 找不到 app.py, 按回车键退出...")
        sys.exit(1)

    # 已有实例运行 → 只打开浏览器
    if lock_owner_alive():
        log("已有实例在运行，打开浏览器")
        webbrowser.open(URL)
        return

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        # 后台等几秒后打开浏览器
        def _open():
            time.sleep(4)
            webbrowser.open(URL)

        threading.Thread(target=_open, daemon=True).start()

        log("启动 Streamlit...")

        # 直接在进程内启动 Streamlit，不用子进程
        sys.argv = [
            "streamlit", "run", app_path,
            "--server.port", str(PORT),
            "--server.address", "127.0.0.1",
            "--server.headless", "true",
            "--global.developmentMode", "false",
            "--browser.gatherUsageStats", "false",
            "--server.enableXsrfProtection", "false",
            "--server.fileWatcherType", "none",
        ]
        from streamlit.web.cli import main as stcli_main
        stcli_main()

    except Exception:
        import traceback
        log(traceback.format_exc())
        input("发生错误，按回车键退出...")
        sys.exit(1)
    finally:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
