"""Tests for the generic mode (serve/generic.py) and its llama-server download (tools/get_llama_server.py): the
llama-server command line, the Monitor's request accounting, the GGUF header facts and the release file names.
No GPU, no model, no network.

    python -m unittest serve.test_generic
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from serve import generic  # noqa: E402
import get_llama_server as G  # noqa: E402


def tiny_gguf(path: Path, kv: list[tuple[str, int, bytes]]):
    def s(x):
        b = x.encode()
        return struct.pack("<Q", len(b)) + b
    with open(path, "wb") as f:
        f.write(b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0) + struct.pack("<Q", len(kv)))
        for k, t, v in kv:
            f.write(s(k) + struct.pack("<I", t) + v)


class Args(unittest.TestCase):
    def test_placement_is_left_to_fit(self):
        a = generic.llama_args(Path("ls"), Path("m.gguf"), 9000, "m", None, None, False, [])
        self.assertNotIn("-ngl", a)
        self.assertNotIn("--n-cpu-moe", a)
        for flag in ("--metrics", "--no-webui", "--alias"):
            self.assertIn(flag, a)
        self.assertEqual(a[a.index("--reasoning-format") + 1], "deepseek")

    def test_low_vram_kv_unless_set(self):
        a = generic.llama_args(Path("ls"), Path("m.gguf"), 9000, "m", 16384, None, True, [])
        self.assertEqual(a[a.index("-ctk") + 1], "q8_0")
        self.assertEqual(a[a.index("-c") + 1], "16384")
        b = generic.llama_args(Path("ls"), Path("m.gguf"), 9000, "m", None, None, True, ["-ctk", "f16"])
        self.assertEqual(b.count("-ctk"), 1)

    def test_extra_args_come_last(self):
        a = generic.llama_args(Path("ls"), Path("m.gguf"), 9000, "m", None, "p.gguf", False, ["-ngl", "20"])
        self.assertEqual(a[-2:], ["-ngl", "20"])
        self.assertEqual(a[a.index("--mmproj") + 1], "p.gguf")


class Accounting(unittest.TestCase):
    def test_a_request_from_reading_to_done(self):
        st = generic.State()
        rid = st.begin("/v1/chat/completions")
        st.update(rid, prompt_read=500, prompt_total=1000)
        v = st.live_view(1)
        self.assertEqual((v["state"], v["prompt_read"], v["prompt_total"]), ("reading", 500, 1000))
        st.token(rid)
        self.assertEqual(st.live_view(1)["state"], "generating")
        st.end(rid, {"cache_n": 10, "prompt_n": 990, "predicted_n": 4, "prompt_ms": 400.0, "predicted_ms": 100.0,
                     "predicted_per_second": 40.0, "prompt_per_second": 2475.0}, "stop")
        self.assertEqual(st.live_view(1)["state"], "idle")
        r = st.history[-1]
        self.assertEqual((r["prompt_tokens"], r["reused"], r["output_tokens"], r["decode_tok_s"]), (1000, 10, 4, 40.0))
        self.assertEqual(st.totals["requests"], 1)

    def test_more_requests_than_slots_are_queued(self):
        st = generic.State()
        for _ in range(3):
            st.begin("/v1/chat/completions")
        self.assertEqual(st.live_view(1)["queued"], 2)
        self.assertEqual(st.live_view(4)["queued"], 0)


class Facts(unittest.TestCase):
    def test_moe_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.gguf"
            s = lambda x: struct.pack("<Q", len(x.encode())) + x.encode()   # noqa: E731
            tiny_gguf(p, [("general.architecture", 8, s("gemma4")), ("general.name", 8, s("Satsuki")),
                          ("gemma4.block_count", 4, struct.pack("<I", 30)),
                          ("gemma4.expert_count", 4, struct.pack("<I", 128))])
            f = generic.gguf_facts(p)
            self.assertEqual((f["name"], f["arch"], f["layers"], f["experts"]), ("Satsuki", "gemma4", 30, 128))

    def test_unreadable_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.gguf"
            p.write_bytes(b"not a gguf")
            self.assertEqual(generic.gguf_facts(p), {})


class Download(unittest.TestCase):
    def test_backend_by_driver(self):
        self.assertEqual(G.pick_backend(581), "cuda13")
        self.assertEqual(G.pick_backend(560), "cuda12")
        self.assertEqual(G.pick_backend(None), "vulkan")

    def test_release_file_names(self):
        self.assertEqual(G.asset_names("b1", "cuda13", win=True),
                         ["llama-b1-bin-win-cuda-13.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip"])
        self.assertEqual(G.asset_names("b1", "vulkan", win=True), ["llama-b1-bin-win-vulkan-x64.zip"])
        self.assertEqual(G.asset_names("b1", "cuda12", win=False),
                         ["llama-b1-bin-ubuntu-cuda-12.8-x64.tar.gz", "cudart-llama-b1-bin-ubuntu-cuda-12.8-x64.tar.gz"])
        self.assertEqual(G.asset_names("b1", "cpu", win=False), ["llama-b1-bin-ubuntu-x64.tar.gz"])


if __name__ == "__main__":
    unittest.main()
