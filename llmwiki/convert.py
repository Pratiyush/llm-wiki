"""Convert agent session transcripts (.jsonl) to Karpathy-style markdown.

Called by `llmwiki sync`. Reads from the adapters in `llmwiki.adapters` and
writes clean, frontmatter-tagged markdown under `raw/sessions/`.

The conversion is idempotent: state is tracked in `.llmwiki-state.json` by
mtime, so re-running on unchanged files is a fast no-op.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_adapters

DEFAULT_STATE_FILE = REPO_ROOT / ".llmwiki-state.json"
DEFAULT_CONFIG_FILE = REPO_ROOT / "examples" / "sessions_config.json"
DEFAULT_OUT_DIR = REPO_ROOT / "raw" / "sessions"
DEFAULT_IGNORE_FILE = REPO_ROOT / ".llmwikiignore"

DEFAULT_CONFIG: dict[str, Any] = {
    "filters": {
        "live_session_minutes": 60,
        "include_projects": [],
        "exclude_projects": [],
        "drop_record_types": ["queue-operation", "file-history-snapshot", "progress"],
    },
    "redaction": {
        "real_username": "",
        "replacement_username": "USER",
        "extra_patterns": [
            r"(?i)(api[_-]?key|secret|token|bearer|password)[\"'\s:=]+[\w\-\.]{8,}",
            r"sk-[A-Za-z0-9]{20,}",
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        ],
    },
    "truncation": {
        "tool_result_chars": 500,
        "bash_stdout_lines": 5,
        "write_content_preview_lines": 5,
        "user_prompt_chars": 4000,
        "assistant_text_chars": 8000,
    },
    "drop_thinking_blocks": True,
}


# ─── config + state ────────────────────────────────────────────────────────

def load_config(path: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  warning: bad config {path}: {e}", file=sys.stderr)
            return cfg
        for section, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(section), dict):
                cfg[section].update(value)
            else:
                cfg[section] = value
    # Auto-detect username if not set
    if not cfg["redaction"].get("real_username"):
        try:
            import os
            cfg["redaction"]["real_username"] = os.environ.get("USER", "") or Path.home().name
        except Exception:
            pass
    return cfg


def load_state(path: Path) -> dict[str, float]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(path: Path, state: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


# ─── .llmwikiignore ───────────────────────────────────────────────────────


class IgnoreMatcher:
    """Gitignore-style pattern matcher for `.llmwikiignore`.

    Patterns are read from one file (typically `.llmwikiignore` at the repo
    root). Each non-empty, non-comment line is a pattern. A pattern is matched
    against the project slug, the session filename, and the `<project>/<name>`
    composite.

    Supports:
      - `#` for line comments
      - `!pattern` for negation (a negated pattern re-includes a previously
        excluded match)
      - `*`, `?`, `[abc]` glob metacharacters via fnmatch
      - `**` matches any number of path segments (any substring)
      - Trailing `/` marks a pattern as directory-only (matches project slugs)
    """

    def __init__(self, patterns: list[str]):
        # Each entry is (glob_pattern, is_negation, dir_only)
        self._rules: list[tuple[str, bool, bool]] = []
        for raw in patterns:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            negate = raw.startswith("!")
            if negate:
                raw = raw[1:]
            dir_only = raw.endswith("/")
            if dir_only:
                raw = raw[:-1]
            self._rules.append((raw, negate, dir_only))

    @classmethod
    def from_file(cls, path: Path) -> "IgnoreMatcher":
        if not path.exists():
            return cls([])
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return cls([])
        return cls(text.splitlines())

    @staticmethod
    def _match_one(pattern: str, target: str) -> bool:
        """Match a single pattern against a target string.

        We emulate gitignore-ish behaviour with stdlib fnmatch, extended to
        handle `**` by translating it to `*` and also matching the pattern
        against any path suffix.
        """
        import fnmatch

        # Normalize path separators
        target = target.replace("\\", "/")
        pattern_norm = pattern.replace("\\", "/")
        # `**` means "any number of path segments" — collapse to `*` for fnmatch
        fn_pattern = pattern_norm.replace("**", "*")
        if fnmatch.fnmatch(target, fn_pattern):
            return True
        # Also allow matching against any suffix of the target so `foo/*.md`
        # matches `raw/sessions/foo/bar.md`.
        parts = target.split("/")
        for i in range(len(parts)):
            suffix = "/".join(parts[i:])
            if fnmatch.fnmatch(suffix, fn_pattern):
                return True
        # And bare basename match so `*.tmp` matches any file named *.tmp
        base = parts[-1] if parts else target
        if fnmatch.fnmatch(base, fn_pattern):
            return True
        return False

    def is_ignored(self, *, project: str, filename: str) -> bool:
        """Return True if the (project, filename) pair should be skipped.

        The composite path `<project>/<filename>` is matched too so patterns
        like `confidential-client/` or `ai-newsletter/2026-04-04-*` work.
        """
        composite = f"{project}/{filename}"
        ignored = False
        for pattern, negate, dir_only in self._rules:
            targets: list[str] = [composite, filename, project]
            matched = any(self._match_one(pattern, t) for t in targets)
            if not matched:
                continue
            if dir_only and not self._match_one(pattern, project):
                # Directory-only rule but the match came from the filename —
                # skip this rule.
                continue
            ignored = not negate
        return ignored

    def __bool__(self) -> bool:
        return bool(self._rules)

    def __len__(self) -> int:
        return len(self._rules)


# ─── parsing ───────────────────────────────────────────────────────────────

def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        # ``errors="replace"`` lets us survive the occasional corrupt byte in a
        # session transcript (e.g. a truncated UTF-8 sequence from a killed
        # tool). Before the fix a single bad byte would abort the whole sync.
        with path.open(encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Only keep dict-shaped records. JSONL files occasionally
                # contain stray scalars (e.g. numbers, strings) from partial
                # writes, which used to crash downstream filter_records.
                if isinstance(rec, dict):
                    out.append(rec)
    except OSError:
        pass
    return out


def filter_records(records: list[dict[str, Any]], drop_types: list[str]) -> list[dict[str, Any]]:
    drop = set(drop_types)
    return [r for r in records if r.get("type") not in drop]


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def latest_record_time(records: list[dict[str, Any]]) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for r in records:
        t = parse_iso(r.get("timestamp"))
        if t and (latest is None or t > latest):
            latest = t
    return latest


def first_record_time(records: list[dict[str, Any]]) -> Optional[datetime]:
    earliest: Optional[datetime] = None
    for r in records:
        t = parse_iso(r.get("timestamp"))
        if t and (earliest is None or t < earliest):
            earliest = t
    return earliest


def first_field(records: list[dict[str, Any]], field: str, default: str = "") -> str:
    for r in records:
        v = r.get(field)
        if v:
            return str(v)
    return default


def most_common_model(records: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for r in records:
        if r.get("type") != "assistant":
            continue
        m = r.get("message", {}).get("model")
        if m:
            counts[m] = counts.get(m, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else ""


# ─── redaction + truncation ────────────────────────────────────────────────

class Redactor:
    def __init__(self, config: dict[str, Any]):
        red = config.get("redaction", {})
        self.real_user = red.get("real_username", "")
        self.repl_user = red.get("replacement_username", "USER")
        self.patterns = [re.compile(p) for p in red.get("extra_patterns", [])]

    def __call__(self, text: str) -> str:
        if not text:
            return text
        if self.real_user:
            text = text.replace(f"/Users/{self.real_user}/", f"/Users/{self.repl_user}/")
            text = text.replace(f"/Users/{self.real_user}", f"/Users/{self.repl_user}")
            text = text.replace(f"/home/{self.real_user}/", f"/home/{self.repl_user}/")
        for pat in self.patterns:
            text = pat.sub("<REDACTED>", text)
        return text


def _close_open_fence(text: str) -> str:
    """If ``text`` contains an odd number of ``\\`\\`\\``` fence markers,
    append a closing fence so downstream markdown parsers don't swallow the
    rest of the page as one giant code block. Counts only lines whose first
    non-whitespace characters are triple backticks (real fences, not inline
    code). See #72 — truncated tool results used to eat everything below them.
    """
    fence_count = sum(
        1 for line in text.splitlines() if line.lstrip().startswith("```")
    )
    if fence_count % 2 == 1:
        return text + "\n```"
    return text


