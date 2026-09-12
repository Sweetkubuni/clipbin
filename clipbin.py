#!/usr/bin/env python3
"""
clipbin - a tiny shared "copy space" for text on your local network.

Run it on one computer, then open the printed local URL from any device on
the same Wi-Fi/LAN. Text you paste into a named bin is instantly readable by
everyone else pointed at the same URL - like a shared clipboard / pastebin
that lives in memory.

No dependencies: Python 3.8+ standard library only.

Usage:
    python3 clipbin.py                # serve on port 8000
    python3 clipbin.py 9000           # serve on port 9000
    python3 clipbin.py --port 9000 --save bins.json
"""

import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# In-memory store of bins.  { name: {"text": str, "updated": float} }
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_bins = {}
_save_path = None  # optional JSON file for persistence across restarts


def _now():
    return time.time()


def _load(path):
    global _bins
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            with _lock:
                _bins = {
                    str(k): {
                        "text": str(v.get("text", "")),
                        "updated": float(v.get("updated", _now())),
                    }
                    for k, v in data.items()
                    if isinstance(v, dict)
                }
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[clipbin] could not load {path}: {e}")


def _persist():
    if not _save_path:
        return
    try:
        with _lock:
            snapshot = json.dumps(_bins)
        with open(_save_path, "w", encoding="utf-8") as f:
            f.write(snapshot)
    except Exception as e:
        print(f"[clipbin] could not save {_save_path}: {e}")


def get_bin(name):
    with _lock:
        b = _bins.get(name)
        if b is None:
            return {"name": name, "text": "", "updated": 0.0}
        return {"name": name, "text": b["text"], "updated": b["updated"]}


def set_bin(name, text):
    with _lock:
        _bins[name] = {"text": text, "updated": _now()}
        result = {"name": name, "text": text, "updated": _bins[name]["updated"]}
    _persist()
    return result


def delete_bin(name):
    with _lock:
        existed = name in _bins
        _bins.pop(name, None)
    _persist()
    return existed


def list_bins():
    with _lock:
        return [
            {
                "name": name,
                "updated": b["updated"],
                "size": len(b["text"]),
                "preview": b["text"][:80].replace("\n", " "),
            }
            for name, b in sorted(_bins.items())
        ]


