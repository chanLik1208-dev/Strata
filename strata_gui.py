"""Strata's desktop launcher: a window over setup.py and the run-<model> scripts, for people who would rather click
than answer questions in a console.  It finds the GPU and RAM, recommends a model and the --low-vram profile on an
8-12 GB NVIDIA card (most gaming laptops), installs or changes a model with setup.py --yes, starts and stops an
installed one, and shows the server's state.  Standard library only (tkinter); started by STRATA-GUI.bat /
strata-gui.sh.  Everything it runs is printed in its log as the command line it used.

    python strata_gui.py
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

ROOT = Path(__file__).resolve().parent
WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if WIN else 0                  # CREATE_NO_WINDOW: no console behind the launcher

try:                                                  # setup's own tables, so the menus match what it accepts
    sys.path.insert(0, str(ROOT))
    import setup as S                                 # noqa: E402
    FAMILIES = {k: v["title"] for k, v in S.FAMILIES.items()}
    MODELS = S.MODELS
    DRAFT_VOCABS = list(S.DRAFT_VOCABS)
    LOW_VRAM_MAX_GB = S.LOW_VRAM_MAX_GB
except Exception:                                     # a copy without setup.py's newer names: the launcher still opens
    S = None
    FAMILIES = {"qwen": "Qwen3.8-Flash-Next", "swift": "Swift 1.5", "coder": "Qwen3.8-Flash-Next Coder",
                "unsloth": "Qwen3.8-Flash-Next (Unsloth)"}
    MODELS = {"Q2_0": {"ram_gb": 48, "families": ("qwen",)}, "IQ2_XS": {"ram_gb": 48},
              "IQ3_XXS": {"ram_gb": 60}, "IQ3_S": {"ram_gb": 62}, "IQ1_M": {"ram_gb": 32, "families": ("coder",)},
              "UD-IQ4_XS": {"ram_gb": 48, "families": ("unsloth",)}}
    DRAFT_VOCABS = ["cjk", "en", "cyrillic", "fr"]
    LOW_VRAM_MAX_GB = 12.5

CONTEXTS = ["auto", "8192", "16384", "32768", "65536", "131072", "262144"]


# ---- the PC

def nvidia_gpus() -> list[dict]:
    """[{index, name, vram_gb, driver}] from nvidia-smi; [] without an NVIDIA card or driver."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        text = subprocess.run([exe, "--query-gpu=index,name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in text.strip().splitlines():
        try:
            idx, name, mem, drv = [x.strip() for x in line.split(",")]
            found.append({"index": int(idx), "name": name, "vram_gb": float(mem) / 1024.0, "driver": drv})
        except ValueError:
            continue
    return found


def ram_gb() -> float:
    if WIN:
        class MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MemStatus()
        m.dwLength = ctypes.sizeof(m)
        return m.ullTotalPhys / 2 ** 30 if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) else 0.0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 2 ** 20
    except OSError:
        pass
    return 0.0


def is_laptop(g) -> bool:
    return "laptop" in str(g.get("name", "")).lower()


def recommended(ram: float) -> tuple[str, str]:
    """(family, size) by RAM, as the README's table picks them."""
    if ram < 40:
        return "coder", "IQ1_M"
    if ram < 90:
        return "qwen", "IQ2_XS"
    return "qwen", "IQ3_S"


def family_sizes(family: str) -> list[str]:
    return [m for m, v in MODELS.items() if family in v.get("families", ("qwen", "swift"))]


def installed() -> list[str]:
    """The installed models' tags (strata-<tag>.json beside setup.py), newest first."""
    files = [p for p in ROOT.glob("strata-*.json") if not p.name.endswith(".shared-settings.json")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem[len("strata-"):] for p in files]


def config_port(tag: str) -> int:
    try:
        cfg = json.loads((ROOT / f"strata-{tag}.json").read_text(encoding="utf-8"))
        return int(cfg.get("port") or 8080)
    except (OSError, ValueError, TypeError):
        return 8080


