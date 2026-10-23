"""Collect Google Autocomplete suggestions for a project (see SKILL.md).

The crawl walks the suggestion "tree": a prefix is extended letter by letter only
when Google returned a full list (there is more underneath), and every relevant
suggestion becomes a new prefix itself (+ space). Every answer is cached in
SQLite, so a re-run replays the cache for free and continues where it stopped.

Usage:
  python suggest_collect.py --project DIR [--max-requests N] [--dry-run]
                            [--on-block stop|wait]

Exit codes: 0 finished or budget reached, 2 config error, 3 blocked by Google
(resume later), 4 network failure.
"""
import argparse
import codecs
import heapq
import itertools
import json
import random
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common import ConfigError, load_project, write_json_atomic
from textutils import Filters, normalize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "0.1.1"
# The only host this skill ever contacts. Redirects are refused, so it stays that way.
ENDPOINT = "https://suggestqueries.google.com/complete/search"
USER_AGENT = f"Mozilla/5.0 (compatible; semantic-core-expander/{VERSION})"
JITTER = (1.0, 1.4)  # random factor on the interval; never below 1, so the floor holds
FULL = 15         # client=chrome returns 15 suggestions when there are more
MIN_FULL = 8
MAX_LEN = 80
BATCH = 64
BLOCK_CODES = (429, 403, 503)
STOP_PAUSE = 300  # one shared pause before giving up in --on-block stop mode
MAX_SUGGESTIONS = 50
MAX_SUGGESTION_LEN = 200
MAX_CLIENT_ERRORS = 10  # consecutive 4xx answers before giving up
EMPTY = {"s": [], "rel": []}


class Blocked(Exception):
    pass


class NetworkFailure(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: a 3xx surfaces as HTTPError and is treated as a block."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _charset(headers):
    name = headers.get_content_charset() or "utf-8"
    try:
        codecs.lookup(name)
    except LookupError:
        return "utf-8"
    return name


class Fetcher:
    """Throttled, shared-backoff client for the autocomplete endpoint."""

    def __init__(self, gl, hl, interval, on_block, endpoint=ENDPOINT):
        self.gl, self.hl = gl, hl
        self.interval = interval
        self.on_block = on_block
        self.endpoint = endpoint
        self._opener = urllib.request.build_opener(_NoRedirect)
        self._lock = threading.Lock()
        self._next_slot = 0.0
        self._backoff = 0.0
        self._blocks = 0
        self._client_errors = 0

    def _throttle(self):
        with self._lock:
            now = time.time()
            start = max(now, self._next_slot, self._backoff)
            self._next_slot = start + self.interval * random.uniform(*JITTER)
        time.sleep(max(0.0, start - now))

    def _blocked(self, code):
        # One pause for all threads: a block is lifted only by time.
        with self._lock:
            if time.time() < self._backoff:
                return
            self._blocks += 1
            if self.on_block == "stop":
                if self._blocks > 1:
                    raise Blocked(code)
                wait = STOP_PAUSE
            else:
                if self._blocks > 4:
                    raise Blocked(code)
                wait = 600 * 2 ** (self._blocks - 1)
            self._backoff = time.time() + wait
            print(f"  ! HTTP {code}: pausing {wait // 60} min (block #{self._blocks})",
                  flush=True)

    def fetch(self, q):
        params = urllib.parse.urlencode({"client": "chrome", "hl": self.hl,
                                         "gl": self.gl, "q": q})
        req = urllib.request.Request(f"{self.endpoint}?{params}", headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": f"{self.hl},{self.hl.split('-')[0]};q=0.9",
        })
        for attempt in range(8):
            self._throttle()
            try:
                with self._opener.open(req, timeout=20) as r:
                    raw = r.read(1_000_000).decode(_charset(r.headers), "replace")
                data = parse_response(json.loads(raw))
                with self._lock:
                    self._blocks = self._client_errors = 0
                return data
            except urllib.error.HTTPError as e:
                if e.code in BLOCK_CODES or 300 <= e.code < 400:
                    self._blocked(e.code)
                elif 400 <= e.code < 500:
                    # This one query is unacceptable to Google: skip it, keep crawling.
                    with self._lock:
                        self._client_errors += 1
                        if self._client_errors >= MAX_CLIENT_ERRORS:
                            raise NetworkFailure(f"HTTP {e.code} for {MAX_CLIENT_ERRORS} "
                                                 "queries in a row")
                    return dict(EMPTY)
                else:
                    print(f"  ! HTTP {e.code}, retrying", flush=True)
                    time.sleep(5 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
                print(f"  ! network: {e}, retrying", flush=True)
                time.sleep(5 * (attempt + 1))
        raise NetworkFailure("no valid answer after 8 attempts")


def parse_response(data):
    """Validate the untrusted JSON: keep only a bounded list of strings."""
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        raise ValueError("unexpected response shape")
    sugg = [s[:MAX_SUGGESTION_LEN] for s in data[1][:MAX_SUGGESTIONS] if isinstance(s, str)]
    rel = []
    if len(data) > 4 and isinstance(data[4], dict):
        rel = [x for x in data[4].get("google:suggestrelevance", []) if isinstance(x, int)]
    return {"s": sugg, "rel": rel[:MAX_SUGGESTIONS]}


def open_cache(cfg):
    cfg["data_dir"].mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(cfg["data_dir"] / "cache.sqlite", check_same_thread=False)
    con.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, gl TEXT, hl TEXT, "
                "q TEXT, resp TEXT, ts REAL)")
    return con


