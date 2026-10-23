# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub: **Security → Report a
vulnerability** on this repository (private vulnerability reporting). Do not
open a public issue for a vulnerability. Include the version (release tag), the
steps to reproduce and the impact you expect.

You should get an acknowledgement within 7 days. Fixes are released as a new
version tag and noted in `CHANGELOG.md`.

## Supported versions

Only the latest release receives fixes.

## Scope and design

In scope: anything in this repository, in particular

- the scripts in `semantic-core-expander/scripts/` (network access, file writes,
  parsing of Google responses and of `project.json`);
- the instructions in `SKILL.md` and `references/` (for example, anything that
  could lead Claude to follow instructions found in collected data);
- the release pipeline (`tools/build_zip.py`, `.github/workflows/`).

Design guarantees the project aims to keep:

- the only network destination is `https://suggestqueries.google.com/complete/search`,
  and redirects are never followed;
- no credentials, telemetry, subprocesses, `eval` or `exec`;
- all writes stay inside the user's project directory;
- collected text is stripped of control and bidi characters before it is
  printed or saved;
- spreadsheet exports cannot contain live formulas from collected text;
- release zips contain only allowlisted files and pass a privacy scan, and the
  release job runs no third-party packages.

A change that breaks one of these is a security bug.

Out of scope: Google's availability or blocking behaviour, and the content of
suggestions themselves (they are third-party public text).
