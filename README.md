# fin-bash

**Market-aware cron wrapper** — drop-in replacement for `/bin/bash` in your crontab that only runs your script on trading days.

## Installation

### Requirements

- **Python 3.9+** (check with `python3 --version`)
- **pip** (usually bundled with Python)

### macOS / Linux

```bash
# 1. Clone the repo
git clone https://github.com/mvpp/fin-bash.git
cd fin-bash

# 2. Create a virtual environment and install
python3 -m venv .venv
.venv/bin/pip install -e .

# 3. (Option A) Symlink to a directory on your PATH
sudo ln -s "$(pwd)/.venv/bin/fin-bash" /usr/local/bin/fin-bash

# 3. (Option B) Or use the full path directly in crontab
#    ~/path/to/fin-bash/.venv/bin/fin-bash
```

> **Note:** On macOS, if `/usr/local/bin` doesn't exist, create it with `sudo mkdir -p /usr/local/bin` or use `~/.local/bin` instead (make sure it's on your `$PATH`).

### Windows

On Windows, `cron` is not available natively. Use **Task Scheduler** instead.

```powershell
# 1. Clone the repo
git clone https://github.com/mvpp/fin-bash.git
cd fin-bash

# 2. Create a virtual environment and install
python -m venv .venv
.venv\Scripts\pip install -e .

# 3. Verify it works
.venv\Scripts\fin-bash.exe check
```

To use with **Task Scheduler**:
1. Open Task Scheduler → **Create Basic Task**
2. Set the trigger to your desired schedule (e.g., daily at 9:30 AM, weekdays only)
3. Set the action to **Start a program**:
   - **Program:** `C:\path\to\fin-bash\.venv\Scripts\fin-bash.exe`
   - **Arguments:** `your_script.sh` (or `--exchange XLON your_script.sh`)

> **Note:** `fin-bash` invokes `/bin/bash` to run scripts, which requires WSL or Git Bash on Windows. If you're using PowerShell scripts (`.ps1`), you'll need to modify the tool to call `powershell.exe` instead.

### Verify installation

```bash
fin-bash --help          # show all options
fin-bash check           # is today a trading day?
fin-bash next --count 5  # upcoming trading days
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

## Q&A

**Q: Does `fin-bash` distinguish between open and closed hours on a trading day?**

By default, no — `fin-bash` runs your script as long as it's a trading day, regardless of what time it is. Cron already handles the scheduling; `fin-bash` just gates on "is it a trading day?"

If you need time-of-day awareness, opt in with `--session`:

| Flag | Behavior |
|------|----------|
| `--session any` *(default)* | Runs if today is a trading day — ignores time |
| `--session regular` | Runs only during market hours (e.g., 09:30–16:00 ET) |
| `--session pre` | Runs only during pre-market (e.g., 04:00–09:30 ET) |
| `--session post` | Runs only during post-market (e.g., 16:00–20:00 ET) |

**Q: Does `--session regular` handle half trading days (like the day before Thanksgiving)?**

Yes. `fin-bash` uses the **actual close time** from the exchange calendar, not a hardcoded 16:00. On early-close days, the session window adjusts automatically:

```
$ fin-bash check --date 2026-11-27
✓  2026-11-27  is a trading day on XNYS
   Session: 09:30 – 13:00 America/New_York
```

So `--session regular` at 14:00 ET on that day would **skip**, because 14:00 is past the 13:00 early close.
