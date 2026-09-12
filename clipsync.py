#!/usr/bin/env python3
"""
clipsync - mirror a clipbin bin into THIS computer's system clipboard.

Watches a clipbin server's bin (default: the bin named "default") and, whenever
its contents change, copies the text into your local clipboard so you can paste
it anywhere with Cmd+V / right-click > Paste.

One-way:  clipbin bin  ->  your clipboard.

It only pushes when the bin gets a NEW write (it tracks the bin's "updated"
timestamp), so it will not stomp on something you just copied locally unless a
fresh update actually arrives in the bin.

Usage:
    python3 clipsync.py                         # watch default bin on localhost:8000
    python3 clipsync.py --bin notes             # watch a different bin
    python3 clipsync.py --url http://zaddle64.local:8000
    python3 clipsync.py --interval 0.5          # poll faster
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.request


def clipboard_command():
    """Pick the right 'write to clipboard' command for this OS."""
    system = platform.system()
    if system == "Darwin" and shutil.which("pbcopy"):
        return ["pbcopy"]
    if system == "Windows":
        return ["clip"]
    # Linux / *BSD: try Wayland then X11 tools
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


def set_clipboard(cmd, text):
    try:
        p = subprocess.run(cmd, input=text.encode("utf-8"))
        return p.returncode == 0
    except Exception as e:
        print(f"[clipsync] clipboard write failed: {e}")
        return False


def fetch(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description="Mirror a clipbin bin into your clipboard.")
    ap.add_argument("--url", default="http://localhost:8000", help="clipbin server URL")
    ap.add_argument("--bin", default="default", help="bin name to watch")
    ap.add_argument("--interval", type=float, default=1.0, help="poll seconds (default 1.0)")
    ap.add_argument("--allow-empty", action="store_true",
                    help="also copy when the bin is cleared to empty (default: skip)")
    args = ap.parse_args()

    cmd = clipboard_command()
    if not cmd:
        print("[clipsync] No clipboard tool found "
              "(need pbcopy / wl-copy / xclip / xsel / clip).")
        sys.exit(1)

    endpoint = args.url.rstrip("/") + "/api/bin/" + args.bin
    print(f"[clipsync] watching  {endpoint}")
    print(f"[clipsync] copying into clipboard via: {' '.join(cmd)}")
    print("[clipsync] Ctrl+C to stop.\n")

    last_updated = None
    while True:
        try:
            b = fetch(endpoint)
            upd = b.get("updated", 0)
            text = b.get("text", "")
            if upd != last_updated:
                if text == "" and not args.allow_empty:
                    last_updated = upd  # note it, but don't wipe the clipboard
                elif set_clipboard(cmd, text):
                    last_updated = upd
                    preview = text[:60].replace("\n", " ")
                    print(f"[clipsync] copied {len(text)} chars -> clipboard: {preview!r}")
        except urllib.error.URLError as e:
            print(f"[clipsync] can't reach server ({e}); retrying…")
        except Exception as e:
            print(f"[clipsync] warn: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
