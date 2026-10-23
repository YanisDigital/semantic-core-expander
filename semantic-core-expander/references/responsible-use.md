# Responsible use

## What the skill contacts

Only `https://suggestqueries.google.com/complete/search`, the endpoint behind
the search box suggestions. It is public and needs no account, but it is not
an official, documented API, and Google's Terms of Service apply to its use.
You are responsible for how you use it. Commercial, high-volume or automated
use may need Google's permission or an official product (Google Ads Keyword
Planner, Search Console).

The skill sends the query text, `gl`, `hl` and a User-Agent that names the
tool. It sends no cookies, accounts, API keys or personal data, and it has no
telemetry: nothing is reported anywhere else.

## Why the limits exist

A real crawl takes tens of thousands of requests. In practice about 2-2.5
requests per second ran for hours without problems, while about 8 per second led
to an IP block (HTTP 403) lasting around an hour. So:

- At most 4 parallel connections and at least 0.3 s between any two requests,
  enforced by the config loader, not just suggested.
- One shared pause for all threads when Google answers 429 / 403 / 503. In the
  default mode the collector then stops with exit code 3; `--on-block wait`
  waits longer (up to about 2.5 hours in total) before stopping.
- No proxy support, no IP or User-Agent rotation, no CAPTCHA handling. A block
  is a signal to slow down or stop, not something to get around.

Everything already answered is cached, so stopping costs nothing: the next run
continues from the cache.

## Data

Collected suggestions, the cache and exports stay in the project directory on
your machine. Suggestions are written by the public and may contain names,
addresses or offensive text; review before publishing a list, and do not commit
`semantic-core/` to a public repository (the repo's `.gitignore` excludes it).
