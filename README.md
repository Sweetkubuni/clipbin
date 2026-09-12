# clipbin

A tiny **shared copy space** for text on your local network — like a self-hosted,
in-memory pastebin/clipboard that devices on the same Wi‑Fi share through a simple
local URL. Paste text on your laptop, read it on your phone; or have a named bin
mirror itself straight into your computer's system clipboard.

- **Zero dependencies** — pure Python 3.8+ standard library.
- **Two small pieces:**
  - **`clipbin.py`** — the server. Holds named *bins* of text and serves a web UI + JSON API.
  - **`clipsync.py`** — an optional watcher that mirrors one bin into *this* machine's clipboard (⌘V / Ctrl‑V).
- **Runs on macOS, Linux, and Windows.**

---

## Quick start

You need Python 3.8+ installed (`python3 --version`).

**macOS / Linux**
```bash
./run.sh
```

**Windows (PowerShell)**
```powershell
.\run.ps1
```

**Windows (Command Prompt)**
```bat
run.bat
```

**Any platform, directly**
```bash
python run.py
```

That starts the **server** and the **clipboard watcher** together. On startup the
server prints the URLs to open from other devices, e.g.:

```
    this machine :  http://localhost:8000
    friendly URL :  http://your-hostname.local:8000
    LAN address  :  http://192.168.0.237:8000
```

Open any of those in a browser on another device on the same network. Press
**Ctrl+C** once to stop everything.

---

## How it works

`clipbin` stores **bins** — named slots of text. The web UI shows one bin at a
time (it opens on the bin called `default`); the sidebar lists all bins and
refreshes automatically as new ones appear.

- Write to a bin → everyone viewing that bin sees the update within ~1.5s.
- The optional **clipsync** watcher polls one bin and, whenever it gets a *new*
  write, copies the text into your OS clipboard so you can paste it anywhere.

The clipboard sync is **one-way**: `bin → your clipboard`. It only pushes on a
genuinely new write (it tracks the bin's `updated` timestamp), so it won't stomp
on something you just copied locally unless fresh text actually arrives.

---

## Using it

### Web UI
Open the printed URL. Type or paste into a bin, use **Copy** / **Paste in** to
move text between the bin and the browser device's clipboard, create new bins from
the sidebar. Edits autosave.

### HTTP API
| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/bins` | List all bins (name, updated, size, preview) |
| `GET` | `/api/bin/<name>` | Read a bin → `{name, text, updated}` |
| `PUT` or `POST` | `/api/bin/<name>` | Set a bin's text (raw body, or JSON `{"text": "..."}`) |
| `DELETE` | `/api/bin/<name>` | Delete a bin |
| `GET` | `/health` | Liveness check |

Send text to a bin (which, if you run the watcher, lands on your clipboard):
```bash
curl -X PUT --data 'hello from another device' http://your-hostname.local:8000/api/bin/default
```
Read it back:
```bash
curl http://your-hostname.local:8000/api/bin/default
```

---

## Running & managing the services

There are three good options depending on how permanent you want it.

### 1. The built-in supervisor (recommended, no extra tools)
`run.py` starts, health-checks, and cleanly shuts down both processes together.

```bash
python run.py            # server + clipboard watcher (default)
python run.py server     # server only (e.g. on a headless machine)
python run.py watch      # watcher only (server runs elsewhere)

python run.py --port 9000
python run.py watch --url http://192.168.0.237:8000 --bin notes
```

### 2. Docker / Docker Compose (server only)
The **server** containerizes cleanly. The **watcher does not** — it needs access
to the host OS clipboard, which a container can't reach — so run the watcher
natively with `python run.py watch` on machines that want clipboard mirroring.

```bash
docker compose up -d          # build + run the server, persisting bins to a volume
docker compose logs -f
docker compose down
```

### 3. Docker Swarm — and why it's usually overkill here
You asked about Swarm. It works:

```bash
docker swarm init                                   # once, on the manager node
docker stack deploy -c docker-compose.yml clipbin   # deploy the stack
docker stack services clipbin                       # check status
docker stack rm clipbin                             # tear down
```

But keep it to **one replica**. clipbin holds bins **in memory** (persisted to a
file); if Swarm ran several replicas, each would hold a *different* set of bins and
the load balancer would bounce you between them, so text would seem to appear and
vanish. Swarm gives you auto-restart and rolling redeploys, which is nice, but for
a single-instance LAN utility a plain `docker compose up -d`, `run.py`, or an
OS service (below) is simpler and does the same job. True horizontal scaling would
require swapping the in-memory store for shared storage (Redis, a database) — more
than this tool needs.

### 4. Start automatically at login (optional)
- **macOS:** a `launchd` LaunchAgent plist that runs `python3 run.py`.
- **Linux:** a `systemd --user` service.
- **Windows:** a Task Scheduler task at logon, or a shortcut to `run.bat` in the
  Startup folder.

(Ask and these can be added as ready-made files.)

---

## Security — please read

clipbin is built for **trusted local networks** (home / small office). It has:

- **No authentication** — anyone who can reach the URL can read and write *every* bin.
- **No encryption** — it's plain HTTP.

So:
- Don't put long-term secrets in a bin — anyone on your Wi‑Fi can read them, and if
  you run the clipboard watcher, whatever lands in the watched bin lands on your
  clipboard.
- Don't expose the port to the public internet or forward it through your router.
- `bins.json` (the persistence file) holds your actual bin contents and is
  **git-ignored** on purpose — don't commit it.

---

## Files

| File | What it is |
| --- | --- |
| `clipbin.py` | The server (web UI + JSON API). |
| `clipsync.py` | Clipboard watcher: mirrors a bin → this machine's clipboard. |
| `run.py` | Cross-platform supervisor for both processes. |
| `run.sh` / `run.ps1` / `run.bat` | Thin launchers for macOS·Linux / Windows. |
| `Dockerfile`, `docker-compose.yml` | Containerize/orchestrate the server. |
| `bins.json` | Runtime persistence (git-ignored). |

## License

MIT — see [LICENSE](LICENSE).
