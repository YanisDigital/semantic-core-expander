"""Build the release zip of the skill and run the repository privacy scan.

  python tools/build_zip.py --version v0.1.0   # dist/semantic-core-expander-v0.1.0.zip (+ .sha256)
  python tools/build_zip.py --check            # privacy scan + SKILL.md validation only

The zip holds exactly one top-level folder, semantic-core-expander/, with an
allowlisted set of files, so caches, exports or stray files can never ship.
Entries are sorted and timestamps fixed, so the same sources give the same zip.
"""
import argparse
import fnmatch
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = "semantic-core-expander"
SKILL_DIR = ROOT / SKILL
ALLOW = ["SKILL.md", "scripts/*.py", "scripts/langs.json", "references/*.md",
         "assets/*.json"]
EXTRA = {"LICENSE": ROOT / "LICENSE"}  # copied into the skill folder in the zip
FIXED_TIME = (2020, 1, 1, 0, 0, 0)

SKIP_DIRS = {".git", "dist", "__pycache__", "semantic-core", ".venv", "venv", "node_modules"}
DATA_EXT = {".sqlite", ".sqlite3", ".db", ".xlsx", ".xls", ".csv", ".log", ".zip", ".pyc"}
TEXT_EXT = {".py", ".md", ".json", ".yml", ".yaml", ".txt", ".toml", ".cfg", ".ini", ""}
# Patterns are assembled from pieces so this file does not flag itself.
PRIVACY = [
    ("email address", re.compile(r"[\w.+-]+" + "@" + r"[\w-]+\.[\w.-]+")),
    ("Windows user path", re.compile(r"[A-Za-z]:[\\/]+" + "Users" + r"[\\/]+\w", re.I)),
    ("Unix home path", re.compile(r"/(?:home|" + "Users" + r")/[a-z][\w.-]+/", re.I)),
    ("private key", re.compile("-----BEGIN [A-Z ]*" + "PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{30,}")),
    ("API key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,})")),
]
EMAIL_OK = re.compile(r"@(example\.(com|org|net)|users\.noreply\.github\.com)$", re.I)


def iter_repo_files(root):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS):
            yield p


def privacy_scan(root=ROOT):
    """List of 'path:line: problem' strings; empty means clean."""
    problems = []
    for p in iter_repo_files(root):
        rel = p.relative_to(root).as_posix()
        if p.suffix.lower() in DATA_EXT:
            problems.append(f"{rel}: data file in the repository ({p.suffix})")
            continue
        if p.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text")
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for label, rx in PRIVACY:
                for m in rx.finditer(line):
                    if label == "email address" and EMAIL_OK.search(m.group(0)):
                        continue
                    problems.append(f"{rel}:{n}: {label}")
    return problems


def frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        raise ValueError("SKILL.md has no frontmatter")
    out = {}
    for line in m.group(1).splitlines():
        if line.strip() and not line.startswith(" "):
            key, _, val = line.partition(":")
            out[key.strip()] = val.strip()
    return out


def validate_skill(skill_dir=SKILL_DIR):
    fm = frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    errors = []
    allowed = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
    if set(fm) - allowed:
        errors.append(f"unexpected frontmatter keys: {sorted(set(fm) - allowed)}")
    if fm.get("name") != skill_dir.name:
        errors.append("frontmatter name must equal the folder name")
    desc = fm.get("description", "")
    if not desc or len(desc) > 1024 or "<" in desc or ">" in desc:
        errors.append("description must be 1-1024 chars without angle brackets")
    if len(fm.get("compatibility", "")) > 500:
        errors.append("compatibility must be at most 500 chars")
    return errors


def skill_files(skill_dir=SKILL_DIR):
    files, ignored = {}, []
    for p in iter_repo_files(skill_dir):
        rel = p.relative_to(skill_dir).as_posix()
        if any(fnmatch.fnmatch(rel, pat) and rel.count("/") == pat.count("/") for pat in ALLOW):
            files[rel] = p
        else:
            ignored.append(rel)
    for rel, p in EXTRA.items():
        files[rel] = p
    return dict(sorted(files.items())), ignored


def build(version, out_dir):
    files, ignored = skill_files()
    for rel in ignored:
        print(f"  not packaged: {rel}")
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"{SKILL}-{version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, p in files.items():
            info = zipfile.ZipInfo(f"{SKILL}/{rel}", date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            data = p.read_bytes().replace(b"\r\n", b"\n")
            z.writestr(info, data)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    (out_dir / f"{zpath.name}.sha256").write_text(f"{digest}  {zpath.name}\n", encoding="utf-8")
    return zpath, digest, list(files)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", default="dev", help="version label, e.g. v0.1.0")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--check", action="store_true", help="scan and validate only")
    args = ap.parse_args(argv)
    if not re.match(r"^[\w.-]{1,40}$", args.version):
        print("bad --version", file=sys.stderr)
        return 2

    problems = privacy_scan() + [f"SKILL.md: {e}" for e in validate_skill()]
    if problems:
        print("Release blocked:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print("Privacy scan and SKILL.md validation passed.")
    if args.check:
        return 0
    zpath, digest, names = build(args.version, Path(args.out))
    print(f"Built {zpath} ({len(names)} files)\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
