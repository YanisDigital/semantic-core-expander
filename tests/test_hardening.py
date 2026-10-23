"""Regression tests for the 0.1.1 security / robustness fixes (local only)."""
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from helpers import FakeFetcher, make_project
import build_zip
import clean_export
import suggest_collect
from common import ConfigError, load_project
from textutils import normalize, strip_controls


class Handler(BaseHTTPRequestHandler):
    """Answers by the first query letter: r=redirect, b=400, c=odd charset, else JSON."""
    hits = []

    def do_GET(self):
        q = self.path.split("q=", 1)[-1]
        Handler.hits.append(q)
        if q.startswith("r"):
            self.send_response(302)
            self.send_header("Location", "http://example.org/sorry")
            self.end_headers()
        elif q.startswith("b"):
            self.send_response(400)
            self.end_headers()
        else:
            body = json.dumps([q, [q + " one", q + " two"]]).encode()
            self.send_response(200)
            ctype = "x-unknown-charset" if q.startswith("c") else "utf-8"
            self.send_header("Content-Type", f"application/json; charset={ctype}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/complete/search"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Handler.hits = []
        self._pause = suggest_collect.STOP_PAUSE
        suggest_collect.STOP_PAUSE = 0

    def tearDown(self):
        suggest_collect.STOP_PAUSE = self._pause

    def fetcher(self):
        return suggest_collect.Fetcher("us", "en", 0.3, "stop", endpoint=self.url)

    def test_redirect_is_a_block_and_never_followed(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(suggest_collect.Blocked):
                self.fetcher().fetch("redirect me")
        self.assertEqual(len(Handler.hits), 2)  # one pause, one retry, then stop

    def test_client_error_skips_query(self):
        self.assertEqual(self.fetcher().fetch("bad"), {"s": [], "rel": []})

    def test_repeated_client_errors_stop(self):
        f = self.fetcher()
        with self.assertRaises(suggest_collect.NetworkFailure):
            for _ in range(suggest_collect.MAX_CLIENT_ERRORS):
                f.fetch("bad")

    def test_unknown_charset_falls_back(self):
        self.assertEqual(self.fetcher().fetch("charset")["s"], ["charset one", "charset two"])

    def test_jitter_never_shortens_interval(self):
        self.assertGreaterEqual(suggest_collect.JITTER[0], 1.0)

    def test_user_agent_version(self):
        self.assertIn(suggest_collect.VERSION, suggest_collect.USER_AGENT)


class ControlCharsTest(unittest.TestCase):
    def test_strip(self):
        s = "dentist \x1b[2J\x1b[31mred‮evil​"
        self.assertEqual(normalize(s), "dentist [2j[31mredevil")
        self.assertEqual(strip_controls("a\tb\nc"), "a b c")

    def test_keeps_joiners(self):
        self.assertEqual(normalize("می‌خواهم"), "می‌خواهم")


class StatusAndConfigTest(unittest.TestCase):
    def test_crash_leaves_error_status(self):
        proj = make_project({})

        class Boom(FakeFetcher):
            def fetch(self, q):
                raise RuntimeError("boom")

        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                suggest_collect.main(["--project", str(proj)], fetcher=Boom({}))
        status = json.loads((proj / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "error")
        self.assertEqual(status["error"], "RuntimeError")

    def test_bad_cluster_labels(self):
        proj = make_project({})
        with contextlib.redirect_stdout(io.StringIO()):
            suggest_collect.main(["--project", str(proj)], fetcher=FakeFetcher({}))
        for bad in ("[1, 2]", '{"labels": ["x"]}', '{"ignore_stems": "x"}'):
            (proj / "cluster_labels.json").write_text(bad, encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(clean_export.main(["--project", str(proj)]), 2, bad)

    def test_symlinked_data_dir_is_refused(self):
        proj = make_project({})
        outside = Path(tempfile.mkdtemp())
        try:
            os.symlink(outside, proj / "data", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not permitted here")
        with self.assertRaises(ConfigError):
            load_project(proj)


class PrivacyScanTest(unittest.TestCase):
    def scan(self, name, data):
        root = Path(tempfile.mkdtemp())
        (root / name).write_bytes(data)
        return build_zip.privacy_scan(root)

    def test_flags_documents_metadata_and_unknown_types(self):
        self.assertTrue(self.scan("brief.docx", b"PK"))
        self.assertTrue(self.scan("shot.jpg", b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00MM"))
        self.assertTrue(self.scan("shot.png", b"\x89PNG....tEXtAuthor\x00me"))
        self.assertTrue(self.scan("blob.bin", b"\x00\x01"))

    def test_clean_image_passes(self):
        self.assertEqual(self.scan("ok.png", b"\x89PNG\r\n\x1a\nIHDR....IDAT....IEND"), [])


if __name__ == "__main__":
    unittest.main()
