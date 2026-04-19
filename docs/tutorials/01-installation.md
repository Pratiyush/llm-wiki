---
title: "01 · Installation"
type: tutorial
docs_shell: true
---

# 01 · Installation

**Time:** 5 minutes
**You'll need:** Python 3.9+, `git`, and at least one AI-coding agent already installed with session history on disk.
**Result:** A working `llmwiki` CLI on your PATH (or runnable via `python3 -m llmwiki`).

---

## Why this matters

llmwiki runs **locally**. Every session transcript stays on your machine. No
telemetry, no account, no network calls at build time. The install is
deliberately boring: clone, run the setup script, done.

---

## Step 1 — Check your toolchain

```bash
python3 --version          # expect 3.9 or newer
git --version
```

macOS and most Linux distros already ship both. Windows: install Python from
[python.org](https://python.org) and git from [git-scm.com](https://git-scm.com).

## Step 2 — Clone the repo

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
```

## Step 3 — Run the setup script

### macOS / Linux

```bash
./setup.sh
```

### Windows

```cmd
setup.bat
```

The setup script is idempotent. Running it twice is safe.

It will:

- Create `raw/`, `wiki/`, `site/` directories if they don't exist
- Seed `wiki/index.md`, `wiki/overview.md`, `wiki/log.md`, `wiki/CRITICAL_FACTS.md`
- Install the `markdown` pip package (only runtime dep; everything else is stdlib)
- Verify the CLI launches: `python3 -m llmwiki --version`

Expected output (version string matches the latest tagged release):

```
llmwiki <version>
```

## Step 4 — (Optional) Install via PyPI instead

Once [#246](https://github.com/Pratiyush/llm-wiki/issues/246) is set up:

```bash
pip install llmwiki
llmwiki --version
```

Or via Homebrew, once [#247](https://github.com/Pratiyush/llm-wiki/issues/247) is set up:

```bash
brew install Pratiyush/tap/llmwiki
```

Until then the clone-and-run path above is authoritative.

## Step 5 — (Optional) Install via Docker

Zero-touch, no Python on your machine:

```bash
docker run -p 8765:8765 -v $PWD/wiki:/wiki ghcr.io/pratiyush/llm-wiki:latest
```

See [deploy/docker.md](../deploy/docker.md) for the full Compose setup.

---

## Verify

```bash
python3 -m llmwiki --version           # → llmwiki <version>
python3 -m llmwiki adapters            # lists every agent adapter and whether it's configured
```

The `adapters` output tells you which agents have session stores on this
machine — your first sync pulls from every one marked `configured ✓`.

---

## Troubleshooting

**`command not found: python3`** — install Python from python.org and re-open your terminal.

**`setup.sh: permission denied`** — `chmod +x setup.sh` once, then re-run.

**`ModuleNotFoundError: No module named 'markdown'`** — `pip install markdown` and re-run.

**`ImportError` on Python 3.8 or older** — llmwiki requires ≥ 3.9. Upgrade Python; on macOS use `brew install python@3.12`.

---

## Next

→ **[02 · First sync](02-first-sync.md)** — point llmwiki at your session history and build the site.
