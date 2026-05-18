"""COD 审核系统 — 桌面启动器

双击 .exe 后自动启动 Streamlit 服务器并在浏览器打开。
同事无需安装 Python，直接使用。
"""

import os
import sys
import subprocess
import webbrowser
import tempfile
import time

LOCK_FILE = os.path.join(tempfile.gettempdir(), "cod_audit_streamlit.lock")
PORT = 8501
URL = f"http://localhost:{PORT}"


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


def lock_owner_alive() -> bool:
    """检查锁文件中记录的 PID 是否还在运行"""
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


def acquire_lock() -> bool:
    """尝试获取锁，返回 True 表示成功获取（需要启动服务）"""
    if lock_owner_alive():
        return False
    # 清理可能的残留锁文件
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass


def main():
    app_path = find_app_path()
    if not app_path:
        print("错误: 找不到 app.py，请确认程序文件完整。")
        input("按回车键退出...")
        sys.exit(1)

    # 检查是否已有实例在运行
    if not acquire_lock():
        print("COD 审核系统已在运行，打开浏览器...")
        webbrowser.open(URL)
        return

    try:
        print("COD 审核系统启动中...")
        print(f"启动完成后浏览器将打开 {URL}")

        cmd = [
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.port", str(PORT),
            "--server.address", "127.0.0.1",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.enableXsrfProtection", "false",
            "--server.fileWatcherType", "none",
        ]

        p = subprocess.Popen(cmd)
        time.sleep(5)

        # 检查 Streamlit 是否成功启动（进程还活着）
        if p.poll() is not None:
            print(f"错误: Streamlit 启动失败 (退出码 {p.returncode})")
            print("请确认杀毒软件没有拦截，或联系管理员。")
            input("按回车键退出...")
            sys.exit(1)

        webbrowser.open(URL)
        print(f"服务运行中 → {URL}")
        print("关闭本窗口即可停止服务。")
        p.wait()
    finally:
        release_lock()


if __name__ == "__main__":
    main()
