# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-23

Fixes from a security and privacy audit of 0.1.0.

### Security
- HTTP redirects are refused and treated as a block, so requests can no longer
  be bounced to another host or downgraded to plain HTTP, and a CAPTCHA
  redirect stops the crawl instead of being retried.
- Control, bidi-override and other invisible formatting characters are
  stripped from collected text before it is printed or exported (terminal
  escape injection, display spoofing in spreadsheets).
- `data/` and `output/` are resolved and confined to the project directory,
  so a symlinked folder cannot redirect cache or status writes.
- The release job no longer installs third-party packages; the CI test
  dependency (openpyxl + et-xmlfile) is pinned by hash. Dependabot now updates
  the pinned actions and the CI dependency.
- The privacy scan also rejects office documents, images with EXIF / XMP /
  text metadata and unreviewed file types.
- SKILL.md tells Claude to build the project slug itself and keep user text
  out of shell commands.

### Fixed
- The request interval jitter could shorten the gap to 0.8 × interval; it is
  now 1.0-1.4 ×, so the documented 0.3 s floor holds.
- A single 4xx answer no longer aborts the whole crawl (the query is skipped;
  ten in a row stop it), other 5xx answers are retried, and an unknown response
  charset falls back to UTF-8 instead of crashing.
- `status.json` records `error` / `interrupted` instead of staying `running`
  when the collector crashes or is stopped.
- A malformed `cluster_labels.json` gives a clear error (exit code 2).
- User-Agent now carries the real version.

## [0.1.0] - 2026-10-23

### Added
- Skill `semantic-core-expander`: Google Autocomplete crawl for any seeds,
  country and language, with a resumable SQLite cache and progress file.
- Language profiles for en, uk, ru, de, fr, es, it, pl, pt, nl; inline profiles
  for other languages.
- Cleaning: word-order duplicates, wrong script, excluded languages, adult /
  profanity, project excludes, truncated and junk phrases, `allow_words`.
- Relative popularity index (1-100), deterministic topic clusters with optional
  labels, XLSX (Keywords, Clusters, Rejected, About) and CSV export.
- Rate caps, shared back-off and stop-on-block behaviour.
- Formula-injection-safe exports, config validation, path confinement.
- Release tooling: allowlisted deterministic zip, SHA-256, privacy scan, CI and
  tag-triggered GitHub release.
