"""启动 Celery Worker（后台持久运行）。"""
import os, subprocess, sys

env = os.environ.copy()
env["PYTHONPATH"] = "d:/企业文档智能问答平台/backend"
proc = subprocess.Popen(
    [sys.executable, "-m", "celery", "-A", "tasks.celery_app", "worker", "-l", "info", "-P", "solo"],
    cwd=r"d:\企业文档智能问答平台\backend",
    env=env,
)
print(f"Celery PID: {proc.pid}")
proc.wait()
