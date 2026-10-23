"""Normalisation, tokenising and the language / relevance filters.

Everything here is driven by a language profile (scripts/langs.json) and the
project config, so the same code serves any niche, country and language.
"""
import re
import unicodedata

APOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "´": "'", "‘": "'"})
TOKEN = re.compile(r"[^\W_]+(?:['-][^\W_]+)*")
REPEATS = re.compile(r"([^\W\d_])\1{3,}")
# Zero-width (non-)joiners are part of normal spelling in some scripts; keep them.
KEEP_FORMAT = {"‌", "‍"}


def strip_controls(text):
    """Drop control, format (bidi overrides, zero-width) and private-use characters.

    Suggestions are untrusted text: an ANSI escape or U+202E could rewrite a
    terminal line or flip how a phrase is displayed in a spreadsheet.
    """
    out = []
    for ch in text:
        if ch.isspace():
            out.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cs") and ch not in KEEP_FORMAT:
            continue
        else:
            out.append(ch)
    return "".join(out)


def normalize(q, profile=None):
    q = strip_controls(unicodedata.normalize("NFC", q)).lower().translate(APOS)
    q = re.sub(r"\s+", " ", q).strip()
    fix = profile.get("apostrophe_fix") if profile else None
    if fix:
        # Google often returns a lost apostrophe as a space: "пам ятки" -> "пам'ятки".
        q = re.sub(fix, lambda m: m.group(1) + "'", q)
    return q


def tokens(q):
    return TOKEN.findall(q)


def scripts_of(text):
    """Set of Unicode script names (LATIN, CYRILLIC, ...) of the letters in text."""
    out = set()
    for ch in text:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            if name:
                out.add(name.split(" ")[0])
    return out


class Filters:
    """Relevance and language checks for one project."""

    def __init__(self, cfg):
        self.profile = cfg["profile"]
        self.excluded = cfg["excluded"]
        self.roots = [normalize(r, self.profile) for r in cfg["roots"]]
        own_letters = set(self.profile["letters"])
        self.allow = {normalize(w, self.profile) for w in cfg.get("allow_words", [])}
        own_words = (set(self.profile["markers"]["words"]) | set(self.profile["stopwords"])
                     | set(self.profile["questions"]) | self.allow)
        self.foreign = []
        for code, p in self.excluded.items():
            m = p["markers"]
            self.foreign.append({
                "code": code,
                "script": p["script"],
                "chars": set(m["chars"]) - own_letters,
                "words": set(m["words"]) - own_words,
                "suffix": re.compile(m["suffix_regex"]) if m["suffix_regex"] else None,
                "except": set(m["suffix_except"]),
            })
        self.own_exclusive = set(self.profile["exclusive_chars"])
        clean = cfg["cleaning"]
        self.adult = list(self.profile["adult_stems"]) if clean["filter_adult"] else []
        self.ex_stems = [normalize(s, self.profile) for s in cfg["exclude_stems"]]
        self.ex_regex = cfg["exclude_regex"]
        self.max_words = clean["max_words"]
        self.drop_trailing = clean["drop_trailing_single_letter"]

    def relevant(self, q):
        return any(r in q for r in self.roots)

    def wrong_script(self, q):
        s = scripts_of(q)
        return bool(s) and self.profile["script"] not in s

    def foreign_reason(self, q):
        """'<lang> (<marker>)' when q looks like an excluded language, else None."""
        chars = set(q)
        for f in self.foreign:
            hit = chars & f["chars"]
            if hit:
                return f"{f['code']} ({''.join(sorted(hit))})"
        for t in tokens(q):
            if t in self.allow or set(t) & self.own_exclusive:
                continue  # allowed explicitly, or carries letters only our language has
            t_scripts = scripts_of(t)
            for f in self.foreign:
                if f["script"] not in t_scripts:
                    continue
                if t in f["words"]:
                    return f"{f['code']} ({t})"
                if (f["suffix"] and len(t) > 3 and t not in f["except"]
                        and f["suffix"].search(t)):
                    return f"{f['code']} ({t})"
        return None

    def project_excluded(self, q):
        words = q.split()
        for s in self.ex_stems:
            if (" " in s and s in q) or any(w.startswith(s) for w in words):
                return f"project exclude ({s})"
        for rx in self.ex_regex:
            if rx.search(q):
                return f"project exclude regex ({rx.pattern})"
        return None

    def exclude_conflicts(self, cfg):
        """Exclude stems that would also hit words of the project's own seeds,
        core forms or modifiers (e.g. stem "львов" also matches "львові")."""
        words = set()
        for key in ("seeds", "core", "modifiers"):
            for phrase in cfg[key]:
                words.update(normalize(phrase, self.profile).split())
        out = []
        for s in self.ex_stems:
            hits = sorted(w for w in words if (" " not in s and w.startswith(s)))
            if hits:
                out.append((s, hits))
        return out

    def keep_expanding(self, q):
        """Should a suggestion become a new prefix for the crawl?"""
        return (self.relevant(q) and not self.wrong_script(q)
                and self.foreign_reason(q) is None and self.project_excluded(q) is None)

    def offtopic_reason(self, q):
        words = q.split()
        for s in self.adult:
            if (" " in s and s in q) or any(w.startswith(s) for w in words):
                return f"adult / profanity ({s})"
        r = self.project_excluded(q)
        if r:
            return r
        if (self.drop_trailing and len(words) > 1 and len(words[-1]) == 1
                and words[-1].isalpha() and not words[-2].isdigit()):
            return "truncated fragment (ends with a single letter)"
        if len(words) > self.max_words:
            return f"too long (> {self.max_words} words)"
        if REPEATS.search(q):
            return "junk (repeated characters)"
        return None

    def reject_reason(self, q):
        """Full cleaning verdict for a relevant phrase: None means keep."""
        if self.wrong_script(q):
            return "wrong script"
        r = self.foreign_reason(q)
        if r:
            return f"foreign language: {r}"
        return self.offtopic_reason(q)
