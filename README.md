# semantic-core-expander

A Claude skill that expands a website's **semantic core** (keyword list) for
free: it crawls Google Autocomplete for your base queries in any country and
language, collects thousands of long-tail queries, cleans them, scores them
with a relative popularity index and groups them into topics. The result is an
Excel file you can build a site structure and content plan from, without
Ahrefs, Semrush or other paid tools.

- Any niche, any seed queries, any country (`gl`) and language (`hl`)
- Built-in profiles: English, Ukrainian, Russian, German, French, Spanish,
  Italian, Polish, Portuguese, Dutch; other languages via a few lines of config
- Long tail on purpose: alphabet crawl after every full suggestion list, niche
  and question modifiers, every found phrase expanded again
- Cleaning: duplicates (incl. word order), wrong script, unwanted languages
  (e.g. Russian phrasing in a Ukrainian project), adult/profanity, homonyms you
  define, junk fragments; everything rejected stays visible with a reason
- Output: `Keywords` (keyword, index 1-100, cluster), `Clusters`, `Rejected`,
  `About` sheets, plus CSV
- Resumable: every answer is cached in SQLite, a re-run never repeats a request
- Polite and transparent: ~2 requests/s, stops when Google pushes back, no
  proxies or disguises, no telemetry

## How it works

Claude does the language work, the bundled Python scripts do the crawling:

1. You give base queries, the site and the market. Claude writes a
   `project.json`: grammatical forms of the seeds, relevance roots, 100-200 niche
   modifiers, question words, languages to exclude.
2. `suggest_collect.py` walks the autocomplete tree and caches every answer.
3. `clean_export.py --preview` shows samples; Claude tunes exclusions
   (other meanings of the root, false language matches) and names the clusters.
4. `clean_export.py` writes the Excel / CSV files; Claude summarises the result.

