"""Strata's generic mode: any GGUF model (Gemma, Llama, Mistral, a fine-tune of your own ...) run by llama.cpp's
llama-server, behind Strata's web app, Monitor and activity bar.

Strata's own engine (src/, serve/server.py) is written for Qwen3.8-Flash-Next and runs nothing else.  This mode puts a
small proxy in front of llama-server instead:

  - the API paths go through to llama-server unchanged: /v1/chat/completions, /v1/completions, /v1/messages
    (Anthropic), /v1/responses, /v1/models, /v1/embeddings, /tokenize ...  llama-server renders the model's own chat
    template (--jinja), so tools and thinking work as the model's template defines them;
  - the web app's own paths are answered here in the shape serve/server.py gives them: /health, /metrics (the
    Monitor: what is running, the prompt's progress, the last requests, the GPU/CPU/RAM), /settings, /mcp;
  - llama-server's --fit (on by default) places the model in the VRAM there is, so an 8 GB laptop card runs a model
    larger than its VRAM: what does not fit stays in RAM (for a mixture-of-experts model, the experts).

Standard library only, besides serve/telemetry.py (psutil / NVML when present).

    python serve/generic.py --model path/to/model.gguf [--ctx 32768] [--port 8080] [-- extra llama-server args]
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "serve" / "web"
WIN = os.name == "nt"
LLAMA_DIR = ROOT / "engine-llama"
HISTORY = 100                                    # the requests the Monitor can show ("Show all")
STRATA_ONLY = ("experimental_speed_projection", "strata_mcp")   # web-app fields llama-server does not know
PROGRESS_PATHS = ("/v1/chat/completions", "/v1/completions", "/completion", "/chat/completions")


def say(*a):
    print("[strata-generic]", *a, flush=True)


def default_llama_server() -> Path:
    return LLAMA_DIR / ("llama-server.exe" if WIN else "llama-server")


def gguf_facts(path: Path) -> dict:
    """The model's name, architecture, layers, experts and trained context from the GGUF's header (no tensors read).
    {} when the header cannot be read: llama-server will say what is wrong."""
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from gguf_reader import GGUFFile
        md = GGUFFile(path).metadata
    except Exception:
        return {}
    arch = str(md.get("general.architecture", ""))
    return {"name": md.get("general.name") or path.stem, "arch": arch,
            "layers": md.get(f"{arch}.block_count"), "experts": md.get(f"{arch}.expert_count"),
            "experts_used": md.get(f"{arch}.expert_used_count"), "trained_ctx": md.get(f"{arch}.context_length")}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def total_vram_gb(index: int = 0) -> float:
    try:
        out = subprocess.run(["nvidia-smi", "-i", str(index), "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return float(out.strip().splitlines()[0]) / 1024
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return 0.0


def llama_args(exe: Path, model: Path, port: int, name: str, ctx: int | None, mmproj: str | None, low_vram: bool,
               extra: list[str]) -> list[str]:
    """llama-server's command line.  Placement is left to its --fit (on by default) unless `extra` sets -ngl /
    --n-cpu-moe itself; `low_vram` adds the 8-bit KV cache (half of f16's VRAM) where `extra` sets none."""
    args = [str(exe), "-m", str(model), "--host", "127.0.0.1", "--port", str(port), "--alias", name, "--metrics",
            "--no-webui", "--reasoning-format", "deepseek"]
    if ctx:
        args += ["-c", str(ctx)]
    if mmproj:
        args += ["--mmproj", mmproj]
    if low_vram and not any(a in extra for a in ("-ctk", "--cache-type-k")):
        args += ["-ctk", "q8_0", "-ctv", "q8_0"]
    return args + extra


class Upstream:
    """llama-server: the process, its log, and whether it answers yet."""

    def __init__(self, args: list[str], port: int, log: Path):
        self.port, self.log_path = port, log
        self.ready = False
        self.props: dict = {}
        self.error = ""
        self.log = open(log, "a", encoding="utf-8", errors="replace")
        say("starting:", subprocess.list2cmdline(args))
        self.proc = subprocess.Popen(args, cwd=str(Path(args[0]).parent), stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        try:                                     # Windows: llama-server ends with this proxy, however it ends
            sys.path.insert(0, str(ROOT))
            from serve.winjob import contain
            contain(self.proc)
        except Exception:
            pass
        threading.Thread(target=self._pump, daemon=True).start()
        threading.Thread(target=self._wait, daemon=True).start()

    def _pump(self):
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip()
            self.log.write(line + "\n")
            self.log.flush()
            low = line.lower()
            if any(k in low for k in ("error", "failed", "fit", "offload", "model loaded", "listening", "warn")):
                print("[llama-server]", line, flush=True)
        code = self.proc.wait()
        self.ready = False
        self.error = f"llama-server stopped (exit code {code}); its log: {self.log_path.name}"
        say(self.error)

    def _wait(self):
        while self.proc.poll() is None:
            try:
                status, body = self.get("/health")
                if status == 200:
                    _, props = self.get("/props")
                    self.props = json.loads(props or b"{}")
                    self.ready = True
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.5)

    def get(self, path: str) -> tuple[int, bytes]:
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            c.request("GET", path)
            r = c.getresponse()
            return r.status, r.read()
        finally:
            c.close()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class State:
    """What the Monitor and the activity bar show: the requests in flight, the last ones, and the totals."""

    def __init__(self):
        self.lock = threading.Lock()
        self.live: dict[str, dict] = {}
        self.history: deque = deque(maxlen=HISTORY)
        self.totals = {"since": time.time(), "requests": 0, "prompt_tokens": 0, "reused": 0, "output_tokens": 0,
                       "prompt_ms": 0.0, "decode_ms": 0.0}
        self.tok_s = 0.0

    def begin(self, path: str) -> str:
        rid = uuid.uuid4().hex[:12]
        with self.lock:
            self.live[rid] = {"path": path, "state": "reading", "started": time.time(), "prompt_read": None,
                              "prompt_total": None, "generated": 0, "first": None}
        return rid

    def update(self, rid: str, **kw):
        with self.lock:
            r = self.live.get(rid)
            if r is not None:
                r.update(kw)

    def token(self, rid: str):
        with self.lock:
            r = self.live.get(rid)
            if r is None:
                return
            now = time.time()
            if r["first"] is None:
                r["first"], r["state"] = now, "generating"
            r["generated"] += 1
            span = now - r["first"]
            if span > 0.5:
                self.tok_s = r["generated"] / span

    def end(self, rid: str, timings: dict | None, finish: str):
        with self.lock:
            r = self.live.pop(rid, None)
            if r is None:
                return
            t = timings or {}
            cache, prompt_n, out_n = t.get("cache_n") or 0, t.get("prompt_n") or 0, t.get("predicted_n") or r["generated"]
            rec = {"time": r["started"], "duration_s": round(time.time() - r["started"], 1), "finish": finish,
                   "path": r["path"], "prompt_tokens": (prompt_n + cache) or None, "reused": cache,
                   "output_tokens": out_n, "prompt_ms": t.get("prompt_ms"), "decode_ms": t.get("predicted_ms"),
                   "decode_tok_s": round(t["predicted_per_second"], 1) if t.get("predicted_per_second") else None,
                   "prefill_tok_s": round(t["prompt_per_second"], 1) if t.get("prompt_per_second") else None,
                   "state": "done" if finish != "error" else "error"}
            self.history.append(rec)
            tot = self.totals
            tot["requests"] += 1
            tot["prompt_tokens"] += rec["prompt_tokens"] or 0
            tot["reused"] += cache
            tot["output_tokens"] += out_n or 0
            tot["prompt_ms"] += t.get("prompt_ms") or 0.0
            tot["decode_ms"] += t.get("predicted_ms") or 0.0

    def live_view(self, slots: int) -> dict:
        with self.lock:
            reqs = sorted(self.live.values(), key=lambda r: r["started"])
            tok_s = self.tok_s
        running = reqs[:max(1, slots)]
        queued = len(reqs) - len(running)
        cur = running[-1] if running else None
        state = cur["state"] if cur else "idle"
        return {"state": state, "queued": queued, "phase": None,
                "prompt_tokens": cur.get("prompt_total") if cur else None,
                "prompt_read": cur.get("prompt_read") if cur and state == "reading" else None,
                "prompt_total": cur.get("prompt_total") if cur and state == "reading" else None,
                "generated": cur["generated"] if cur else None, "max_tokens": None,
                "elapsed_s": round(time.time() - cur["started"], 1) if cur else None,
                "tok_s": round(tok_s, 1) if state == "generating" else None,
                "tok_s_mean": round(tok_s, 1) if state == "generating" else None}


def make_handler(up: Upstream, st: State, name: str, api_key: str | None, telemetry, facts: dict):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        # ---- helpers
        def _json(self, code: int, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, f: Path, ctype: str):
            body = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not api_key:
                return True
            got = self.headers.get("Authorization", "")
            got = got[7:] if got.lower().startswith("bearer ") else self.headers.get("x-api-key", "")
            if got and got in api_key.split(","):
                return True
            self._json(401, {"error": {"message": "this server needs an API key", "type": "authentication_error"}})
            return False

        def _health(self) -> dict:
            p = up.props
            return {"status": "ok" if up.ready else "loading", "model": name,
                    "max_context": (p.get("default_generation_settings") or {}).get("n_ctx") or p.get("n_ctx"),
                    "images": bool((p.get("modalities") or {}).get("vision")), "api_key": bool(api_key),
                    "loaded": up.ready, "service": "strata", "engine": "llama.cpp", "error": up.error or None}

        def _metrics(self, all_requests: bool) -> dict:
            p = up.props
            slots = int(p.get("total_slots") or 1)
            h = self._health()
            with st.lock:
                hist = list(st.history)
                totals = dict(st.totals)
            live = st.live_view(slots)
            if not up.ready and live["state"] != "idle":
                live["state"] = "reading"
            requests = [dict(r) for r in hist[::-1]]
            if not up.ready and up.proc.poll() is None:  # the model is still loading: the activity bar says so
                requests.insert(0, {"time": time.time(), "state": "loading", "prompt_tokens": None, "output_tokens": None})
            tel = telemetry.snapshot() if telemetry else {"now": {}, "history": {}, "static": {}}
            engine = {"model": name, "max_context": h["max_context"], "images": h["images"], "backend": "llama.cpp",
                      "arch": facts.get("arch"), "layers": facts.get("layers"), "experts": facts.get("experts")}
            return {"engine": engine, "live": live, "requests": requests if all_requests else requests[:12],
                    "conversation_cache": None, "requests_kept": len(hist), "totals": totals,
                    "hardware": tel["now"], "hardware_static": tel["static"], "history": tel["history"],
                    "time": time.time()}

        # ---- the web app's own paths
        def do_GET(self):
            path = self.path.split("?")[0].rstrip("/")
            if path == "":
                return self._file(WEB / "index.html", "text/html; charset=utf-8")
            if path.startswith("/web/") or path.startswith("/fonts/"):
                sub = WEB / "fonts" if path.startswith("/fonts/") else WEB
                fname = path.split("/", 2)[2]
                types = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                         ".svg": "image/svg+xml", ".woff2": "font/woff2"}
                f = sub / fname
                if "/" in fname or "\\" in fname or f.suffix not in types or not f.is_file():
                    return self._json(404, {"error": {"message": "not found"}})
                return self._file(f, types[f.suffix])
            if path in ("/health", "/api/health"):
                return self._json(200 if up.ready else 503, self._health())
            if path == "/metrics" and "prometheus" not in self.headers.get("Accept", ""):
                if self._authorized():
                    self._json(200, self._metrics("requests=all" in self.path))
                return
            if path == "/settings":
                return self._json(200, {"shared": False, "defaults": None}) if self._authorized() else None
            if path == "/mcp":
                return self._json(200, {"servers": [], "tools": 0}) if self._authorized() else None
            if path == "/config":
                return self._json(404, {"error": {"message": "generic mode: settings are the command line"}})
            self._proxy("GET")

        def do_POST(self):
            path = self.path.split("?")[0].rstrip("/")
            if path in ("/settings", "/config"):
                return self._json(400, {"error": {"message": "not available in generic mode (llama.cpp)"}})
            self._proxy("POST")

        def do_DELETE(self):
            self._proxy("DELETE")

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()

        # ---- everything else: llama-server
        def _proxy(self, method: str):
            if not self._authorized():
                return
            if not up.ready:
                return self._json(503, {"error": {"message": up.error or "the model is still loading",
                                                  "type": "unavailable"}})
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            path = self.path.split("?")[0].rstrip("/")
            tracked = method == "POST" and (path.startswith("/v1/") or path in PROGRESS_PATHS)
            stream = asked_progress = False
            if body and self.headers.get("Content-Type", "").startswith("application/json"):
                try:
                    req = json.loads(body)
                except ValueError:
                    req = None
                if isinstance(req, dict):
                    for k in STRATA_ONLY:
                        req.pop(k, None)
                    stream = bool(req.get("stream"))
                    asked_progress = bool(req.get("return_progress"))
                    if stream and path in PROGRESS_PATHS:
                        req["return_progress"] = True       # the prompt's progress, for the Monitor and the bar
                    body = json.dumps(req).encode()
            rid = st.begin(path) if tracked else None
            finish, timings = "error", None
            conn = http.client.HTTPConnection("127.0.0.1", up.port, timeout=3600)
            try:
                headers = {k: v for k, v in self.headers.items()
                           if k.lower() not in ("host", "content-length", "connection", "authorization", "x-api-key")}
                headers["Content-Length"] = str(len(body))
                conn.request(method, self.path, body=body, headers=headers)
                r = conn.getresponse()
                ctype = r.getheader("Content-Type", "")
                if "text/event-stream" in ctype:
                    finish, timings = self._relay_sse(r, rid, asked_progress)
                else:
                    data = r.read()
                    self.send_response(r.status)
                    for k, v in r.getheaders():
                        if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    if rid and r.status == 200:
                        try:
                            j = json.loads(data)
                            timings = j.get("timings")
                            finish = "stop"
                        except ValueError:
                            pass
            except (ConnectionError, OSError) as e:
                if rid:
                    finish = "cancelled" if isinstance(e, (BrokenPipeError, ConnectionResetError)) else "error"
                try:
                    self._json(502, {"error": {"message": f"llama-server: {e}"}})
                except OSError:
                    pass
            finally:
                conn.close()
                if rid:
                    st.end(rid, timings, finish)

        def _relay_sse(self, r, rid, asked_progress) -> tuple[str, dict | None]:
            self.send_response(r.status)
            self.send_header("Content-Type", r.getheader("Content-Type"))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            finish, timings = "stop", None

            def send(chunk: bytes):
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                self.wfile.flush()

            while True:
                line = r.readline()
                if not line:
                    break
                drop = False
                s = line.strip()
                if rid and s.startswith(b"data:") and s[5:].strip() not in (b"", b"[DONE]"):
                    try:
                        j = json.loads(s[5:])
                    except ValueError:
                        j = None
                    if isinstance(j, dict):
                        pp = j.get("prompt_progress")
                        if pp:
                            st.update(rid, prompt_read=pp.get("processed"), prompt_total=pp.get("total"))
                            only = not j.get("choices") or not any(
                                (c.get("delta") or {}).get(k) for c in j["choices"]
                                for k in ("content", "reasoning_content", "tool_calls"))
                            drop = only and not asked_progress
                        if j.get("timings"):
                            timings = j["timings"]
                        for c in j.get("choices") or []:
                            d = c.get("delta") or {}
                            if d.get("content") or d.get("reasoning_content") or d.get("tool_calls") or c.get("text"):
                                st.token(rid)
                            if c.get("finish_reason"):
                                finish = c["finish_reason"]
                        if j.get("type") in ("content_block_delta", "response.output_text.delta"):
                            st.token(rid)                 # Anthropic / Responses streams: count their deltas
                if drop:
                    r.readline()                          # the blank line that ends the dropped event
                    continue
                try:
                    send(line)
                except OSError:
                    return "cancelled", timings
            try:
                send(b"")                                  # the last chunk
            except OSError:
                pass
            return finish, timings

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description="Strata's generic mode: any GGUF through llama.cpp's llama-server.",
                                 epilog="Arguments after -- go to llama-server unchanged (e.g. -- -ngl 20 --n-cpu-moe 30).")
    ap.add_argument("--model", required=True, help="the .gguf file (for a split model: its first part)")
    ap.add_argument("--mmproj", help="the vision projector .gguf, for a model that reads images")
    ap.add_argument("--name", help="the model's name in the API and the web app (default: from the GGUF)")
    ap.add_argument("--ctx", type=int, help="context in tokens (default: llama-server's choice, fitted to memory)")
    ap.add_argument("--low-vram", action="store_true", help="8-bit KV cache (half the VRAM of f16), for 8-12 GB cards")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--api-key", help="require this key (always set one with --host 0.0.0.0)")
    ap.add_argument("--llama-server", default=str(default_llama_server()), help="the llama-server executable")
    ap.add_argument("--gpu", type=int, default=0, help="the card the Monitor shows (nvidia-smi's number)")
    ap.add_argument("--no-browser", action="store_true")
    if "--" in sys.argv:
        cut = sys.argv.index("--")
        a, extra = ap.parse_args(sys.argv[1:cut]), sys.argv[cut + 1:]
    else:
        a, extra = ap.parse_args(), []
    model, exe = Path(a.model), Path(a.llama_server)
    if not model.is_file():
        ap.error(f"no such model file: {model}")
    if not exe.is_file():
        ap.error(f"llama-server not found at {exe}: run  python tools/get_llama_server.py  first")
    if a.host not in ("127.0.0.1", "localhost") and not a.api_key:
        ap.error("--host beyond this PC needs --api-key")
    facts = gguf_facts(model)
    name = a.name or str(facts.get("name") or model.stem)
    vram = total_vram_gb(a.gpu)
    say(f"model: {name} ({facts.get('arch') or '?'}, {facts.get('layers') or '?'} layers"
        + (f", {facts['experts']} experts, {facts.get('experts_used')} per token" if facts.get("experts") else "")
        + f"), {model.stat().st_size / 2**30:.1f} GB file" + (f"; GPU: {vram:.1f} GB VRAM" if vram else "; no NVIDIA GPU"))
    if vram and model.stat().st_size / 2**30 > vram - 1:
        say("the model is larger than the VRAM: llama-server's --fit keeps what does not fit in RAM"
            + (" (the experts of the first layers: a MoE model runs well this way)" if facts.get("experts") else
               " (the last layers: slower, a dense model reads them from RAM each token)"))
    up_port = free_port()
    log = ROOT / f"strata-generic-{model.stem.lower()}.log"
    up = Upstream(llama_args(exe, model, up_port, name, a.ctx, a.mmproj, a.low_vram, extra), up_port, log)
    st = State()                                         # before the telemetry thread asks it for tok/s
    try:
        sys.path.insert(0, str(ROOT))
        from serve.telemetry import Telemetry
        telemetry = Telemetry(extra=lambda: {"tok_s": st.tok_s}, gpu_index=a.gpu)
    except Exception as e:                               # the Monitor's hardware cards stay empty
        say(f"hardware readings off: {e}")
        telemetry = None
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(up, st, name, a.api_key, telemetry, facts))
    srv.daemon_threads = True
    url = f"http://127.0.0.1:{a.port}"
    say(f"web app: {url}  (the model loads in the background; the page shows when it is ready)")
    say(f"API: {url}/v1 (OpenAI), {url}/v1/messages (Anthropic), {url}/v1/responses")

    def opener():
        while not up.ready and up.proc.poll() is None:
            time.sleep(0.5)
        if up.ready:
            say(f"ready: {url}/v1")
            if not a.no_browser:
                webbrowser.open(url)
    threading.Thread(target=opener, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        up.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
