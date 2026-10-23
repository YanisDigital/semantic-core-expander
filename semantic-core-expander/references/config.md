# project.json reference

One file per project, in `./semantic-core/<slug>/project.json`. The scripts read
it with `--project ./semantic-core/<slug>`; nothing user-supplied is passed on
the command line, so there are no quoting problems with non-Latin text.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `project` | slug | yes | Lowercase letters, digits, `-`, `_`. Used in file names. |
| `site` | string | no | The site the core is for. Shown in the About sheet only. |
| `goal` | string | no | One line on the purpose. About sheet only. |
| `gl` | 2 letters | yes | Google country: `us`, `gb`, `de`, `ua`, `pl`... |
| `hl` | lang code | yes | Interface language: `en`, `de`, `uk`, `pt-br`... |
| `language` | profile id | no | Profile from `scripts/langs.json`. Default: first part of `hl`. |
| `language_profile` | object | no | Patch or define a profile inline (see `languages.md`). |
| `seeds` | list | yes | Base queries and their forms. Each is crawled as `seed`, `seed `, `seed a`... |
| `roots` | list | recommended | Relevance substrings (any-of). A suggestion counts only if it contains one. Default: the seeds, which is usually too strict for inflected languages. |
| `core` | list | no | Forms combined with every modifier and question (`core modifier`, `modifier core`, `question core`). Default: seeds. |
| `modifiers` | list | no | Niche words and phrases in the target language. |
| `questions` | list | no | Question words. Default: the profile's list. |
| `exclude_languages` | list | no | Profile ids whose phrasing should be dropped, e.g. `["ru"]` for a Ukrainian project. |
| `allow_words` | list | no | Words never treated as foreign-language evidence (fixes false positives). |
| `exclude.stems` | list | no | Drop phrases with a word starting with one of these (or containing it, if it has a space). |
| `exclude.regex` | list | no | Python regular expressions; drop matching phrases. |
| `limits.max_requests` | int | no | Network requests per run (default 3000, max 200000). Cached answers are free. |
| `limits.workers` | int | no | Parallel connections, 1-4 (default 2). |
| `limits.interval` | float | no | Minimum seconds between any two requests, ≥ 0.3 (default 0.4). |
| `limits.max_words` | int | no | Suggestions with this many words or more are not expanded further (default 7). |
| `cleaning.max_words` | int | no | Longer phrases are rejected (default 10). |
| `cleaning.filter_adult` | bool | no | Reject adult / profanity phrases (default true). |
| `cleaning.merge_word_order` | bool | no | Treat "a b" and "b a" as duplicates, keep the stronger (default true). Turn off when direction matters, e.g. routes "kyiv lviv" vs "lviv kyiv". |
| `cleaning.drop_trailing_single_letter` | bool | no | Reject "root a" style fragments. Default: on for Cyrillic profiles, off for Latin ones (where "vitamin c" is a real query). |
| `cleaning.min_cluster_size` | int | no | Smaller clusters go to `(misc)` (default 3). |

## Choosing roots

A root is the part every relevant phrase shares. For a city in an inflected
language use the stem: `житомир` matches житомир, житомира, у житомирі,
житомирська. For a niche use the head nouns: `["dentist", "dental"]`. One
root of 2-3 letters would match half the language, so the crawl drifts; when
in doubt prefer more, longer roots.

## Exclusions in practice

- Homonyms: a city name that is also a street or metro station elsewhere,
  e.g. `"exclude": {"regex": ["житомирськ\\w*.*\\bметро\\b"]}`.
- Foreign-language forms of the root: `"stems": ["житомире", "житомирск"]`.
  Stems match the *start* of a word, so make sure a stem is not also the start
  of a word in your own language: `"львов"` (Russian) would also drop Ukrainian
  "у львові". Use the full forms (`"львове"`, `"львовск"`) or a regex such as
  `"\\bльвов(?!і)"` (JSON escaping doubles the backslash). `--dry-run` and `--preview` warn about stems that hit your
  own seeds, core forms or modifiers.
- Brands or competitors the site never writes about: add their names.

## Files the scripts create

```
semantic-core/<slug>/
  project.json            you write this
  cluster_labels.json     optional, you write this after --preview
  data/cache.sqlite       every Google answer, keyed by gl|hl|query
  data/status.json        progress of the last collect run
  data/raw_suggestions.csv  everything seen, before cleaning
  output/<slug>_semantic_core.xlsx
  output/<slug>_keywords.csv
  output/<slug>_clusters.csv
```

Changing `gl` or `hl` in the same project starts a separate cache space, so
answers for different countries never mix.
