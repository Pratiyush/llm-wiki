# Cursor adapter

**Status:** Production (v0.5)
**Module:** `llmwiki.adapters.cursor`
**Source:** [`llmwiki/adapters/cursor.py`](../../llmwiki/adapters/cursor.py)
**Tracking issue:** #37

## What it reads

Cursor IDE stores conversation history in per-workspace directories under platform-specific paths:

```
# macOS
~/Library/Application Support/Cursor/User/workspaceStorage/<hash>/

# Linux
~/.config/Cursor/User/workspaceStorage/<hash>/

# Windows
%APPDATA%\Cursor\User\workspaceStorage\<hash>\
```

The adapter checks all three platform paths and discovers `.jsonl` files (and `state.vscdb` for future SQLite support). The `<hash>` is a workspace-specific identifier.

## Project slug derivation

Cursor workspace directories use opaque hashes. The adapter truncates the hash to 12 characters and prefixes with `cursor-`:

```
workspaceStorage/a1b2c3d4e5f6789/session.jsonl
  -> cursor-a1b2c3d4e5f6
```

Future versions will read `workspace.json` from each workspace directory to extract the friendly project name.

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

## Configuration

Override roots in `config.json`:

```json
{
  "adapters": {
    "cursor": {
      "roots": ["~/custom/cursor/path"]
    }
  }
}
```

## Testing the adapter

```bash
python3 -m llmwiki adapters      # should list cursor as available (if installed)
python3 -m pytest tests/test_adapter_graduation.py -k cursor -v
```

## Fixture

A minimal synthetic fixture is provided at `tests/fixtures/cursor/minimal.jsonl` for converter round-trip testing. It contains a single turn with a Write tool call.

## Reference

- [`llmwiki/adapters/cursor.py`](../../llmwiki/adapters/cursor.py) -- the adapter source
- [`llmwiki/convert.py`](../../llmwiki/convert.py) -- the shared converter
- [README](../../README.md) -- project overview
