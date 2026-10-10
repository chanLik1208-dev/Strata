"""Tests for setup.py's --low-vram profile (8-12 GB NVIDIA cards, most laptops): which settings it picks for each card
size, and that a setting the user chose is never changed.  Pure functions - no GPU, no downloads, no prompts.

    python -m unittest tools.test_setup_low_vram
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import setup  # noqa: E402


class Profile(unittest.TestCase):
    def test_an_8gb_card(self):
        p = setup.low_vram_profile(7.99, False)
        self.assertEqual(p, {"context": 16384, "kv": "q4_0", "draft_vocab": "en"})

    def test_a_12gb_card_keeps_the_draft_subset(self):
        p = setup.low_vram_profile(11.99, False)
        self.assertEqual(p, {"context": 32768, "kv": "q4_0"})

    def test_bigger_cards_are_left_alone(self):
        for vram in (12.5, 16.0, 24.0, 0.0):
            self.assertEqual(setup.low_vram_profile(vram, True), {}, vram)

    def test_a_card_driving_the_display_keeps_room_for_it(self):
        p = setup.low_vram_profile(7.99, True)
        self.assertEqual(p["vram_reserve_mib"], setup.DISPLAY_RESERVE_MIB)

    def test_images_move_to_the_cpu_unless_gpu_was_chosen(self):
        self.assertEqual(setup.low_vram_profile(7.99, False, vision="yes")["vision"], "cpu")
        for vision in ("gpu", "cpu", "no", None):
            self.assertNotIn("vision", setup.low_vram_profile(7.99, False, vision=vision), vision)

    def test_explicit_choices_win(self):
        p = setup.low_vram_profile(7.99, True, context=65536, kv="int8", reserve=900)
        self.assertNotIn("context", p)
        self.assertNotIn("kv", p)
        self.assertNotIn("vram_reserve_mib", p)


class Laptop(unittest.TestCase):
    def test_names(self):
        self.assertTrue(setup.is_laptop_gpu({"name": "NVIDIA GeForce RTX 4060 Laptop GPU"}))
        self.assertFalse(setup.is_laptop_gpu({"name": "NVIDIA GeForce RTX 5070"}))
        self.assertFalse(setup.is_laptop_gpu({}))


if __name__ == "__main__":
    unittest.main()