def load_cached(con, gl, hl):
    rows = con.execute("SELECT q, resp FROM cache WHERE gl = ? AND hl = ?", (gl, hl))
    return dict(rows)


def cache_key(gl, hl, q):
    return f"{gl}|{hl}|{q}"


def initial_queue(cfg):
    p = cfg["profile"]
    word_start = list(dict.fromkeys(p["word_start"] + "0123456789"))
    seeds = [normalize(s, p) for s in cfg["seeds"]]
    core = [normalize(s, p) for s in cfg["core"]]
    q = []
    for s in seeds:
        q += [s, s + " "] + [f"{s} {c}" for c in word_start]
    for c in core:
        for m in cfg["modifiers"]:
            m = normalize(m, p)
            q += [f"{c} {m}", f"{m} {c}"]
        for w in cfg["questions"]:
            q.append(f"{normalize(w, p)} {c}")
    return list(dict.fromkeys(x for x in q if x.strip()))


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser(description="Collect Google Autocomplete suggestions.")
    ap.add_argument("--project", required=True, help="project directory with project.json")
    ap.add_argument("--max-requests", type=int, help="override limits.max_requests")
    ap.add_argument("--on-block", choices=["stop", "wait"], default="stop",
                    help="stop: one 5-min pause, then exit 3; wait: up to ~2.5 h of pauses")
    ap.add_argument("--dry-run", action="store_true", help="validate and show the plan only")
    args = ap.parse_args(argv)

    try:
        cfg = load_project(args.project)
    except (ConfigError, json.JSONDecodeError) as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2
    lim = cfg["limits"]
    budget = args.max_requests if args.max_requests is not None else lim["max_requests"]
    if not 0 <= budget <= 200000:
        print("Config error: --max-requests must be between 0 and 200000", file=sys.stderr)
        return 2
    flt = Filters(cfg)
    profile = cfg["profile"]
    letters = list(profile["letters"])
    word_start = list(dict.fromkeys(profile["word_start"] + "0123456789"))

    con = open_cache(cfg)
    cached = load_cached(con, cfg["gl"], cfg["hl"])
    start_q = initial_queue(cfg)
    if cfg["roots_defaulted"]:
        print("Note: 'roots' not set, using seeds as relevance roots.", flush=True)
    for stem, hits in flt.exclude_conflicts(cfg):
        print(f"Warning: exclude stem '{stem}' also matches your own words: "
              f"{', '.join(hits[:5])}. Make it longer or use exclude.regex.", flush=True)

    if args.dry_run:
        todo = sum(1 for q in start_q if q not in cached)
        rate = min(lim["workers"] * 2.0, 1.0 / (lim["interval"] * sum(JITTER) / 2))
        print(f"gl={cfg['gl']} hl={cfg['hl']} language={cfg['language']} "
              f"roots={len(cfg['roots'])}")
        print(f"Start queries: {len(start_q)} ({todo} not cached), cached answers: {len(cached)}")
        print(f"Budget: {budget} requests, ~{rate:.1f} req/s -> up to "
              f"~{budget / rate / 60:.0f} min")
        print("Sample:", "; ".join(start_q[:: max(1, len(start_q) // 10)][:10]))
        return 0

    fetcher = fetcher or Fetcher(cfg["gl"], cfg["hl"], lim["interval"], args.on_block)
    status_path = cfg["data_dir"] / "status.json"
    started = time.time()
    status = {"state": "running", "project": cfg["project"], "gl": cfg["gl"],
              "hl": cfg["hl"], "budget": budget, "started": started}

    # Priority queue: start queries first, then shorter (broader) prefixes.
    counter = itertools.count()
    queue = [(0, next(counter), q) for q in start_q]
    seen = set(start_q)

    def push(q):
        if q not in seen:
            seen.add(q)
            heapq.heappush(queue, (len(q), next(counter), q))

    found, network, processed, deferred = set(), 0, 0, 0
    max_seen = 0
    state, exit_code = "done", 0

    def get(q):
        if q in cached:
            return q, json.loads(cached[q]), False
        return q, fetcher.fetch(q), True

    def save_status(extra=None):
        status.update({"processed": processed, "network": network,
                       "queue": len(queue) + deferred,
                       "found": len(found), "updated": time.time(),
                       "rate": round(network / max(1.0, time.time() - started), 2)})
        if extra:
            status.update(extra)
        write_json_atomic(status_path, status)

    save_status()
    try:
        with ThreadPoolExecutor(lim["workers"]) as pool:
            while queue:
                batch, budget_left = [], budget - network
                while queue and len(batch) < BATCH:
                    q = heapq.heappop(queue)[2]
                    if q not in cached:
                        if budget_left <= 0:
                            deferred += 1  # left for the next run
                            continue
                        budget_left -= 1
                    batch.append(q)
                if not batch:
                    state = "budget_reached"
                    break
                futures = [pool.submit(get, q) for q in batch]
                results, failure = [], None
                for fut in futures:
                    try:
                        results.append(fut.result())
                    except (Blocked, NetworkFailure) as e:
                        failure = failure or e
                new_rows = []
                for q, resp, remote in results:
                    processed += 1
                    if remote:
                        network += 1
                        cached[q] = json.dumps(resp, ensure_ascii=False)
                        new_rows.append((cache_key(cfg["gl"], cfg["hl"], q), cfg["gl"],
                                         cfg["hl"], q, cached[q], time.time()))
                    sugg = [normalize(s, profile) for s in resp["s"]]
                    max_seen = max(max_seen, len(sugg))
                    for s in sugg:
                        if flt.relevant(s):
                            found.add(s)
                        if len(s.split()) < lim["max_words"] and flt.keep_expanding(s):
                            push(s + " ")
                    # A full list means more lies under this prefix: go one letter deeper.
                    full = len(sugg) >= max(MIN_FULL, min(FULL, max_seen))
                    if full and len(q) < MAX_LEN and flt.keep_expanding(q.strip() or q):
                        for c in (word_start if q.endswith(" ") else letters):
                            push(q + c)
                if new_rows:
                    con.executemany("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?)",
                                    new_rows)
                    con.commit()
                    print(f"processed {processed}, network {network} "
                          f"({network / max(1.0, time.time() - started):.1f}/s), "
                          f"queue {len(queue) + deferred}, phrases {len(found)}", flush=True)
                if failure:
                    # Unanswered queries were never cached, so a re-run retries them.
                    if isinstance(failure, Blocked):
                        state, exit_code = "blocked", 3
                        print("Google is blocking requests. Answers so far are cached; "
                              "run again later and the crawl resumes from the cache.",
                              flush=True)
                    else:
                        state, exit_code = "network_error", 4
                        print(f"Network failure ({failure}). Answers so far are cached.",
                              flush=True)
                    break
                save_status()
    except BaseException as e:
        # Leave an honest status behind instead of a stale "running".
        state = "interrupted" if isinstance(e, KeyboardInterrupt) else "error"
        save_status({"state": state, "error": type(e).__name__, "finished": time.time()})
        con.close()
        raise

    if state == "done" and (queue or deferred):
        state = "budget_reached"
    save_status({"state": state, "finished": time.time()})
    con.close()
    print(f"{state.upper()}: processed {processed}, network {network}, "
          f"queue left {len(queue) + deferred}, "
          f"relevant phrases {len(found)}", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
