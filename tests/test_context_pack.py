"""Tests for advisors.context_pack (Lisa Console v1, Phase C2).

Hermetic: builds its own tmp docs/GPT_CONTEXT-shaped directory per test,
never reads the real ~/Lisa/docs/GPT_CONTEXT.

Run: PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_context_pack -v
"""

from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path

from advisors.context_pack import ContextPackError, load_context_pack


class ContextPackTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-context-pack-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestLoadContextPack(ContextPackTestCase):
    def test_missing_directory_raises(self) -> None:
        with self.assertRaises(ContextPackError):
            load_context_pack(self.tmp / "does-not-exist")

    def test_empty_directory_raises(self) -> None:
        with self.assertRaises(ContextPackError):
            load_context_pack(self.tmp)

    def test_non_numbered_files_ignored(self) -> None:
        (self.tmp / "README.md").write_text("index, not context")
        (self.tmp / "CHANGELOG.md").write_text("revision log, not context")
        with self.assertRaises(ContextPackError):
            load_context_pack(self.tmp)

    def test_files_loaded_in_numeric_order(self) -> None:
        (self.tmp / "02_second.md").write_text("SECOND")
        (self.tmp / "01_first.md").write_text("FIRST")
        (self.tmp / "09_last.md").write_text("LAST")
        pack = load_context_pack(self.tmp)
        self.assertLess(pack.text.index("FIRST"), pack.text.index("SECOND"))
        self.assertLess(pack.text.index("SECOND"), pack.text.index("LAST"))
        self.assertEqual([f.order for f in pack.files], [1, 2, 3])

    def test_meta_files_excluded_from_text(self) -> None:
        (self.tmp / "01_first.md").write_text("REAL CONTEXT")
        (self.tmp / "README.md").write_text("SHOULD NOT APPEAR")
        pack = load_context_pack(self.tmp)
        self.assertIn("REAL CONTEXT", pack.text)
        self.assertNotIn("SHOULD NOT APPEAR", pack.text)


class TestCaching(ContextPackTestCase):
    def test_cached_object_returned_when_unchanged(self) -> None:
        (self.tmp / "01_first.md").write_text("v1")
        first = load_context_pack(self.tmp)
        second = load_context_pack(self.tmp)
        self.assertIs(first, second)

    def test_cache_invalidated_on_content_change(self) -> None:
        f = self.tmp / "01_first.md"
        f.write_text("v1")
        first = load_context_pack(self.tmp)
        self.assertIn("v1", first.text)

        time.sleep(0.01)
        f.write_text("v2 -- changed")
        second = load_context_pack(self.tmp)
        self.assertIn("v2 -- changed", second.text)
        self.assertNotIn("v1", second.text.replace("v2 -- changed", ""))

    def test_force_reload_bypasses_cache_object_identity(self) -> None:
        (self.tmp / "01_first.md").write_text("v1")
        first = load_context_pack(self.tmp)
        second = load_context_pack(self.tmp, force_reload=True)
        self.assertEqual(first.text, second.text)


if __name__ == "__main__":
    unittest.main()
