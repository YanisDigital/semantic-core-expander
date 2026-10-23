"""Shared fixtures: import path, temporary projects and a fake fetcher."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "semantic-core-expander" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tools"))


def make_project(cfg, tmp=None):
    """Write project.json into a fresh temp dir and return its path."""
    d = Path(tmp or tempfile.mkdtemp(prefix="sce-test-")) / "proj"
    d.mkdir(parents=True, exist_ok=True)
    base = {"project": "test", "gl": "us", "hl": "en", "seeds": ["dentist"],
            "roots": ["dentist"], "limits": {"workers": 1, "interval": 0.3}}
    base.update(cfg)
    (d / "project.json").write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    return d


class FakeFetcher:
    """Answers from a dict; unknown prefixes get an empty list."""

    def __init__(self, answers, fail_after=None, exc=None):
        self.answers = answers
        self.calls = []
        self.fail_after = fail_after
        self.exc = exc

    def fetch(self, q):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise self.exc
        self.calls.append(q)
        return {"s": list(self.answers.get(q, [])), "rel": []}
