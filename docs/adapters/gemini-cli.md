# Gemini CLI adapter

**Status:** Production (v0.5)
**Module:** `llmwiki.adapters.gemini_cli`
**Source:** [`llmwiki/adapters/gemini_cli.py`](../../llmwiki/adapters/gemini_cli.py)
**Tracking issue:** #38

## What it reads

Gemini CLI stores session history under one of these paths:

```
~/.gemini/                    # primary
~/.config/gemini/             # XDG config
~/.local/share/gemini/        # XDG data
```

The adapter checks all three and discovers `.jsonl` files as well as `chat-*.json` and `session-*.json` patterns (Gemini CLI's JSON export format).

## Project slug derivation

Uses the first directory under the root, lowercased and prefixed with `gemini-`:

```
~/.gemini/MyProject/session-001.jsonl
  -> gemini-myproject
```

Files directly in the root get slug `gemini-root`.

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

## Configuration

Override roots in `config.json`:

```json
{
  "adapters": {
    "gemini_cli": {
      "roots": ["~/custom/gemini/path"]
    }
  }
}
```

## Testing the adapter

```bash
python3 -m llmwiki adapters      # should list gemini_cli as available (if installed)
python3 -m pytest tests/test_adapter_graduation.py -k gemini -v
```

## Fixture

A minimal synthetic fixture is provided at `tests/fixtures/gemini_cli/minimal.jsonl` for converter round-trip testing. It contains a single turn with a Bash tool call.

## Reference

- [`llmwiki/adapters/gemini_cli.py`](../../llmwiki/adapters/gemini_cli.py) -- the adapter source
- [`llmwiki/convert.py`](../../llmwiki/convert.py) -- the shared converter
- [README](../../README.md) -- project overview
