#!/usr/bin/env python3
"""Run Next.js frontend and FastAPI backend locally (not SAM)."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
processes = []


def cleanup(signum=None, frame=None):
    print("\nShutting down services...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def check_requirements():
    for cmd, label in [("node", "Node.js"), ("npm", "npm"), ("uv", "uv")]:
        try:
            subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                check=True,
                shell=IS_WINDOWS and cmd == "npm",
            )
            print(f"  {label}: ok")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print(f"  Missing {label}")
            sys.exit(1)


def check_env_files():
    root = Path(__file__).parent.parent
    missing = []
    if not (root / ".env").exists():
        missing.append(".env")
    if not (root / "frontend" / ".env.local").exists():
        missing.append("frontend/.env.local")
    if missing:
        print("Missing env files:", ", ".join(missing))
        sys.exit(1)


def start_backend():
    backend_dir = Path(__file__).parent.parent / "backend" / "api"
    print("Starting FastAPI backend...")
    proc = subprocess.Popen(
        ["uv", "run", "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    processes.append(proc)
    import httpx

    for _ in range(30):
        try:
            if httpx.get("http://localhost:8000/health", timeout=1).status_code == 200:
                print("  Backend http://localhost:8000  docs: /docs")
                return
        except Exception:
            time.sleep(1)
    print("Backend failed to start")
    cleanup()


def start_frontend():
    frontend_dir = Path(__file__).parent.parent / "frontend"
    print("Starting Next.js frontend...")
    if not (frontend_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True, shell=IS_WINDOWS)
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=IS_WINDOWS,
    )
    processes.append(proc)
    import httpx

    for _ in range(40):
        try:
            httpx.get("http://localhost:3000", timeout=1)
            print("  Frontend http://localhost:3000")
            return
        except Exception:
            time.sleep(1)
    print("Frontend failed to start")
    cleanup()


def main():
    print("Alex SAM — local app (FastAPI + Next.js)")
    check_requirements()
    check_env_files()
    try:
        import httpx  # noqa: F401
    except ImportError:
        subprocess.run(["uv", "add", "httpx"], cwd=Path(__file__).parent, check=True)
    start_backend()
    start_frontend()
    print("Press Ctrl+C to stop.")
    while True:
        for proc in processes:
            if proc.poll() is not None:
                print("A process exited")
                cleanup()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
