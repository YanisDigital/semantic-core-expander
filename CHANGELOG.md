# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-23

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