# ---- the window

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Strata 啟動器")
        self.geometry("880x760")
        self.minsize(720, 600)
        self.proc: subprocess.Popen | None = None
        self.proc_kind = ""
        self.lines: queue.Queue[str] = queue.Queue()
        self.gpus = nvidia_gpus()
        self.ram = ram_gb()

        self.family = tk.StringVar()
        self.size = tk.StringVar()
        self.context = tk.StringVar(value="auto")
        self.kv = tk.StringVar(value="auto")
        self.vision = tk.StringVar(value="no")
        self.draft = tk.StringVar(value="auto")
        self.reserve = tk.StringVar()
        self.port = tk.StringVar(value="8080")
        self.data_dir = tk.StringVar()
        self.gpu_pick = tk.StringVar()
        self.low_vram = tk.BooleanVar()
        self.start_after = tk.BooleanVar(value=True)
        self.browser = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="伺服器：檢查中…")
        self.cmdline = tk.StringVar()

        self.build()
        self.defaults()
        for v in (self.family, self.size, self.context, self.kv, self.vision, self.draft, self.reserve, self.port,
                  self.data_dir, self.gpu_pick, self.low_vram, self.start_after, self.browser):
            v.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self.after(100, self.pump)
        self.after(500, self.poll_health)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # layout
    def build(self):
        pad = {"padx": 8, "pady": 4}
        top = ttk.LabelFrame(self, text="這台電腦")
        top.pack(fill="x", **pad)
        self.pc_label = ttk.Label(top, justify="left")
        self.pc_label.pack(anchor="w", padx=8, pady=6)

        run = ttk.LabelFrame(self, text="已安裝的模型")
        run.pack(fill="x", **pad)
        self.installed_box = ttk.Combobox(run, state="readonly", width=34)
        self.installed_box.grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.start_btn = ttk.Button(run, text="啟動", command=self.start_model)
        self.start_btn.grid(row=0, column=1, padx=4)
        self.stop_btn = ttk.Button(run, text="停止", command=self.stop)
        self.stop_btn.grid(row=0, column=2, padx=4)
        ttk.Button(run, text="開啟聊天", command=self.open_chat).grid(row=0, column=3, padx=4)
        ttk.Label(run, textvariable=self.status).grid(row=1, column=0, columnspan=4, padx=8, pady=(0, 6), sticky="w")

        form = ttk.LabelFrame(self, text="安裝模型或修改設定")
        form.pack(fill="x", **pad)
        r = 0

        def row(label, widget, hint=""):
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", padx=8, pady=3)
            widget.grid(row=r, column=1, sticky="we", padx=4, pady=3)
            if hint:
                ttk.Label(form, text=hint, foreground="gray").grid(row=r, column=2, sticky="w", padx=4)
            r += 1

        self.family_box = ttk.Combobox(form, state="readonly", values=list(FAMILIES), textvariable=self.family)
        row("模型", self.family_box, "qwen = 原版，coder = 寫程式用（32 GB 記憶體就放得下）")
        self.size_box = ttk.Combobox(form, state="readonly", textvariable=self.size)
        row("大小", self.size_box)
        row("Context（tokens）", ttk.Combobox(form, state="readonly", values=CONTEXTS, textvariable=self.context),
            "auto = 依顯卡自動建議")
        row("KV 快取", ttk.Combobox(form, state="readonly", values=["auto", "int8", "q4_0"], textvariable=self.kv),
            "q4_0 = VRAM 減半")
        row("圖片", ttk.Combobox(form, state="readonly", values=["no", "cpu", "gpu"], textvariable=self.vision),
            "cpu = 把 VRAM 留給模型")
        row("草稿詞表", ttk.Combobox(form, state="readonly", values=["auto", *DRAFT_VOCABS],
                                         textvariable=self.draft), "en = 英文／程式碼，比 cjk 少約 215 MiB VRAM")
        row("保留 VRAM（MiB）", ttk.Entry(form, textvariable=self.reserve), "空白 = 引擎預設")
        row("GPU", ttk.Combobox(form, state="readonly", textvariable=self.gpu_pick,
                                values=["auto"] + [f"{g['index']}: {g['name']}" for g in self.gpus]))
        row("連接埠", ttk.Entry(form, textvariable=self.port, width=8))
        dd = ttk.Frame(form)
        ttk.Entry(dd, textvariable=self.data_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(dd, text="...", width=3, command=self.pick_dir).pack(side="left", padx=(4, 0))
        row("模型檔資料夾", dd, "空白 = 本資料夾旁的 Strata-data")
        checks = ttk.Frame(form)
        self.low_check = ttk.Checkbutton(checks, text="低 VRAM 設定（NVIDIA 8–12 GB、筆電）",
                                         variable=self.low_vram)
        self.low_check.pack(side="left")
        ttk.Checkbutton(checks, text="完成後啟動", variable=self.start_after).pack(side="left", padx=12)
        ttk.Checkbutton(checks, text="開啟瀏覽器", variable=self.browser).pack(side="left")
        checks.grid(row=r, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        r += 1
        self.profile_label = ttk.Label(form, foreground="#2a6", justify="left", wraplength=800)
        self.profile_label.grid(row=r, column=0, columnspan=3, sticky="w", padx=8)
        r += 1
        btns = ttk.Frame(form)
        self.install_btn = ttk.Button(btns, text="安裝／套用", command=self.install)
        self.install_btn.pack(side="left")
        self.check_btn = ttk.Button(btns, text="檢查這台電腦", command=self.check)
        self.check_btn.pack(side="left", padx=6)
        btns.grid(row=r, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        r += 1
        ttk.Entry(form, textvariable=self.cmdline, state="readonly").grid(row=r, column=0, columnspan=3, sticky="we",
                                                                           padx=8, pady=(0, 8))
        form.columnconfigure(1, weight=1)

        act = ttk.Frame(self)
        act.pack(fill="x", padx=8)
        self.activity_text = tk.StringVar(value="閒置")
        ttk.Label(act, textvariable=self.activity_text, width=14).pack(side="left")
        self.activity = ttk.Progressbar(act, mode="indeterminate")
        self.activity.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.activity_on = False
        self.server_ready = False

        logf = ttk.LabelFrame(self, text="記錄")
        logf.pack(fill="both", expand=True, **pad)
        self.log = ScrolledText(logf, height=12, font=("Consolas" if WIN else "monospace", 9), state="disabled")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

    def defaults(self):
        g = self.main_gpu()
        fam, size = recommended(self.ram)
        self.family.set(fam)
        self.size.set(size)
        self.gpu_pick.set("auto")
        lines = [f"記憶體：{self.ram:.0f} GB"]
        if not self.gpus:
            lines.append("NVIDIA 顯卡：找不到（nvidia-smi）。AMD 顯卡由 setup.py 自行設定。")
        for x in self.gpus:
            lines.append(f"GPU {x['index']}：{x['name']}，{x['vram_gb']:.1f} GB VRAM，驅動 {x['driver']}"
                         + ("（筆電）" if is_laptop(x) else ""))
        if g and g["vram_gb"] < LOW_VRAM_MAX_GB:
            self.low_vram.set(True)
            lines.append(f"這張 {g['vram_gb']:.0f} GB 的顯卡低於 12 GB：已開啟低 VRAM 設定。"
                         "速度會比 12 GB 以上的桌機顯卡慢；放不進 GPU 的專家改由 CPU 計算。")
        if self.ram and self.ram < 32:
            lines.append("Strata 需要 32 GB 以上的記憶體：這台電腦不夠，模型放不下。")
        lines.append(f"{self.ram:.0f} GB 記憶體建議：{FAMILIES.get(fam, fam)} {size}")
        self.pc_label.configure(text="\n".join(lines))
        tags = installed()
        self.installed_box.configure(values=tags)
        if tags:
            self.installed_box.set(tags[0])
            self.port.set(str(config_port(tags[0])))

    def main_gpu(self):
        pick = self.gpu_pick.get()
        if pick and pick != "auto":
            idx = int(pick.split(":")[0])
            return next((g for g in self.gpus if g["index"] == idx), None)
        return max(self.gpus, key=lambda g: g["vram_gb"], default=None)

    # the command
    def setup_args(self) -> list[str]:
        args = ["--yes", "--family", self.family.get(), "--model", self.size.get()]
        if installed():
            args.append("--setup")
        if self.context.get() != "auto":
            args += ["--context", self.context.get()]
        if self.kv.get() != "auto":
            args += ["--kv", self.kv.get()]
        args += ["--vision", {"no": "no", "cpu": "cpu", "gpu": "gpu"}[self.vision.get()]]
        if self.draft.get() != "auto":
            args += ["--draft-vocab", self.draft.get()]
        if self.reserve.get().strip().isdigit():
            args += ["--vram-reserve-mib", self.reserve.get().strip()]
        if self.gpu_pick.get() not in ("", "auto"):
            args += ["--gpu", self.gpu_pick.get().split(":")[0]]
        if self.port.get().strip().isdigit() and self.port.get().strip() != "8080":
            args += ["--port", self.port.get().strip()]
        if self.data_dir.get().strip():
            args += ["--data-dir", self.data_dir.get().strip()]
        if self.low_vram.get():
            args += ["--low-vram", "on"]
        if not self.start_after.get():
            args.append("--no-start")
        if not self.browser.get():
            args.append("--no-browser")
        return args

    def launcher(self, args: list[str]) -> list[str]:
        """setup.py through START-HERE.bat / setup.sh: they make the Python environment on a first run."""
        if WIN:
            return ["cmd", "/c", str(ROOT / "START-HERE.bat"), *args]
        return ["bash", str(ROOT / "setup.sh"), *args]

    def refresh(self):
        sizes = family_sizes(self.family.get())
        self.size_box.configure(values=sizes)
        if sizes and self.size.get() not in sizes:
            self.size.set(sizes[0])
        m = MODELS.get(self.size.get(), {})
        if m.get("ram_gb") and self.ram and self.ram < m["ram_gb"] - 4:
            note = f"需要約 {m['ram_gb']} GB 記憶體，這台電腦有 {self.ram:.0f} GB"
        else:
            note = ""
        self.profile_label.configure(text=(self.profile_text() + ("\n" if note else "") + note).strip())
        self.cmdline.set(subprocess.list2cmdline(self.launcher(self.setup_args())))
        busy = self.proc is not None and self.proc.poll() is None
        for b in (self.install_btn, self.check_btn, self.start_btn):
            b.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")
        self.show_activity()

    def show_activity(self):
        """The loading bar runs while setup, the check or the model's start works, and stops once the server
        answers /health as loaded: a model that is up and waiting is not "loading"."""
        busy = self.proc is not None and self.proc.poll() is None
        on = busy and not (self.proc_kind == "server" and self.server_ready)
        if on and not self.activity_on:
            self.activity.start(12)
        elif not on and self.activity_on:
            self.activity.stop()
            self.activity["value"] = 0
        self.activity_on = on
        what = {"setup": "安裝／設定中…", "check": "檢查電腦中…", "server": "啟動模型中…"}.get(self.proc_kind, "處理中…")
        self.activity_text.set(what if on else ("模型執行中" if busy else "閒置"))

    def profile_text(self) -> str:
        g = self.main_gpu()
        if not self.low_vram.get() or g is None or S is None:
            return ""
        ctx = None if self.context.get() == "auto" else int(self.context.get())
        p = S.low_vram_profile(g["vram_gb"], False, ctx, None if self.kv.get() == "auto" else self.kv.get(),
                               None, int(self.reserve.get()) if self.reserve.get().strip().isdigit() else None)
        if not p:
            return f"低 VRAM 設定：{g['vram_gb']:.0f} GB 的顯卡不需要（不會改任何東西）。"
        parts = []
        if "context" in p:
            parts.append(f"context {p['context'] // 1024}K")
        if "kv" in p:
            parts.append("4-bit KV 快取")
        if "draft_vocab" in p and self.draft.get() == "auto":
            parts.append("英文／程式碼草稿詞表")
        parts.append("開圖片時改用 CPU")
        parts.append(f"若這張卡接螢幕則保留 {S.DISPLAY_RESERVE_MIB} MiB")
        return "低 VRAM 設定會套用：" + "、".join(parts) + "（上面你自己選的優先）。"

    # actions
    def run(self, cmd: list[str], kind: str):
        if self.proc is not None and self.proc.poll() is None:
            messagebox.showinfo("Strata", "已經有工作在執行，請先停止。")
            return
        self.say(f"\n> {subprocess.list2cmdline(cmd)}\n")
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, env=env, creationflags=NO_WINDOW)
        except OSError as e:
            self.say(f"無法啟動：{e}\n")
            return
        self.proc_kind = kind
        threading.Thread(target=self.read, args=(self.proc,), daemon=True).start()
        self.refresh()

    def read(self, proc):
        for raw in iter(proc.stdout.readline, b""):
            self.lines.put(raw.decode("utf-8", "replace"))
        code = proc.wait()
        self.lines.put(f"[{self.proc_kind} 結束，代碼 {code}]\n")
        self.lines.put("\0refresh")

    def install(self):
        m = MODELS.get(self.size.get(), {})
        size = f"約 {m['download_gb']:.0f} GB" if m.get("download_gb") else "70–120 GB"
        if not messagebox.askokcancel("Strata", f"將下載並設定 {self.family.get()} {self.size.get()}（{size}，已下載過的不會重抓）。"
                                                "可能要一小時以上，中斷後重跑會接續。要繼續嗎？"):
            return
        self.run(self.launcher(self.setup_args()), "setup")

    def check(self):
        self.run(self.launcher(["--check"]), "check")

    def start_model(self):
        tag = self.installed_box.get()
        if not tag:
            messagebox.showinfo("Strata", "還沒有安裝模型，請用下方的「安裝／套用」。")
            return
        script = ROOT / (f"run-{tag}.bat" if WIN else f"run-{tag}.sh")
        if not script.exists():
            self.say(f"找不到 {script.name}：請對這個模型重新「安裝／套用」\n")
            return
        self.port.set(str(config_port(tag)))
        self.run(["cmd", "/c", str(script)] if WIN else ["bash", str(script)], "server")

    def stop(self):
        p = self.proc
        if p is None or p.poll() is not None:
            return
        self.say("[停止中…]\n")
        if WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, creationflags=NO_WINDOW)
        else:
            p.terminate()

    def open_chat(self):
        webbrowser.open(f"http://127.0.0.1:{self.port.get().strip() or '8080'}")

    def pick_dir(self):
        d = filedialog.askdirectory(title="模型檔放哪裡（70–120 GB）")
        if d:
            self.data_dir.set(d)

    # plumbing
    def say(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        if int(self.log.index("end-1c").split(".")[0]) > 5000:
            self.log.delete("1.0", "1000.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def pump(self):
        try:
            while True:
                line = self.lines.get_nowait()
                if line == "\0refresh":
                    self.defaults_installed()
                    self.refresh()
                else:
                    self.say(line)
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def defaults_installed(self):
        tags = installed()
        self.installed_box.configure(values=tags)
        if tags and self.installed_box.get() not in tags:
            self.installed_box.set(tags[0])

    def poll_health(self):
        port = self.port.get().strip() or "8080"

        def ask():
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                    h = json.loads(r.read().decode("utf-8"))
                text = (f"伺服器：執行中（port {port}）－ {h.get('model', '?')}，context {h.get('max_context', '?')}"
                        + ("" if h.get("loaded", True) else "（模型載入中…）"))
            except Exception:
                text = "伺服器：未執行" + ("（啟動中…）" if self.proc_kind == "server" and self.proc
                                                and self.proc.poll() is None else "")
            ready = text.startswith("伺服器：執行中") and "載入中" not in text

            def apply():
                self.status.set(text)
                self.server_ready = ready
                self.show_activity()
            self.after(0, apply)

        threading.Thread(target=ask, daemon=True).start()
        self.after(3000, self.poll_health)

    def on_close(self):
        if self.proc is not None and self.proc.poll() is None:
            what = "模型" if self.proc_kind == "server" else "安裝程式"
            if not messagebox.askyesno("Strata", f"要停止{what}並關閉嗎？"):
                return
            self.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