The **index (1-100)** is not monthly search volume. It reflects how early, how
high and how often Google suggests a phrase, on a log scale, comparable only
within one export. It is good for prioritising and clustering; confirm the top
of the list with Keyword Planner or Search Console when you need numbers. See
[Using the index](#using-the-index-1-100-instead-of-search-volume) below.

## Installation

Download `semantic-core-expander-vX.Y.Z.zip` from
[Releases](../../releases) and verify it:

```bash
sha256sum -c semantic-core-expander-vX.Y.Z.zip.sha256
```

**Claude Code** (CLI, desktop, IDE): unzip into your skills folder, so that the
file `~/.claude/skills/semantic-core-expander/SKILL.md` exists (or into
`.claude/skills/` of a project to scope it to that project).

**Claude apps** (claude.ai / desktop chat): open the Skills section in
Settings and upload the zip. The crawl needs outbound HTTPS to `suggestqueries.google.com`;
if your code-execution environment restricts network access, run the skill in
Claude Code instead.

Requirements: Python 3.10+. `openpyxl` is optional (`pip install openpyxl`) —
without it you get CSV files instead of `.xlsx`.

## Usage

Just ask, in any language:

> Expand the semantic core for my dental clinic site in Austin. Base queries:
> "dentist austin", "dental clinic austin". Google US, English.

> Собери семантику для регионального новостного сайта: «житомир», «у житомирі»,
> «житомирська область». Google Украина, украинский, без русскоязычных запросов.

> Find long-tail keywords for "sourdough starter" in Germany, German language,
> and group them by topic.

Project files land in `./semantic-core/<slug>/` of your working directory:
`project.json`, `data/` (cache, progress) and `output/` (Excel and CSV).
A first pass of 3000 requests takes about 25 minutes; Claude runs it in the
background and can continue later from the cache.

## Using the index (1-100) instead of search volume

Google does not publish search volumes for free, so there is no "queries per
month" column. The `Index (1-100)` column is a stand-in: a **relative
popularity score** computed from how Google suggested each phrase while the
crawl ran. It answers "which of these phrases does Google treat as more
common?", not "how many people search for it?".

### What the number means

A phrase scores higher when Google suggests it:

- after fewer typed characters (an early suggestion means a common phrase),
- in a higher position of the suggestion list,
- for more different prefixes,
- with the typed text at its start rather than in the middle.

The sum is put on a logarithmic scale and stretched to 1-100 inside your
export: the strongest phrase gets 100, the weakest 1. Typical readings:

| Index | Meaning | Typical use |
|---|---|---|
| 60-100 | Stable, mass queries of the topic (a few percent of the list) | Site sections, hub pages, main landing pages |
| 30-59 | Middle layer, most of the list | Articles, guides, category and service pages |
| 1-29 | Long tail: specific questions, details, rare wording | FAQ blocks, sub-headings, small pages, support for bigger pages |

### What it is not

- **Not traffic.** 80 does not mean twice the searches of 40. The scale is
  logarithmic and only ranks phrases.
- **Not comparable between files.** Each export has its own 1-100 scale; 70 in
  one project says nothing about 70 in another. Do not merge two exports and
  sort by index.
- **Not additive.** Do not sum indexes into "traffic" of a topic. Use them to
  compare topics, not to forecast visits.
- **Not always stable.** Phrases tied to news, incidents or seasons can score
  high because of a recent spike.

### How to work with it

1. **Start from clusters, not single phrases.** Open the `Clusters` sheet. A
   high *sum index* means a topic Google surfaces often; many *queries* mean the
   topic is deep enough for a whole section. A lone phrase with index 20 tells
   you little; fifty phrases around one theme tell you a lot.
2. **Sort topics by sum index, pages by max index.** Topics with the highest sum
   become sections of the site. Inside a topic, the phrase with the highest
   index is the natural page title; the rest become sub-headings and FAQ.
3. **Plan in tiers.** Write the 60-100 pages first because demand is proven,
   then 30-59, and fill the tail from real questions. A high index shows demand,
   not that you will rank: check who already answers the query.
4. **Treat the bottom as a filter, not as trash.** Below roughly 5-10 you often
   find one-off tails (an address, a surname, a cut-off phrase). Keep them for
   coverage but do not plan around them. For information sites the tail is a
   large share of total reach, so never delete it automatically.
5. **Separate news spikes from steady demand.** Phrases with "today", dates,
   incidents or events need fast, short-lived formats. Prices, schedules,
   addresses, "how to" and phone numbers deserve durable pages.
6. **Confirm only the top with real numbers.** Take the top 1-3 thousand phrases
   (not the whole file) and check them in Google Keyword Planner for volume
   ranges. Once the site is live, Google Search Console gives real impressions
   and positions; add the queries that bring them to the core. Google Trends
   helps compare two or three topics.

### Example

A clinic site gets these rows: `dentist near me` (100), `dentist cost` (93),
`emergency dentist open now` (62), `dentist for kids anxiety tips` (18). Read
them as: "near me" and "cost" are core demand, so they get a location page and
a price page; "emergency, open now" is a mid-tier page with strong intent; the
anxiety tips phrase is a tail topic that fits a section of a kids' dentistry
page. None of the numbers says how many visits each will bring.

More detail and the exact formula:
[`frequency-index.md`](semantic-core-expander/references/frequency-index.md).

## Privacy and security

- **One network destination.** The scripts only call
  `https://suggestqueries.google.com/complete/search` with the query, `gl`,
  `hl` and a User-Agent that names the tool. Redirects are refused (treated as a
  block), so a request never ends up on another host or on plain HTTP. No
  accounts, cookies, API keys, telemetry or third-party services. If you have
  a system proxy configured (`HTTPS_PROXY`), Python uses it, as it does for any
  program; the skill itself adds none.
- **Local data.** Cache and exports stay in your project folder. `.gitignore`
  excludes `semantic-core/`, SQLite, Excel and CSV files so you do not publish
  them by accident.
- **No shell, no eval.** Scripts use the Python standard library (plus optional
  openpyxl), never run subprocesses or evaluate input. User text reaches them
  through a JSON file, never through command-line interpolation. The config is
  validated (codes, list sizes, rate caps) and every file the scripts write
  (cache, status, exports) is confined to the project directory, symlinks
  included. SQLite queries are parameterised.
- **Untrusted text handled as data.** Google responses are size- and
  type-checked. Control and invisible formatting characters (ANSI escapes,
  bidi overrides) are stripped before a phrase is printed or saved. Phrases
  starting with `=`, `+`, `-`, `@` cannot turn into spreadsheet formulas
  (stored as text in XLSX, prefixed with `'` in CSV). The skill instructs
  Claude to treat suggestions and web pages as data, never as instructions.
- **Clean releases.** `tools/build_zip.py` packages an allowlist of files only
  and refuses to build if the repository contains data files, office documents,
  images with EXIF/XMP metadata, unreviewed file types, e-mail addresses,
  personal paths or credential-like strings. CI runs the same scan. Workflows
  use only official actions pinned to commit SHAs, with least-privilege
  permissions; the release job installs no third-party packages, and the CI test
  dependency is hash-pinned. Dependabot keeps both pins current. Each release
  ships a SHA-256 checksum.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Responsible use

The autocomplete endpoint is public but not an official API; Google's Terms of
Service apply, and you are responsible for your use. The skill keeps a low,
fixed rate, pauses once when Google answers 429/403/503 or redirects, then
stops and resumes later from the cache. It does not and will not support proxy
or IP rotation, User-Agent rotation, or CAPTCHA solving. Details:
[`responsible-use.md`](semantic-core-expander/references/responsible-use.md).

## Repository layout

```
semantic-core-expander/      the skill (this folder is what the zip contains)
  SKILL.md                   workflow for Claude
  scripts/                   suggest_collect.py, clean_export.py, textutils.py,
                             common.py, langs.json
  references/                config, languages, index, responsible use
  assets/project.example.json
tests/                       offline unit tests (no network)
tools/build_zip.py           release packaging + privacy scan
.github/workflows/           CI and tag-triggered release
```

## Development

```bash
python -m unittest discover -s tests -v
```

```bash
python tools/build_zip.py --version v0.1.0
```

Releasing: update `CHANGELOG.md`, then push a tag `vX.Y.Z`. The Release
workflow runs the tests, builds the zip and checksum, and publishes a GitHub
release.

## License

[MIT](LICENSE)
