#!/usr/bin/env python3
"""
run.py - one command to start clipbin on macOS, Linux, or Windows.

It supervises the two pieces:
  * the clipbin server   (network service - shares text bins on your LAN)
  * the clipsync watcher (mirrors a bin into THIS machine's clipboard)

Examples:
    python run.py                     # start server + clipboard watcher (default)
    python run.py server              # only the server (e.g. on a headless box)
    python run.py watch               # only the clipboard watcher (server elsewhere)
    python run.py --port 9000         # use a different port
    python run.py watch --url http://192.168.0.237:8000 --bin notes

Press Ctrl+C once to stop everything cleanly.
No third-party dependencies - just Python 3.8+.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"


def wait_healthy(url, timeout=15.0):
    """Block until the server answers, or timeout."""
    deadline = time.time() + timeout
    health = url.rstrip("/") + "/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def spawn(script, extra):
    return subprocess.Popen([PY, "-u", os.path.join(HERE, script), *extra])


def stop(procs):
    for p in procs:
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
    # give them a moment, then hard-kill anything still alive
    deadline = time.time() + 5
    for p in procs:
        if not p:
            continue
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description="Run clipbin (server + clipboard watcher).")
    ap.add_argument("mode", nargs="?", default="both",
                    choices=["both", "server", "watch"],
                    help="what to run (default: both)")
    ap.add_argument("--port", type=int, default=8000, help="server port (default 8000)")
    ap.add_argument("--host", default="0.0.0.0", help="server bind address")
    ap.add_argument("--bin", default="default", help="bin to mirror to the clipboard")
    ap.add_argument("--interval", type=float, default=1.0, help="watcher poll seconds")
    ap.add_argument("--save", default="bins.json",
                    help="server persistence file ('none' to disable)")
    ap.add_argument("--url", default=None,
                    help="server URL for the watcher (default http://localhost:<port>)")
    args = ap.parse_args()

    # Make SIGTERM (what `kill` and service managers send) behave like Ctrl+C,
    # so children are always cleaned up instead of orphaned.
    def _term(signum, frame):
        raise KeyboardInterrupt
    for _sig in ("SIGTERM", "SIGHUP"):
        s = getattr(signal, _sig, None)
        if s is not None:
            try:
                signal.signal(s, _term)
            except (ValueError, OSError):
                pass  # not available on this platform / thread

    watch_url = args.url or f"http://localhost:{args.port}"

    server_args = [str(args.port), "--host", args.host]
    if args.save and args.save.lower() != "none":
        server_args += ["--save", args.save]
    watch_args = ["--url", watch_url, "--bin", args.bin, "--interval", str(args.interval)]

    procs = []
    try:
        if args.mode in ("both", "server"):
            print(f"[run] starting server on {args.host}:{args.port} …")
            procs.append(spawn("clipbin.py", server_args))

        if args.mode == "both":
            if not wait_healthy(watch_url):
                print("[run] server did not become healthy in time — stopping.")
                stop(procs)
                return 1
            print("[run] server is up.")

        if args.mode in ("both", "watch"):
            if args.mode == "watch" and not wait_healthy(watch_url, timeout=5):
                print(f"[run] warning: can't reach a server at {watch_url} yet — "
                      "the watcher will keep retrying.")
            print(f"[run] starting clipboard watcher on bin '{args.bin}' …")
            procs.append(spawn("clipsync.py", watch_args))

        print("[run] running. Press Ctrl+C to stop.\n")

        # Supervise: if any child dies, take the rest down too.
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"[run] a process exited (code {p.returncode}) — shutting down.")
                    stop(procs)
                    return p.returncode or 0
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[run] stopping …")
        stop(procs)
        return 0


if __name__ == "__main__":
    sys.exit(main())
