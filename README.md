# fin-bash

**Market-aware cron wrapper** — drop-in replacement for `/bin/bash` in your crontab that only runs your script on trading days.

## Installation

```bash
cd ~/Programs/fin-bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Then use the full path in crontab: `~/Programs/fin-bash/.venv/bin/fin-bash`

Or symlink it somewhere on your `$PATH`:
```bash
ln -s ~/Programs/fin-bash/.venv/bin/fin-bash /usr/local/bin/fin-bash
```

## Usage

### In crontab (primary use case)

Replace `/bin/bash` with `fin-bash`:

```crontab
# Before:
30 9 * * 1-5 /bin/bash ~/scripts/scan.sh

# After (only runs on NYSE trading days):
30 9 * * 1-5 fin-bash ~/scripts/scan.sh

# With a specific exchange:
30 9 * * 1-5 fin-bash --exchange XLON ~/scripts/london_scan.sh
```

- If the market is **open**: runs `/bin/bash <script>` (via `execvp`, zero overhead).
- If the market is **closed**: logs the skip and exits with code `10`.

### Check if a date is a trading day

```bash
fin-bash check                          # today
fin-bash check --date 2026-12-25       # specific date
fin-bash check --exchange XLON         # London Stock Exchange
```

### List upcoming trading days

```bash
fin-bash next --count 5
```

### Dry-run (preview without executing)

```bash
fin-bash --dry-run ~/scripts/scan.sh
fin-bash --dry-run --date 2026-03-13 ~/scripts/scan.sh
```

### Session types

```bash
# Only run during regular trading hours (09:30–16:00 for NYSE)
fin-bash --session regular ~/scripts/intraday.sh

# Only run during pre-market (04:00–09:30 for NYSE)
fin-bash --session pre ~/scripts/premarket.sh

# Only run during post-market (16:00–20:00 for NYSE)
fin-bash --session post ~/scripts/afterhours.sh

# Default: "any" — just checks if it's a trading day, ignores time
fin-bash ~/scripts/daily.sh
```

## Configuration

Optional YAML config at `~/.config/fin-bash/config.yaml`:

```yaml
exchange: XNYS       # default exchange
session: any         # any | regular | pre | post
logging:
  level: INFO
  file: ~/.local/log/fin-bash/fin-bash.log
```

CLI flags override config values. See `config/fin-bash.example.yaml` for all options.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Job ran (or would run in dry-run) |
| `10` | Market closed — job skipped |
| `1`  | Error (bad args, exec failure, etc.) |

## Supported exchanges

Any exchange supported by [`exchange_calendars`](https://github.com/gerrymanoim/exchange_calendars), including:

| Code | Exchange |
|------|----------|
| `XNYS` | NYSE (default) |
| `XNAS` | NASDAQ |
| `XLON` | London |
| `XTKS` | Tokyo |
| `XHKG` | Hong Kong |
| `XSHG` | Shanghai |

Run with an invalid code to see the full list.
