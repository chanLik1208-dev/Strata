"""Downloads llama.cpp's ready-made llama-server for Strata's generic mode (serve/generic.py) into engine-llama/.

The build is pinned (LLAMA_TAG) like Strata's other downloads, so a generic setup today and next month run the same
server; --tag latest takes the newest release instead.  Which build: NVIDIA with a driver of 580 or newer: CUDA 13.4,
an older driver: CUDA 12.4 (Windows) / 12.8 (Linux); no NVIDIA card: Vulkan (AMD, Intel and others); --backend
picks one yourself.  On Windows the CUDA runtime DLLs come as a second zip (cudart-...), unpacked beside it.

    python tools/get_llama_server.py [--tag b11541|latest] [--backend cuda13|cuda12|vulkan|cpu]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "engine-llama"
REPO = "ggml-org/llama.cpp"
LLAMA_TAG = "b11541"                 # 2026-10-10: /v1/responses, /v1/messages, --fit, return_progress
WIN = os.name == "nt"
CUDA13_DRIVER = 580


def nvidia_driver() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0].split(".")[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def pick_backend(driver: int | None) -> str:
    if driver is None:
        return "vulkan"
    return "cuda13" if driver >= CUDA13_DRIVER else "cuda12"


def asset_names(tag: str, backend: str, win: bool = WIN) -> list[str]:
    """The release files for this backend: the build, and on Windows CUDA its runtime DLLs."""
    if win:
        cuda = {"cuda13": "13.4", "cuda12": "12.4"}.get(backend)
        if cuda:
            return [f"llama-{tag}-bin-win-cuda-{cuda}-x64.zip", f"cudart-llama-bin-win-cuda-{cuda}-x64.zip"]
        return [f"llama-{tag}-bin-win-{'vulkan' if backend == 'vulkan' else 'cpu'}-x64.zip"]
    cuda = {"cuda13": "13.4", "cuda12": "12.8"}.get(backend)
    if cuda:
        return [f"llama-{tag}-bin-ubuntu-cuda-{cuda}-x64.tar.gz", f"cudart-llama-{tag}-bin-ubuntu-cuda-{cuda}-x64.tar.gz"]
    return [f"llama-{tag}-bin-ubuntu-{'vulkan-' if backend == 'vulkan' else ''}x64.tar.gz"]


def latest_tag() -> str:
    with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases?per_page=5", timeout=30) as r:
        for rel in json.load(r):
            if rel["tag_name"].startswith("b") and len(rel.get("assets", [])) > 10:
                return rel["tag_name"]
    raise SystemExit("could not find a llama.cpp release with builds")


def download(url: str, to: Path):
    print(f"  downloading {url.rsplit('/', 1)[1]} ...", flush=True)
    with urllib.request.urlopen(url, timeout=60) as r, open(to, "wb") as f:
        total, done, last = int(r.headers.get("Content-Length") or 0), 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            pct = done * 100 // total if total else -1
            if pct >= 0 and pct // 10 != last:
                last = pct // 10
                print(f"    {pct}% of {total / 2**20:.0f} MB", flush=True)


def unpack(archive: Path, into: Path):
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(into)
    else:
        with tarfile.open(archive) as t:
            t.extractall(into, filter="data")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default=LLAMA_TAG, help=f"a llama.cpp release (default {LLAMA_TAG}) or 'latest'")
    ap.add_argument("--backend", choices=["cuda13", "cuda12", "vulkan", "cpu"],
                    help="default: by the NVIDIA driver (580+: cuda13), Vulkan without an NVIDIA card")
    a = ap.parse_args()
    tag = latest_tag() if a.tag == "latest" else a.tag
    driver = nvidia_driver()
    backend = a.backend or pick_backend(driver)
    stamp = DEST / "BUILD.json"
    if stamp.exists():
        try:
            have = json.loads(stamp.read_text(encoding="utf-8"))
            if have.get("tag") == tag and have.get("backend") == backend:
                print(f"llama-server {tag} ({backend}) is already in {DEST}")
                return 0
        except ValueError:
            pass
    print(f"llama-server {tag}, {backend}" + (f" (NVIDIA driver {driver})" if driver else " (no NVIDIA driver found)"))
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        tmp = Path(tmp)
        out = tmp / "out"
        out.mkdir()
        for name in asset_names(tag, backend):
            arc = tmp / name
            download(f"https://github.com/{REPO}/releases/download/{tag}/{name}", arc)
            unpack(arc, out)
        exe = next(out.rglob("llama-server.exe" if WIN else "llama-server"), None)
        if exe is None:
            raise SystemExit("the download has no llama-server in it")
        for f in out.rglob("*"):                       # the runtime DLLs may sit in another folder: put all together
            if f.is_file() and f.parent != exe.parent:
                shutil.move(str(f), str(exe.parent / f.name))
        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.move(str(exe.parent), str(DEST))
    if not WIN:
        (DEST / "llama-server").chmod(0o755)
    stamp.write_text(json.dumps({"tag": tag, "backend": backend}), encoding="utf-8")
    print(f"done: {DEST / ('llama-server.exe' if WIN else 'llama-server')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
