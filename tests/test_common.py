import tempfile
import unittest
from pathlib import Path

from helpers import make_project
from common import ConfigError, csv_safe, inside, load_project


class ConfigTest(unittest.TestCase):
    def bad(self, **cfg):
        with self.assertRaises(ConfigError):
            load_project(make_project(cfg))

    def test_defaults(self):
        cfg = load_project(make_project({}))
        self.assertEqual(cfg["language"], "en")
        self.assertEqual(cfg["core"], ["dentist"])
        self.assertTrue(cfg["questions"])
        self.assertFalse(cfg["cleaning"]["drop_trailing_single_letter"])

    def test_validation(self):
        self.bad(project="../evil")
        self.bad(gl="usa")
        self.bad(hl="english")
        self.bad(seeds=[])
        self.bad(seeds="dentist")
        self.bad(seeds=["x" * 500])
        self.bad(exclude_languages=["en"])
        self.bad(exclude_languages=["xx"])
        self.bad(exclude={"regex": ["("]})
        self.bad(language="xx")

    def test_rate_caps(self):
        self.bad(limits={"interval": 0.05})
        self.bad(limits={"workers": 32})
        self.bad(limits={"max_requests": 10 ** 9})

    def test_inline_language_profile(self):
        cfg = load_project(make_project({
            "hl": "cs", "language": "cs",
            "language_profile": {"script": "latin", "letters": "abc", "word_start": "ab"}}))
        self.assertEqual(cfg["profile"]["script"], "LATIN")

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_project(tempfile.mkdtemp())


class SafetyTest(unittest.TestCase):
    def test_inside(self):
        base = Path(tempfile.mkdtemp())
        self.assertEqual(inside(base, base / "output" / "x.csv"), (base / "output" / "x.csv").resolve())
        with self.assertRaises(ConfigError):
            inside(base, base / ".." / "escape.csv")

    def test_csv_safe(self):
        for v in ["=1+1", "+cmd", "-2", "@SUM(A1)", "\tx"]:
            self.assertTrue(csv_safe(v).startswith("'"), v)
        self.assertEqual(csv_safe("dentist"), "dentist")
        self.assertEqual(csv_safe(5), 5)


if __name__ == "__main__":
    unittest.main()
