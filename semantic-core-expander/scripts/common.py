"""Project config loading, validation and safe file helpers shared by the scripts.

A project is a directory with a project.json (see references/config.md). Every
file the scripts write goes into that directory: data/ for the cache and status,
output/ for the deliverables. Nothing is written next to the skill itself.
"""
import json
import os
import re
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
LANGS_PATH = Path(__file__).resolve().parent / "langs.json"

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
COUNTRY = re.compile(r"^[a-z]{2}$")
LANG_CODE = re.compile(r"^[a-z]{2,3}(-[a-z]{2,4})?$")
MAX_PHRASE = 120
MAX_LIST = 2000

DEFAULT_LIMITS = {"max_requests": 3000, "workers": 2, "interval": 0.4, "max_words": 7}
# Hard caps keep the request rate polite no matter what the config says.
MIN_INTERVAL, MAX_WORKERS, MAX_REQUESTS = 0.3, 4, 200000

DEFAULT_CLEANING = {"max_words": 10, "filter_adult": True, "merge_word_order": True,
                    "drop_trailing_single_letter": None, "min_cluster_size": 3}


class ConfigError(ValueError):
    pass


def _str_list(cfg, key, required=False):
    val = cfg.get(key, [])
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        raise ConfigError(f"'{key}' must be a list of strings")
    val = [x.strip() for x in val if x.strip()]
    if required and not val:
        raise ConfigError(f"'{key}' must not be empty")
    if len(val) > MAX_LIST:
        raise ConfigError(f"'{key}' has more than {MAX_LIST} items")
    for x in val:
        if len(x) > MAX_PHRASE:
            raise ConfigError(f"'{key}' item is longer than {MAX_PHRASE} chars: {x[:40]}...")
    return val


def _number(d, key, lo, hi, cast):
    try:
        v = cast(d[key])
    except (TypeError, ValueError):
        raise ConfigError(f"limits.{key} must be a number")
    if not lo <= v <= hi:
        raise ConfigError(f"limits.{key} must be between {lo} and {hi}")
    return v


def load_profiles():
    with open(LANGS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def build_profile(lang, profiles, override=None):
    """Profile for `lang`, optionally patched or fully defined by `override`."""
    base = dict(profiles.get(lang, {}))
    if override:
        if not isinstance(override, dict):
            raise ConfigError("'language_profile' must be an object")
        base.update(override)
    missing = [k for k in ("script", "letters", "word_start") if not base.get(k)]
    if missing:
        raise ConfigError(f"no language profile '{lang}' in langs.json; define "
                          f"'language_profile' with at least: {', '.join(missing)} "
                          "(see references/languages.md)")
    base.setdefault("exclusive_chars", "")
    base.setdefault("stem_len", 6)
    base.setdefault("questions", [])
    base.setdefault("stopwords", [])
    base.setdefault("adult_stems", [])
    base.setdefault("drop_trailing_single_letter", False)
    base.setdefault("markers", {})
    for k in ("chars", "suffix_regex"):
        base["markers"].setdefault(k, "")
    for k in ("words", "suffix_except"):
        base["markers"].setdefault(k, [])
    for key in ("apostrophe_fix",):
        if base.get(key):
            re.compile(base[key])
    if base["markers"]["suffix_regex"]:
        re.compile(base["markers"]["suffix_regex"])
    base["script"] = base["script"].upper()
    return base


def load_project(project_dir):
    """Read and validate <project_dir>/project.json, fill defaults."""
    root = Path(project_dir).resolve()
    path = root / "project.json"
    if not path.is_file():
        raise ConfigError(f"{path} not found (copy assets/project.example.json)")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ConfigError("project.json must be an object")

    slug = str(cfg.get("project", "")).strip().lower()
    if not SLUG.match(slug):
        raise ConfigError("'project' must be a slug: lowercase letters, digits, - or _")
    gl = str(cfg.get("gl", "")).strip().lower()
    hl = str(cfg.get("hl", "")).strip().lower()
    if not COUNTRY.match(gl):
        raise ConfigError("'gl' must be a 2-letter country code, e.g. us, de, ua")
    if not LANG_CODE.match(hl):
        raise ConfigError("'hl' must be a language code, e.g. en, de, uk, pt-br")
    lang = str(cfg.get("language", hl.split("-")[0])).strip().lower()

    profiles = load_profiles()
    profile = build_profile(lang, profiles, cfg.get("language_profile"))
    excluded = {}
    for code in _str_list(cfg, "exclude_languages"):
        code = code.lower()
        if code == lang:
            raise ConfigError("'exclude_languages' must not contain the project language")
        if code not in profiles:
            raise ConfigError(f"unknown language in exclude_languages: {code}")
        excluded[code] = build_profile(code, profiles)

    limits = dict(DEFAULT_LIMITS)
    limits.update(cfg.get("limits") or {})
    limits["max_requests"] = _number(limits, "max_requests", 1, MAX_REQUESTS, int)
    limits["workers"] = _number(limits, "workers", 1, MAX_WORKERS, int)
    limits["interval"] = _number(limits, "interval", MIN_INTERVAL, 60, float)
    limits["max_words"] = _number(limits, "max_words", 2, 15, int)

    cleaning = dict(DEFAULT_CLEANING)
    cleaning.update(cfg.get("cleaning") or {})
    if cleaning["drop_trailing_single_letter"] is None:
        cleaning["drop_trailing_single_letter"] = bool(profile["drop_trailing_single_letter"])
    cleaning["max_words"] = _number(cleaning, "max_words", 2, 30, int)
    cleaning["min_cluster_size"] = _number(cleaning, "min_cluster_size", 1, 1000, int)

    exclude = cfg.get("exclude") or {}
    if not isinstance(exclude, dict):
        raise ConfigError("'exclude' must be an object with 'stems' and/or 'regex'")
    ex_stems = _str_list(exclude, "stems")
    ex_regex = []
    for rx in _str_list(exclude, "regex"):
        try:
            ex_regex.append(re.compile(rx))
        except re.error as e:
            raise ConfigError(f"bad exclude.regex '{rx}': {e}")

    seeds = _str_list(cfg, "seeds", required=True)
    roots = _str_list(cfg, "roots")
    return {
        "dir": root,
        # Resolved and checked, so a symlinked data/ or output/ cannot point elsewhere.
        "data_dir": inside(root, root / "data"),
        "output_dir": inside(root, root / "output"),
        "project": slug,
        "site": str(cfg.get("site", "")),
        "goal": str(cfg.get("goal", "")),
        "gl": gl,
        "hl": hl,
        "language": lang,
        "profile": profile,
        "excluded": excluded,
        "seeds": seeds,
        "core": _str_list(cfg, "core") or seeds,
        "modifiers": _str_list(cfg, "modifiers"),
        "questions": _str_list(cfg, "questions") or list(profile["questions"]),
        "roots": roots or seeds,
        "roots_defaulted": not roots,
        "exclude_stems": ex_stems,
        "allow_words": [w.lower() for w in _str_list(cfg, "allow_words")],
        "exclude_regex": ex_regex,
        "limits": limits,
        "cleaning": cleaning,
    }


def inside(base, path):
    """Resolve `path` and make sure it stays inside `base` (no traversal)."""
    base = Path(base).resolve()
    p = Path(path).resolve()
    if p != base and base not in p.parents:
        raise ConfigError(f"refusing to write outside the project directory: {p}")
    return p


def write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Neutralise spreadsheet formula injection in CSV cells (OWASP)."""
    if isinstance(value, str) and value.startswith(FORMULA_START):
        return "'" + value
    return value
