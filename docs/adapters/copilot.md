# GitHub Copilot adapters

**Status:** Production (v0.6)
**Modules:** `llmwiki.adapters.copilot_chat`, `llmwiki.adapters.copilot_cli`
**Tracking issue:** #93

llmwiki ships two adapters for GitHub Copilot, covering the two distinct storage layouts.

---

## Copilot Chat (VS Code extension)

**Module:** `llmwiki.adapters.copilot_chat`
**Source:** [`llmwiki/adapters/copilot_chat.py`](../../llmwiki/adapters/copilot_chat.py)
**Registry name:** `copilot-chat`

### What it reads

The GitHub Copilot Chat extension for VS Code stores per-workspace conversation files under the editor's `workspaceStorage` directory:

```
<editor-data>/User/workspaceStorage/<hash>/chatSessions/*.jsonl
<editor-data>/User/workspaceStorage/<hash>/chatSessions/*.json
```

The adapter checks all three platforms and three editor variants (Code, Code - Insiders, VSCodium):

| Platform | Path pattern |
|----------|-------------|
| macOS | `~/Library/Application Support/<editor>/User/workspaceStorage/` |
| Linux | `~/.config/<editor>/User/workspaceStorage/` |
| Windows | `%APPDATA%\<editor>\User\workspaceStorage\` |

That gives 9 default roots (3 platforms x 3 editors).

### Project slug derivation

Workspace directories use opaque hashes. The adapter truncates the hash to 12 characters and prefixes with `copilot-`:

```
workspaceStorage/a1b2c3d4e5f6789/chatSessions/conv.jsonl
  -> copilot-a1b2c3d4e5f6
```

### Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

### Configuration

Override roots in `config.json`:

```json
{
  "adapters": {
    "copilot-chat": {
      "roots": ["~/custom/copilot/path"]
    }
  }
}
```

---

## Copilot CLI

**Module:** `llmwiki.adapters.copilot_cli`
**Source:** [`llmwiki/adapters/copilot_cli.py`](../../llmwiki/adapters/copilot_cli.py)
**Registry name:** `copilot-cli`

### What it reads

GitHub Copilot CLI stores per-session event logs under:

```
~/.copilot/session-state/<session-id>/events.jsonl
```

The adapter also checks the `COPILOT_HOME` environment variable. When set, it adds `$COPILOT_HOME/session-state/` as an additional root.

### Project slug derivation

Uses the session-id directory name directly:

```
~/.copilot/session-state/abc-123-def/events.jsonl
  -> abc-123-def
```

### Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

### Configuration

Override roots in `config.json`:

```json
{
  "adapters": {
    "copilot-cli": {
      "roots": ["~/.copilot/session-state"]
    }
  }
}
```

Or set the `COPILOT_HOME` environment variable:

```bash
export COPILOT_HOME=~/.copilot-custom
```

---

## Testing both adapters

```bash
python3 -m llmwiki adapters      # should list copilot-chat and copilot-cli
python3 -m pytest tests/test_copilot_adapters.py -v
```

## Reference

- [`llmwiki/adapters/copilot_chat.py`](../../llmwiki/adapters/copilot_chat.py) -- Chat adapter source
- [`llmwiki/adapters/copilot_cli.py`](../../llmwiki/adapters/copilot_cli.py) -- CLI adapter source
- [`llmwiki/convert.py`](../../llmwiki/convert.py) -- the shared converter
- [README](../../README.md) -- project overview