def truncate_chars(text: str, max_chars: int) -> str:
    if not text or len(text) <= max_chars:
        return text
    kept = _close_open_fence(text[:max_chars])
    return kept + f"\n…(truncated, {len(text) - max_chars} more chars)"


def truncate_lines(text: str, max_lines: int) -> str:
    if not text:
        return text
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    kept = _close_open_fence("\n".join(lines[:max_lines]))
    return kept + f"\n…(truncated, {len(lines) - max_lines} more lines)"


# ─── record classification ─────────────────────────────────────────────────

def is_real_user_prompt(record: dict[str, Any]) -> bool:
    if record.get("type") != "user":
        return False
    return isinstance(record.get("message", {}).get("content"), str)


def is_tool_result_delivery(record: dict[str, Any]) -> bool:
    if record.get("type") != "user":
        return False
    content = record.get("message", {}).get("content")
    if not isinstance(content, list):
        return False
    return any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def count_user_messages(records: list[dict[str, Any]]) -> int:
    return sum(1 for r in records if is_real_user_prompt(r))


def count_tool_calls(records: list[dict[str, Any]]) -> int:
    n = 0
    for r in records:
        if r.get("type") != "assistant":
            continue
        for b in r.get("message", {}).get("content", []) or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                n += 1
    return n


