# Language profiles

`scripts/langs.json` holds one profile per language: en, uk, ru, de, fr, es,
it, pl, pt, nl. A profile tells the scripts which letters to type, which script
a phrase must be written in, how to spot this language when another project
excludes it, and which words to ignore when clustering.

## Fields

| Field | Meaning |
|---|---|
| `script` | Unicode script of the language: `LATIN`, `CYRILLIC`, `GREEK`, `ARABIC`, `HEBREW`, `DEVANAGARI`, `HANGUL`, `CJK`... A phrase with letters but none in this script is rejected as "wrong script". |
| `letters` | Alphabet typed after a full prefix inside a word. |
| `word_start` | Letters typed at the start of a new word (digits are added automatically). Leave out letters that never start words, it saves requests. |
| `exclusive_chars` | Letters only this language has among its neighbours. A word with one is never taken as foreign. |
| `apostrophe_fix` | Optional regex (group 1 = word start) for apostrophes Google returns as spaces. |
| `questions` | Default question words. |
| `stopwords` | Ignored when clustering. |
| `stem_len` | Prefix length used as a crude stem for clustering (5 for highly inflected languages, 6 otherwise). |
| `strip_suffixes` | Endings removed before stemming, e.g. `["s"]` for English plurals. |
| `adult_stems` | Dropped when `cleaning.filter_adult` is on. |
| `drop_trailing_single_letter` | Default for the cleaning option of the same name. |
| `markers` | Evidence that a phrase is in this language, used only when a project lists this language in `exclude_languages`: `chars` (letters), `words`, `suffix_regex` + `suffix_except`. |

The Russian `markers` (word list and suffix regex) are tuned to tell Russian
from Ukrainian. For other pairs only distinctive letters and function words are
used, which is safe but catches less.

## Adding a language

No code change is needed. Define the profile inline in `project.json`:

```json
"language": "cs",
"language_profile": {
  "name": "Czech",
  "script": "LATIN",
  "letters": "aábcčdďeéěfghiíjklmnňoóprřsštťuúůvyýzž",
  "word_start": "abcčdefghijklmnoprřsštuvzž",
  "exclusive_chars": "ěřů",
  "stem_len": 5,
  "questions": ["jak", "co", "kde", "kdy", "proč", "který", "kolik"],
  "stopwords": ["a", "v", "ve", "na", "s", "se", "z", "do", "pro", "od", "k", "o", "u", "jak", "co", "kde"]
}
```

`language_profile` can also patch an existing profile, e.g. add stopwords:
`"language_profile": {"stopwords": ["..."]}` merges over the built-in profile
(lists are replaced, not appended).

For languages without spaces between words (Chinese, Japanese, Thai) the crawl
works, but word-order deduplication and clustering are not meaningful; turn off
`cleaning.merge_word_order` and rely on the Keywords sheet.