# ---------------------------------------------------------------------------
# Web UI (served at "/").  Plain HTML/JS, works in any modern browser.
# ---------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>clipbin - shared copy space</title>
<style>
  :root {
    --bg:#0f1115; --panel:#171a21; --line:#272c36; --fg:#e6e9ef;
    --muted:#8a92a6; --accent:#4c8bf5; --ok:#3fb950; --danger:#f85149;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#f4f5f7; --panel:#ffffff; --line:#e2e5ea; --fg:#1b1f27;
            --muted:#697086; --accent:#2563eb; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { padding:14px 18px; border-bottom:1px solid var(--line);
           display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; font-weight:600; }
  .grow { flex:1; }
  .wrap { display:flex; min-height:calc(100vh - 55px); }
  aside { width:230px; border-right:1px solid var(--line); padding:12px;
          overflow:auto; }
  main { flex:1; padding:18px; display:flex; flex-direction:column; gap:10px; }
  .binbtn { display:block; width:100%; text-align:left; background:transparent;
            border:1px solid transparent; color:var(--fg); padding:8px 10px;
            border-radius:8px; cursor:pointer; margin-bottom:4px; }
  .binbtn:hover { background:var(--panel); }
  .binbtn.active { background:var(--panel); border-color:var(--accent); }
  .binbtn small { display:block; color:var(--muted); font-size:11px;
                  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  input, textarea, button, select { font:inherit; color:var(--fg); }
  input[type=text] { background:var(--bg); border:1px solid var(--line);
                     border-radius:8px; padding:8px 10px; width:100%; }
  textarea { flex:1; min-height:320px; resize:vertical; background:var(--panel);
             border:1px solid var(--line); border-radius:10px; padding:12px;
             font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
  .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  button.act { background:var(--accent); border:none; color:#fff; padding:9px 14px;
               border-radius:8px; cursor:pointer; font-weight:600; }
  button.ghost { background:transparent; border:1px solid var(--line);
                 padding:9px 12px; border-radius:8px; cursor:pointer; }
  button.ghost:hover { border-color:var(--accent); }
  .status { color:var(--muted); font-size:13px; min-height:18px; }
  .status.saved { color:var(--ok); }
  .pill { font-size:12px; color:var(--muted); }
  code { background:var(--panel); padding:2px 6px; border-radius:6px; }
</style>
</head>
<body>
<header>
  <h1>📋 clipbin</h1>
  <span class="pill">shared copy space on your LAN</span>
  <span class="grow"></span>
  <span class="pill" id="clock"></span>
</header>
<div class="wrap">
  <aside>
    <div class="row" style="margin-bottom:8px">
      <input type="text" id="newbin" placeholder="new bin name…" autocomplete="off">
    </div>
    <button class="ghost" style="width:100%;margin-bottom:12px" id="addbin">+ Create bin</button>
    <div id="binlist"></div>
  </aside>
  <main>
    <div class="row">
      <strong id="binname" style="font-size:16px"></strong>
      <span class="grow"></span>
      <button class="ghost" id="copy">Copy</button>
      <button class="ghost" id="paste">Paste in</button>
      <button class="act" id="save">Save</button>
    </div>
    <textarea id="text" placeholder="Type or paste text here. Anyone on the same bin sees it."></textarea>
    <div class="row">
      <span class="status" id="status"></span>
      <span class="grow"></span>
      <button class="ghost" id="clear">Clear bin</button>
    </div>
  </main>
</div>
<script>
const $ = s => document.querySelector(s);
let current = "default";
let lastServer = "";      // last text known from server
let dirty = false;        // unsaved local edits
let saveTimer = null;

function fmt(ts){ if(!ts) return "empty"; const d=new Date(ts*1000);
  return d.toLocaleTimeString(); }

async function refreshList(){
  const r = await fetch("/api/bins"); const bins = await r.json();
  const names = bins.map(b=>b.name);
  if(!names.includes(current)) names.unshift(current);
  const box = $("#binlist"); box.innerHTML="";
  names.forEach(name=>{
    const meta = bins.find(b=>b.name===name);
    const btn = document.createElement("button");
    btn.className = "binbtn" + (name===current?" active":"");
    btn.innerHTML = `${name}<small>${meta?("updated "+fmt(meta.updated)):"new"}</small>`;
    btn.onclick = ()=>select(name);
    box.appendChild(btn);
  });
}

async function loadCurrent(force){
  const r = await fetch("/api/bin/"+encodeURIComponent(current));
  const b = await r.json();
  // Only overwrite the box if the user isn't in the middle of editing.
  if(force || (!dirty && document.activeElement !== $("#text"))){
    if(b.text !== $("#text").value){
      $("#text").value = b.text;
    }
    lastServer = b.text; dirty = false;
    setStatus("Synced · updated "+fmt(b.updated));
  } else if(b.text !== lastServer){
    setStatus("⚠ someone else changed this bin — Save will overwrite, or reload to see theirs");
  }
}

function setStatus(msg, ok){
  const el = $("#status"); el.textContent = msg;
  el.className = "status" + (ok?" saved":"");
}

async function save(){
  const text = $("#text").value;
  const r = await fetch("/api/bin/"+encodeURIComponent(current), {
    method:"PUT", headers:{"Content-Type":"text/plain; charset=utf-8"}, body:text });
  const b = await r.json();
  lastServer = b.text; dirty = false;
  setStatus("Saved · "+fmt(b.updated), true);
  refreshList();
}

function select(name){
  current = name; $("#binname").textContent = name;
  dirty = false; loadCurrent(true); refreshList();
}

$("#text").addEventListener("input", ()=>{
  dirty = true; setStatus("Editing… (autosaves)");
  clearTimeout(saveTimer); saveTimer = setTimeout(save, 700);
});
$("#save").onclick = save;
$("#clear").onclick = ()=>{ if(confirm("Clear this bin for everyone?")){
  $("#text").value=""; save(); } };
$("#addbin").onclick = ()=>{ const v=$("#newbin").value.trim();
  if(v){ $("#newbin").value=""; select(v); } };
$("#newbin").addEventListener("keydown", e=>{ if(e.key==="Enter") $("#addbin").click(); });

$("#copy").onclick = async ()=>{
  const t = $("#text").value;
  try { await navigator.clipboard.writeText(t); setStatus("Copied to this device's clipboard", true); }
  catch(_) { $("#text").select(); document.execCommand("copy");
             setStatus("Copied (fallback)", true); }
};
$("#paste").onclick = async ()=>{
  try { const t = await navigator.clipboard.readText();
        $("#text").value = t; dirty=true; save(); }
  catch(_) { setStatus("Browser blocked clipboard read — paste manually into the box"); }
};

setInterval(()=>{ $("#clock").textContent = new Date().toLocaleTimeString(); }, 1000);
setInterval(()=>{ loadCurrent(); refreshList(); }, 1500);  // poll for others' changes AND new bins
select("default");
refreshList();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "clipbin/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _bin_name(self):
        # path like /api/bin/<name>
        parts = self.path.split("/", 3)
        return unquote(parts[3]) if len(parts) > 3 and parts[3] else "default"

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = (self.headers.get("Content-Type") or "").lower()
        if "application/json" in ctype:
            try:
                obj = json.loads(raw.decode("utf-8"))
                if isinstance(obj, dict) and "text" in obj:
                    return str(obj["text"])
            except Exception:
                pass
        return raw.decode("utf-8", "replace")

    def do_OPTIONS(self):
        self._send(204, "")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/bins":
            self._send(200, list_bins())
        elif path.startswith("/api/bin/") or path == "/api/bin":
            self._send(200, get_bin(self._bin_name()))
        elif path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def do_PUT(self):
        if self.path.startswith("/api/bin"):
            self._send(200, set_bin(self._bin_name(), self._read_body()))
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        self.do_PUT()

    def do_DELETE(self):
        if self.path.startswith("/api/bin"):
            self._send(200, {"deleted": delete_bin(self._bin_name())})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # quieter logs
        print("[clipbin] %s - %s" % (self.address_string(), fmt % args))


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------
def local_ipv4s():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packets sent; just picks the route
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if "." in ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def main():
    global _save_path
    ap = argparse.ArgumentParser(description="Shared LAN copy space (clipbin).")
    ap.add_argument("port", nargs="?", type=int, default=8000, help="port (default 8000)")
    ap.add_argument("--port", dest="port_opt", type=int, help="port (overrides positional)")
    ap.add_argument("--host", default="0.0.0.0", help="bind address (default all interfaces)")
    ap.add_argument("--save", metavar="FILE", help="persist bins to a JSON file")
    args = ap.parse_args()

    port = args.port_opt or args.port
    if args.save:
        _save_path = args.save
        _load(args.save)

    httpd = ThreadingHTTPServer((args.host, port), Handler)

    # gethostname() may already include the .local suffix (common on macOS),
    # so strip it before re-adding to avoid "host.local.local".
    hostname = socket.gethostname()
    short = hostname[:-6] if hostname.endswith(".local") else hostname
    print("\n  clipbin is running — open a URL below on any device on this network:\n")
    print(f"    this machine :  http://localhost:{port}")
    # <hostname>.local works out-of-the-box on macOS (Bonjour) and most
    # Linux/Windows setups with mDNS enabled — easiest to remember.
    print(f"    friendly URL :  http://{short}.local:{port}")
    for ip in local_ipv4s():
        print(f"    LAN address  :  http://{ip}:{port}")
    print("\n  API:  GET/PUT /api/bin/<name>   ·   GET /api/bins")
    print("  Example:  curl -d 'hello there' http://%s.local:%d/api/bin/default\n" % (short, port))
    if _save_path:
        print(f"  Persisting bins to: {_save_path}\n")
    print("  Press Ctrl+C to stop.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[clipbin] shutting down.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
