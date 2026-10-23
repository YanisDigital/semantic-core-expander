import tempfile
import unittest
import zipfile
from pathlib import Path

import helpers  # noqa: F401  (sets sys.path)
import build_zip


class BuildZipTest(unittest.TestCase):
    def test_skill_is_valid(self):
        self.assertEqual(build_zip.validate_skill(), [])

    def test_zip_layout(self):
        out = Path(tempfile.mkdtemp())
        zpath, digest, _ = build_zip.build("vtest", out)
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
        self.assertTrue(all(n.startswith("semantic-core-expander/") for n in names))
        for must in ["SKILL.md", "LICENSE", "scripts/suggest_collect.py",
                     "scripts/langs.json", "assets/project.example.json"]:
            self.assertIn(f"semantic-core-expander/{must}", names)
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".pyc")])
        self.assertEqual(len(digest), 64)
        # Deterministic: same sources, same bytes.
        zpath2, digest2, _ = build_zip.build("vtest", Path(tempfile.mkdtemp()))
        self.assertEqual(digest, digest2)

    def test_privacy_scan_flags_problems(self):
        root = Path(tempfile.mkdtemp())
        (root / "notes.md").write_text(
            "contact: someone" + "@" + "gmail.com\n"
            "path: C:" + "\\Users\\someone\\x\n"
            "ok: dev" + "@" + "example.com\n", encoding="utf-8")
        (root / "cache.sqlite").write_bytes(b"x")
        problems = build_zip.privacy_scan(root)
        self.assertTrue(any("email" in p for p in problems))
        self.assertTrue(any("Windows user path" in p for p in problems))
        self.assertTrue(any("data file" in p for p in problems))
        self.assertEqual(sum("email" in p for p in problems), 1)

    def test_repository_is_clean(self):
        self.assertEqual(build_zip.privacy_scan(), [])


if __name__ == "__main__":
    unittest.main()