def extract_tools_used(records: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for r in records:
        if r.get("type") != "assistant":
            continue
        for b in r.get("message", {}).get("content", []) or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                seen.setdefault(b.get("name", "Unknown"), None)
    return list(seen.keys())


# ─── v0.8 session metrics (#63) ───────────────────────────────────────────
# Structured per-session metrics emitted into frontmatter as JSON inline
# values. The build step and the v0.8 visualization modules (#64/#65/#66)
# consume these without having to re-parse the raw .jsonl. Keep all helpers
# stdlib-only and tolerant of missing fields.


def compute_tool_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Return a {tool_name: count} mapping across all assistant tool_use blocks."""
    counts: dict[str, int] = {}
    for r in records:
        if r.get("type") != "assistant":
            continue
        for b in r.get("message", {}).get("content", []) or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                name = b.get("name") or "Unknown"
                counts[name] = counts.get(name, 0) + 1
    # Return with stable ordering (by count desc then name) so the rendered
    # frontmatter is byte-identical across runs.
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def compute_token_totals(records: list[dict[str, Any]]) -> dict[str, int]:
    """Sum input / cache_creation / cache_read / output tokens across assistant
    messages. Missing fields contribute 0.
    """
    totals = {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}
    for r in records:
        if r.get("type") != "assistant":
            continue
        usage = r.get("message", {}).get("usage") or {}
        if not isinstance(usage, dict):
            continue
        totals["input"] += int(usage.get("input_tokens") or 0)
        totals["cache_creation"] += int(usage.get("cache_creation_input_tokens") or 0)
        totals["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
        totals["output"] += int(usage.get("output_tokens") or 0)
    return totals


def compute_turn_count(records: list[dict[str, Any]]) -> int:
    """Number of user→assistant turn pairs (equivalent to real user prompts)."""
    return count_user_messages(records)


def compute_hour_buckets(records: list[dict[str, Any]]) -> dict[str, int]:
    """Return {"YYYY-MM-DDTHH": count} keyed by UTC hour-of-activity.

    Sparse — only hours with at least one record. Used by the v0.8 activity
    heatmap (#64) to size per-day dots without reading the raw jsonl.
    """
    buckets: dict[str, int] = {}
    for r in records:
        ts = parse_iso(r.get("timestamp"))
        if ts is None:
            continue
        ts_utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts
        key = ts_utc.strftime("%Y-%m-%dT%H")
        buckets[key] = buckets.get(key, 0) + 1
    # Sorted chronologically for stable frontmatter output.
    return dict(sorted(buckets.items()))


def compute_duration_seconds(records: list[dict[str, Any]]) -> int:
    """Total elapsed session time in whole seconds (last_ts - first_ts)."""
    first = first_record_time(records)
    last = latest_record_time(records)
    if first is None or last is None:
        return 0
    delta = last - first
    return max(0, int(delta.total_seconds()))


# ─── tool-use rendering ────────────────────────────────────────────────────

def summarize_tool_use(block: dict[str, Any], redact: Redactor, config: dict[str, Any]) -> str:
    name = block.get("name", "Tool")
    inp = block.get("input", {}) or {}
    trunc = config.get("truncation", {})

    if name == "Bash":
        cmd = inp.get("command", "") or ""
        first_line = cmd.splitlines()[0] if cmd else ""
        if len(cmd.splitlines()) > 1:
            first_line += " …"
        return f"`Bash`: `{redact(truncate_chars(first_line, 200))}`"

    if name == "Read":
        fp = inp.get("file_path", "")
        offset = inp.get("offset")
        limit = inp.get("limit")
        rng = ""
        if offset is not None or limit is not None:
            start = offset or 1
            end = (offset or 0) + (limit or 0) if limit else "?"
            rng = f" ({start}–{end})"
        return f"`Read`: `{redact(fp)}`{rng}"

    if name == "Write":
        fp = inp.get("file_path", "")
        content = inp.get("content", "") or ""
        preview = truncate_lines(content, trunc.get("write_content_preview_lines", 5))
        return (
            f"`Write`: `{redact(fp)}` ({len(content)} chars)\n\n"
            f"```\n{redact(preview)}\n```"
        )

    if name == "Edit":
        fp = inp.get("file_path", "")
        old = inp.get("old_string", "") or ""
        new = inp.get("new_string", "") or ""
        return f"`Edit`: `{redact(fp)}` (− {len(old)} chars / + {len(new)} chars)"

    if name == "Glob":
        pat = inp.get("pattern", "")
        path = inp.get("path", "")
        return f"`Glob`: `{redact(pat)}`" + (f" in `{redact(path)}`" if path else "")

    if name == "Grep":
        pat = inp.get("pattern", "")
        glob = inp.get("glob") or inp.get("path", "")
        return f"`Grep`: `{redact(pat)}`" + (f" in `{redact(glob)}`" if glob else "")

    if name == "TodoWrite":
        todos = inp.get("todos", []) or []
        return f"`TodoWrite`: {len(todos)} todos"

    if name == "WebFetch":
        return f"`WebFetch`: {redact(inp.get('url', ''))}"

    if name == "WebSearch":
        q = inp.get("query", "")
        return f"`WebSearch`: {redact(truncate_chars(q, 200))}"

    if name == "Task":
        desc = inp.get("description", "") or inp.get("subagent_type", "")
        return f"`Task`: {redact(truncate_chars(desc, 200))}"

    keys = ", ".join(inp.keys())
    return f"`{name}` (inputs: {keys})"


def render_assistant_message(
    record: dict[str, Any],
    redact: Redactor,
    config: dict[str, Any],
) -> tuple[str, list[str]]:
    msg = record.get("message", {})
    content = msg.get("content", [])
    if not isinstance(content, list):
        return "", []
    text_parts: list[str] = []
    tools: list[str] = []
    drop_thinking = config.get("drop_thinking_blocks", True)
    max_chars = config.get("truncation", {}).get("assistant_text_chars", 8000)

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "thinking":
            if drop_thinking:
                continue
            text_parts.append(f"_(thinking)_ {block.get('thinking', '')}")
        elif btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tools.append(summarize_tool_use(block, redact, config))

    text = "\n\n".join(t for t in text_parts if t).strip()
    text = truncate_chars(redact(text), max_chars)
    return text, tools


def render_tool_results(
    record: dict[str, Any],
    redact: Redactor,
    config: dict[str, Any],
) -> list[str]:
    msg = record.get("message", {})
    content = msg.get("content", [])
    if not isinstance(content, list):
        return []
    out: list[str] = []
    max_chars = config.get("truncation", {}).get("tool_result_chars", 500)
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        c = block.get("content", "")
        if isinstance(c, list):
            parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
            c = "\n".join(parts)
        marker = "ERROR" if block.get("is_error") else "ok"
        rendered = truncate_chars(redact(str(c).strip()), max_chars)
        out.append(f"  → result ({marker}): {rendered}" if rendered else f"  → result ({marker})")
    return out


def render_user_prompt(record: dict[str, Any], redact: Redactor, max_chars: int) -> str:
    content = record.get("message", {}).get("content", "")
    if not isinstance(content, str):
        return ""
    return truncate_chars(redact(content.strip()), max_chars)


# ─── full markdown renderer ────────────────────────────────────────────────

def derive_session_slug(records: list[dict[str, Any]], jsonl_path: Path) -> str:
    for r in records:
        slug = r.get("slug")
        if slug:
            return str(slug)
    return jsonl_path.stem[:12]


def render_session_markdown(
    records: list[dict[str, Any]],
    jsonl_path: Path,
    project_slug: str,
    redact: Redactor,
    config: dict[str, Any],
    is_subagent_file: bool,
) -> tuple[str, str, datetime]:
    started = first_record_time(records) or datetime.now(timezone.utc)
    ended = latest_record_time(records) or started
    date_str = started.strftime("%Y-%m-%d")

    session_id = first_field(records, "sessionId") or jsonl_path.stem
    slug = derive_session_slug(records, jsonl_path)
    if is_subagent_file:
        agent_id = jsonl_path.stem.replace("agent-", "")[:8]
        slug = f"{slug}-subagent-{agent_id}"

    cwd = first_field(records, "cwd")
    git_branch = first_field(records, "gitBranch")
    permission_mode = first_field(records, "permissionMode")
    model = most_common_model(records)
    tools_used = extract_tools_used(records)
    u_count = count_user_messages(records)
    t_count = count_tool_calls(records)

    # v0.8 (#63) structured metrics — JSON inline in frontmatter
    tool_counts = compute_tool_counts(records)
    token_totals = compute_token_totals(records)
    turn_count = compute_turn_count(records)
    hour_buckets = compute_hour_buckets(records)
    duration_seconds = compute_duration_seconds(records)

    title = f"Session: {slug} — {date_str}"
    front = [
        "---",
        f'title: "{title}"',
        "type: source",
        "tags: [claude-code, session-transcript]",
        f"date: {date_str}",
        f"source_file: raw/sessions/{project_slug}/{date_str}-{slug}.md",
        f"sessionId: {session_id}",
        f"slug: {slug}",
        f"project: {project_slug}",
        f"started: {started.isoformat()}",
        f"ended: {ended.isoformat()}",
        f"cwd: {redact(cwd)}",
        f"gitBranch: {git_branch}",
        f"permissionMode: {permission_mode}",
        f"model: {model}",
        f"user_messages: {u_count}",
        f"tool_calls: {t_count}",
        f"tools_used: [{', '.join(tools_used)}]",
        # v0.8 — structured metrics (JSON inline so the simple frontmatter
        # parser stores them as strings; consumers json.loads() on demand).
        f"tool_counts: {json.dumps(tool_counts, sort_keys=False)}",
        f"token_totals: {json.dumps(token_totals, sort_keys=False)}",
        f"turn_count: {turn_count}",
        f"hour_buckets: {json.dumps(hour_buckets, sort_keys=False)}",
        f"duration_seconds: {duration_seconds}",
        f"is_subagent: {str(is_subagent_file).lower()}",
        "---",
        "",
    ]

    body: list[str] = [
        f"# {title}",
        "",
        f"**Project:** `{project_slug}` · **Branch:** `{git_branch}` · **Mode:** `{permission_mode}` · **Model:** `{model}`",
        "",
        f"**Stats:** {u_count} user messages, {t_count} tool calls, tools used: {', '.join(tools_used) if tools_used else 'none'}.",
        "",
        "## Conversation",
        "",
    ]

    max_user_chars = config.get("truncation", {}).get("user_prompt_chars", 4000)
    turn_idx = 0
    assistant_open = False
    for r in records:
        if is_real_user_prompt(r):
            turn_idx += 1
            assistant_open = False
            body.append(f"### Turn {turn_idx} — User")
            body.append("")
            body.append(render_user_prompt(r, redact, max_user_chars) or "_(empty)_")
            body.append("")
        elif r.get("type") == "assistant":
            text, tools = render_assistant_message(r, redact, config)
            if not text and not tools:
                continue
            if not assistant_open:
                body.append(f"### Turn {turn_idx} — Assistant")
                body.append("")
                assistant_open = True
            if text:
                body.append(text)
                body.append("")
            if tools:
                body.append("**Tools used:**")
                body.append("")
                for t in tools:
                    body.append(f"- {t}")
                body.append("")
        elif is_tool_result_delivery(r):
            results = render_tool_results(r, redact, config)
            if not results:
                continue
            if not assistant_open:
                body.append(f"### Turn {turn_idx} — Assistant")
                body.append("")
                assistant_open = True
            body.append("**Tool results:**")
            body.append("")
            body.extend(results)
            body.append("")

    md = "\n".join(front + body).rstrip() + "\n"
    return md, slug, started


# ─── orchestration ─────────────────────────────────────────────────────────

def convert_all(
    adapters: list[str] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
    state_file: Path = DEFAULT_STATE_FILE,
    config_file: Path = DEFAULT_CONFIG_FILE,
    ignore_file: Path = DEFAULT_IGNORE_FILE,
    since: Optional[str] = None,
    project: Optional[str] = None,
    include_current: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Main entry: convert new sessions across all enabled adapters."""
    config = load_config(config_file)
    state = {} if force else load_state(state_file)
    redact = Redactor(config)
    ignore = IgnoreMatcher.from_file(ignore_file)
    if ignore:
        print(f"==> loaded {len(ignore)} pattern(s) from {ignore_file.name}")

    drop_types = config.get("filters", {}).get("drop_record_types", [])
    live_minutes = config.get("filters", {}).get("live_session_minutes", 60)
    live_cutoff = datetime.now(timezone.utc) - timedelta(minutes=live_minutes)

    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD, got {since!r}", file=sys.stderr)
            return 2

    discover_adapters()
    selected: list[type] = []
    if adapters:
        for name in adapters:
            if name not in REGISTRY:
                print(f"error: unknown adapter {name!r}. Try: {', '.join(REGISTRY)}", file=sys.stderr)
                return 2
            selected.append(REGISTRY[name])
    else:
        selected = [cls for cls in REGISTRY.values() if cls.is_available()]

    if not selected:
        print("No adapters available. Install Claude Code or Codex CLI first.", file=sys.stderr)
        return 1

    converted = unchanged = live = filtered = ignored_count = errors = 0

    for cls in selected:
        adapter = cls(config)
        print(f"==> adapter: {cls.name}")
        sessions = adapter.discover_sessions()
        print(f"  discovered: {len(sessions)} source files")
        for path in sessions:
            project_slug = adapter.derive_project_slug(path)
            if project and project not in project_slug:
                filtered += 1
                continue
            if ignore and ignore.is_ignored(project=project_slug, filename=path.name):
                ignored_count += 1
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                errors += 1
                continue
            key = str(path)
            if state.get(key) == mtime:
                unchanged += 1
                continue

            # Markdown-source adapters (e.g. Obsidian) route through a simple
            # copy-with-redaction path rather than parse_jsonl.
            if path.suffix == ".md":
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    errors += 1
                    continue
                if len(text) < 50:
                    filtered += 1
                    continue
                out_name = path.stem + ".md"
                out_path = out_dir / project_slug / out_name
                if dry_run:
                    print(f"  [dry-run] {out_path.relative_to(REPO_ROOT) if out_path.is_relative_to(REPO_ROOT) else out_path} ({len(text)} bytes)")
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(redact(text), encoding="utf-8")
                    state[key] = mtime
                converted += 1
                continue

            # PDF adapter: extract text → frontmatter'd markdown
            if path.suffix == ".pdf":
                try:
                    md, out_name = adapter.convert_pdf(path, redact=redact)
                except Exception as e:
                    print(f"  skip: {path.name}: {e}", file=sys.stderr)
                    errors += 1
                    continue
                if not md:
                    filtered += 1
                    continue
                out_path = out_dir / project_slug / out_name
                if dry_run:
                    print(f"  [dry-run] {out_path.relative_to(REPO_ROOT) if out_path.is_relative_to(REPO_ROOT) else out_path} ({len(md)} bytes)")
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(md, encoding="utf-8")
                    state[key] = mtime
                converted += 1
                continue

            records = parse_jsonl(path)
            # v0.5 (#109): normalize agent-specific records into the shared
            # Claude-style format before filtering/rendering. This lets each
            # adapter translate its native schema without touching the shared
            # renderer. The default implementation is a no-op for Claude Code.
            records = adapter.normalize_records(records)
            records = filter_records(records, drop_types)
            if not records:
                filtered += 1
                continue
            last_t = latest_record_time(records)
            if last_t and last_t > live_cutoff and not include_current:
                live += 1
                continue
            if since_dt and last_t and last_t < since_dt:
                filtered += 1
                continue
            try:
                md, slug, started = render_session_markdown(
                    records, path, project_slug, redact, config, adapter.is_subagent(path)
                )
            except Exception as e:
                print(f"  error: {path.name}: {e}", file=sys.stderr)
                errors += 1
                continue
            date_str = started.strftime("%Y-%m-%d")
            out_path = out_dir / project_slug / f"{date_str}-{slug}.md"
            if dry_run:
                print(f"  [dry-run] {out_path.relative_to(REPO_ROOT)} ({len(md)} bytes)")
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(md, encoding="utf-8")
                state[key] = mtime
            converted += 1

    if not dry_run and not force:
        save_state(state_file, state)

    print()
    print(
        f"summary: {converted} converted, {unchanged} unchanged, "
        f"{live} live, {filtered} filtered, {ignored_count} ignored, {errors} errors"
    )
    return 0 if errors == 0 else 1
