"""llmwiki CLI.

Usage:
    python3 -m llmwiki <subcommand> [options]

Subcommands:
    init              Scaffold raw/, wiki/, site/ directories
    sync              Convert new .jsonl sessions to markdown
    build             Compile static HTML site from raw/ + wiki/
    serve             Start local HTTP server
    adapters          List available session-store adapters
    graph             Build the knowledge graph (graph/graph.json + graph.html)
    export            Export AI-consumable formats: llms-txt, llms-full-txt, jsonld, sitemap, rss, robots, ai-readme, marp
    lint              Run lint rules against the wiki
    candidates        List / promote / merge / discard candidate pages
    synthesize        Synthesize wiki source pages from raw sessions via LLM
    all               Run the full pipeline: build → graph → export all → lint
    version           Print version and exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from llmwiki import __version__, REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_adapters


def cmd_version(args: argparse.Namespace) -> int:
    print(f"llmwiki {__version__}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline end-to-end: build → graph → export all → lint.

    This is the convenience entry point advertised as ``wiki-all`` in docs and
    slash commands. It executes the usual post-sync steps in the canonical
    order so a single command reproduces a CI-ready site.

    Exit codes:
      0  every step succeeded (lint warnings are informational).
      1  at least one step returned a non-zero exit status.
      2  ``--strict`` was passed and lint reported any error or warning.
    """
    import shlex

    steps: list[tuple[str, list[str]]] = []
    build_args = ["build", "--out", str(args.out)]
    if args.search_mode:
        build_args.extend(["--search-mode", args.search_mode])
    steps.append(("build", build_args))

    if not args.skip_graph:
        steps.append(("graph", ["graph", "--format", "both", "--engine", args.graph_engine]))

    steps.append(("export", ["export", "all", "--out", str(args.out)]))
    # ``lint --fail-on-errors`` so error-severity issues already fail the step;
    # ``--strict`` additionally escalates warnings (checked below).
    lint_argv = ["lint", "--fail-on-errors"] if args.strict else ["lint"]
    steps.append(("lint", lint_argv))

    overall_rc = 0
    lint_rc: Optional[int] = None
    for name, argv in steps:
        print(f"\n==> llmwiki {' '.join(shlex.quote(a) for a in argv)}")
        sub_args = build_parser().parse_args(argv)
        rc = sub_args.func(sub_args)
        if name == "lint":
            lint_rc = rc
            continue  # lint's own exit policy is handled below
        if rc != 0:
            overall_rc = rc if overall_rc == 0 else overall_rc
            if args.fail_fast:
                print(f"error: step '{name}' exited {rc}; stopping (--fail-fast).", file=sys.stderr)
                return rc

    if args.strict:
        # ``--strict`` escalates *any* lint signal — errors OR warnings —
        # into a pipeline failure. Re-read the lint report directly so we
        # don't depend on lint's own exit code, which by design only fires
        # on error-severity issues.
        from llmwiki.lint import load_pages, run_all, summarize
        wiki_dir = REPO_ROOT / "wiki"
        if wiki_dir.is_dir():
            pages = load_pages(wiki_dir)
            issues = run_all(pages)
            counts = summarize(issues) if issues else {}
            errors = counts.get("error", 0)
            warnings = counts.get("warning", 0)
            if errors or warnings:
                print(
                    f"error: --strict: lint reported "
                    f"{errors} error(s) + {warnings} warning(s).",
                    file=sys.stderr,
                )
                return 2

    if lint_rc not in (None, 0) and overall_rc == 0:
        overall_rc = lint_rc

    return overall_rc


def cmd_init(args: argparse.Namespace) -> int:
    """Create raw/, wiki/, site/ directory structure."""
    for name in ("raw/sessions", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/syntheses", "site"):
        p = REPO_ROOT / name
        p.mkdir(parents=True, exist_ok=True)
        keep = p / ".gitkeep"
        if not keep.exists() and not any(p.iterdir()):
            keep.touch()
        print(f"  {p.relative_to(REPO_ROOT)}/")

    # Also create hot/ for per-project caches
    hot_dir = REPO_ROOT / "wiki" / "hot"
    hot_dir.mkdir(parents=True, exist_ok=True)
    keep = hot_dir / ".gitkeep"
    if not keep.exists():
        keep.touch()

    # Seed index/log/overview + navigation files if not present
    seeds = {
        "wiki/index.md": (
            "# Wiki Index\n\n"
            "<!-- #387 U6: each section heading carries a (count) so the index\n"
            "stays scannable as the wiki grows past ~50 pages. Update the count\n"
            "in the heading when adding/removing pages. The index is otherwise\n"
            "kept flat (no nested folders) so a single grep/scan can find any\n"
            "page without descending into a tree. -->\n\n"
            "## Overview (1)\n- [Overview](overview.md)\n\n"
            "## Sources (0)\n\n"
            "## Entities (0)\n\n"
            "## Projects (0)\n\n"
            "## Concepts (0)\n\n"
            "## Syntheses (0)\n"
        ),
        "wiki/overview.md": '---\ntitle: "Overview"\ntype: synthesis\nsources: []\nlast_updated: ""\n---\n\n# Overview\n\n*This page is maintained by your coding agent.*\n',
        "wiki/log.md": "# Wiki Log\n\nAppend-only chronological record of all operations.\n\nFormat: `## [YYYY-MM-DD] <operation> | <title>`\n\n---\n",
        "wiki/hints.md": '---\ntitle: "Navigation Hints"\ntype: navigation\nlast_updated: ""\n---\n\n# Hints\n\nWriting conventions, entity naming rules, and navigation guidance.\nCustomize this file for your project.\n',
        "wiki/hot.md": '---\ntitle: "Hot Cache"\ntype: navigation\nlast_updated: ""\nauto_maintained: true\n---\n\n# Hot Cache\n\n*Auto-maintained. Last 10 session summaries.*\n',
        "wiki/MEMORY.md": '---\ntitle: "Cross-Session Memory"\ntype: navigation\nlast_updated: ""\nmax_lines: 200\n---\n\n# MEMORY\n\n*200-line cap. Auto-consolidated by Auto Dream.*\n\n## User\n\n## Feedback\n\n## Project\n\n## Reference\n',
        "wiki/SOUL.md": '---\ntitle: "Wiki Identity"\ntype: navigation\nlast_updated: ""\n---\n\n# SOUL\n\nThis wiki compiles raw session transcripts into structured, interlinked pages.\nCustomize this file to set your wiki\'s voice and purpose.\n',
        "wiki/CRITICAL_FACTS.md": '---\ntitle: "Critical Facts"\ntype: navigation\nlast_updated: ""\n---\n\n# Critical Facts\n\n- raw/ is immutable — never modify files under raw/\n- Wiki uses Obsidian-style double-bracket syntax for cross-references\n- Confidence: 0.0-1.0, 4-factor formula\n- Lifecycle: draft > reviewed > verified > stale > archived\n',
    }

    # v1.0 (#153): seed dashboard.md from examples/wiki_dashboard.md template
    dashboard_template = REPO_ROOT / "examples" / "wiki_dashboard.md"
    dashboard_target = REPO_ROOT / "wiki" / "dashboard.md"
    if dashboard_template.is_file() and not dashboard_target.is_file():
        dashboard_target.write_text(
            dashboard_template.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        print(f"  seeded wiki/dashboard.md")
    for rel, content in seeds.items():
        p = REPO_ROOT / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            print(f"  seeded {p.relative_to(REPO_ROOT)}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Convert .jsonl sessions to markdown using the enabled adapters."""
    # G-03 (#289): `sync --status` short-circuits into the status reporter.
    if getattr(args, "status", False):
        return cmd_sync_status(args)

    from llmwiki.convert import convert_all

    # v1.2 (#54): vault-overlay mode — resolve the vault early so bad
    # paths fail before we spend time converting sessions.
    if getattr(args, "vault", None):
        from llmwiki.vault import describe_vault, resolve_vault
        try:
            vault = resolve_vault(args.vault)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")
        if args.allow_overwrite:
            print("  --allow-overwrite: existing vault pages may be clobbered")

    rc = convert_all(
        adapters=args.adapter,
        since=args.since,
        project=args.project,
        include_current=args.include_current,
        force=args.force,
    )

    # v1.0 (#157): auto-build and auto-lint after sync.
    # --no-build and --no-lint let users opt out.
    if rc == 0:
        schedule = _load_schedule_config()
        if args.auto_build and _should_run_after_sync(schedule.get("build", "on-sync")):
            print("  auto-build: regenerating site/...")
            from llmwiki.build import build_site
            # #414: sync has explicit user opt-in to mutate wiki/, so it's
            # the right place to seed project stubs.
            build_site(out_dir=REPO_ROOT / "site", seed_project_stubs=True)
        if args.auto_lint and _should_run_after_sync(schedule.get("lint", "manual")):
            print("  auto-lint: running wiki lint...")
            from llmwiki.lint import load_pages, run_all, summarize
            pages = load_pages()
            issues = run_all(pages)
            summary = summarize(issues)
            print(f"  lint: {sum(summary.values())} issues "
                  f"({summary.get('error', 0)} errors, "
                  f"{summary.get('warning', 0)} warnings)")
    return rc


def _load_schedule_config() -> dict[str, str]:
    """Load build/lint schedule config from sessions_config.json."""
    import json as _json
    from llmwiki import REPO_ROOT
    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    if not config_path.is_file():
        return {"build": "on-sync", "lint": "manual"}
    try:
        data = _json.loads(config_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"build": "on-sync", "lint": "manual"}
    schedule = data.get("schedule", {})
    return {
        "build": schedule.get("build", "on-sync"),
        "lint": schedule.get("lint", "manual"),
    }


def _should_run_after_sync(schedule: str) -> bool:
    """Return True if the schedule value indicates running after sync.

    Accepted values: "on-sync", "daily", "weekly", "manual", "never".
    Only "on-sync" triggers from cmd_sync. "daily"/"weekly" run from a
    scheduled task; "manual" and "never" never auto-run.
    """
    return schedule.lower() == "on-sync"


def cmd_build(args: argparse.Namespace) -> int:
    """Build the static HTML site."""
    from llmwiki.build import build_site

    # v1.2 (#54): vault-overlay mode. Validate the path up front so a
    # typo fails fast before the build walks raw/.
    if getattr(args, "vault", None):
        from llmwiki.vault import describe_vault, resolve_vault
        try:
            vault = resolve_vault(args.vault)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")

    return build_site(
        out_dir=args.out,
        synthesize=args.synthesize,
        claude_path=args.claude,
        search_mode=args.search_mode,
        seed_project_stubs=getattr(args, "seed_project_stubs", False),
    )


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve the built site via a local HTTP server."""
    from llmwiki.serve import serve_site
    return serve_site(directory=args.dir, port=args.port, host=args.host, open_browser=args.open)


def _adapter_status(
    name: str,
    adapter_cls: Any,
    config: dict,
) -> tuple[str, str]:
    """Return ``(configured, will_fire)`` labels for one adapter (G-01 · #287).

    * ``configured``: ``explicit`` (user set ``enabled: true`` in the
      config), ``off`` (user set ``enabled: false``), or ``auto``
      (default — no explicit toggle).
    * ``will_fire``: ``yes`` when the next ``sync`` will pick this
      adapter up (available **and** not explicitly off), ``no``
      otherwise.

    The old labels — ``-`` / ``enabled`` / ``disabled`` — read as
    "adapter can't see anything" even when the adapter was discovering
    471 files on the next line.  The new labels say exactly what they
    mean without the user cross-referencing ``sessions_config.json``.
    """
    adapter_cfg = config.get(name, {})
    enabled_in_cfg = None
    if isinstance(adapter_cfg, dict):
        enabled_in_cfg = adapter_cfg.get("enabled", None)
    if enabled_in_cfg is True:
        configured = "explicit"
    elif enabled_in_cfg is False:
        configured = "off"
    else:
        configured = "auto"
    available = adapter_cls.is_available()
    # #326: non-AI adapters are opt-in only, so ``auto`` on an Obsidian /
    # Jira / Meeting / PDF adapter means "available but won't fire".
    is_ai = getattr(adapter_cls, "is_ai_session", True)
    if configured == "off":
        will_fire = "no"
    elif configured == "explicit":
        will_fire = "yes" if available else "no"
    else:  # auto
        will_fire = "yes" if (available and is_ai) else "no"
    return configured, will_fire


def cmd_adapters(args: argparse.Namespace) -> int:
    """List available adapters and their config state.

    G-01 (#287): ``configured`` column now shows ``auto``/``explicit``/
    ``off`` (not ``-``/``enabled``/``disabled``) and a new
    ``will_fire`` column says whether the next ``sync`` will pick the
    adapter up.

    G-02 (#288): ``--wide`` disables the description cap.
    """
    import json as _json
    import shutil as _shutil

    discover_adapters()
    if not REGISTRY:
        print("No adapters registered.")
        return 0

    # Load user config to show enable/disable state
    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    config: dict = {}
    if config_path.is_file():
        try:
            config = _json.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    # Description column width: 40 by default, full line with --wide,
    # or auto-fit to terminal (minus the four fixed columns + gutters).
    # #387 U2: column names renamed from default/configured/will_fire to
    # present/enabled/active — they read at a glance without needing the
    # legend below.
    wide = bool(getattr(args, "wide", False))
    if wide:
        desc_width: Optional[int] = None  # no cap
    else:
        term_cols = _shutil.get_terminal_size(fallback=(80, 24)).columns
        # Layout: "  name(16)  present(8)  enabled(10)  active(7)  desc"
        desc_width = max(30, term_cols - 55)

    print("Registered adapters:")
    dash = "-"
    header = (
        f"  {'name':<16}  {'present':<8}  {'enabled':<10}  "
        f"{'active':<7}  description"
    )
    print(header)
    sep_desc = "-" * (desc_width if desc_width is not None else len("description"))
    print(
        f"  {dash * 16}  {dash * 8}  {dash * 10}  {dash * 7}  {sep_desc}"
    )
    for name, adapter_cls in sorted(REGISTRY.items()):
        present = "yes" if adapter_cls.is_available() else "no"
        enabled, active = _adapter_status(name, adapter_cls, config)
        desc = adapter_cls.description()
        if desc_width is not None and len(desc) > desc_width:
            desc = desc[: max(desc_width - 3, 1)] + "..."
        print(
            f"  {name:<16}  {present:<8}  {enabled:<10}  "
            f"{active:<7}  {desc}"
        )

    print()
    print("Columns:")
    print("  present  — is the adapter's session store visible on disk?")
    print("  enabled  — auto (default), explicit (enabled:true in config), off (enabled:false)")
    print("  active   — yes/no — will `sync` pick this adapter up on its next run?")
    if not wide:
        print()
        print("Pass --wide to see untruncated descriptions.")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Query the knowledge graph with a natural language question."""
    from llmwiki.graphify_bridge import is_available, query_graph
    if not is_available():
        print("error: graphify not installed. Run: pip install llmwiki[graph]", file=sys.stderr)
        return 2
    question = " ".join(args.question)
    result = query_graph(question, depth=args.depth, token_budget=args.budget)
    print(result)
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Build the knowledge graph from wiki/ wikilinks."""
    engine = getattr(args, "engine", "graphify")
    if engine == "graphify":
        from llmwiki.graphify_bridge import is_available, build_graphify_graph
        if not is_available():
            print("  graphify not installed — falling back to builtin engine", file=sys.stderr)
            print("  install with: pip install llmwiki[graph]", file=sys.stderr)
            engine = "builtin"
        else:
            result = build_graphify_graph()
            return 0 if result.get("graph") is not None else 1

    from llmwiki.graph import build_and_report
    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(write_json_flag=write_json, write_html_flag=write_html)


def cmd_sync_status(args: argparse.Namespace) -> int:
    """Report sync observability — last run, per-adapter counters, quarantined sources.

    G-03 (#289): emits a one-screen status report so operators can see
    *what synced / what didn't / why*.  Reads ``.llmwiki-state.json``
    for the last-sync timestamp + per-adapter counters (written there
    by ``convert_all``) and ``.llmwiki-quarantine.json`` for the failing
    sources.
    """
    import json as _json
    from datetime import datetime, timezone
    from pathlib import Path as _Path

    from llmwiki import quarantine as _q
    from llmwiki.convert import DEFAULT_STATE_FILE

    state: dict = {}
    if DEFAULT_STATE_FILE.is_file():
        try:
            state = _json.loads(DEFAULT_STATE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            state = {}

    meta = state.pop("_meta", {}) if isinstance(state, dict) else {}
    counters = state.pop("_counters", {}) if isinstance(state, dict) else {}

    last_sync = meta.get("last_sync")
    if last_sync:
        try:
            ts = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - ts
            human = f"{int(delta.total_seconds() // 3600)}h ago"
            print(f"Last sync: {last_sync} ({human})")
        except ValueError:
            print(f"Last sync: {last_sync}")
    else:
        print("Last sync: never (or pre-upgrade state file)")

    print()
    if counters:
        print("Adapters:")
        header = (
            f"  {'adapter':<16}  {'discovered':>10}  {'converted':>9}  "
            f"{'unchanged':>9}  {'live':>5}  {'filtered':>8}  {'errored':>7}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))
        for name, c in sorted(counters.items()):
            print(
                f"  {name:<16}  {c.get('discovered', 0):>10}  "
                f"{c.get('converted', 0):>9}  "
                f"{c.get('unchanged', 0):>9}  "
                f"{c.get('live', 0):>5}  "
                f"{c.get('filtered', 0):>8}  "
                f"{c.get('errored', 0):>7}"
            )
    else:
        print("No per-adapter counters recorded (run `llmwiki sync` first).")

    print()
    orphans = [
        k for k in state.keys()
        if isinstance(k, str) and k.startswith(tuple(f"{n}::" for n in counters))
        and not _resolve_key_exists(k)
    ]
    if orphans:
        print(f"Orphan state entries: {len(orphans)} (source path no longer on disk)")

    # Read the module-level default at call time so monkeypatches take effect.
    quar_counts = _q.count_by_adapter(_q.DEFAULT_QUARANTINE_FILE)
    if quar_counts:
        total = sum(quar_counts.values())
        print(f"Quarantined sources: {total} "
              f"({', '.join(f'{k}:{v}' for k, v in sorted(quar_counts.items()))})")
    else:
        print("Quarantined sources: 0")

    if args.recent:
        from llmwiki.log_reader import recent_events
        log_path = REPO_ROOT / "wiki" / "log.md"
        events = recent_events(log_path, limit=args.recent, operations={"sync", "synthesize"})
        if events:
            print()
            print(f"Recent activity (last {len(events)}):")
            for e in events:
                print(f"  [{e.date.isoformat()}] {e.operation:<12} {e.title}")

    return 0


def _resolve_key_exists(key: str) -> bool:
    """Check whether a portable state-file key points at an extant file."""
    from pathlib import Path as _Path
    if "::" not in key:
        return _Path(key).exists()
    _, rel = key.split("::", 1)
    candidate = _Path.home() / rel
    return candidate.exists() or _Path(rel).exists()


def cmd_export(args: argparse.Namespace) -> int:
    """Export AI-consumable formats from the compiled wiki."""
    import sys as _sys
    from llmwiki.exporters import (
        write_llms_txt,
        write_llms_full_txt,
        write_graph_jsonld,
        write_sitemap,
        write_rss,
        write_robots_txt,
        write_ai_readme,
        write_marp,
        export_all,
    )
    from llmwiki.build import discover_sources, group_by_project, RAW_SESSIONS

    out_dir = args.out if args.out else REPO_ROOT / "site"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = discover_sources(RAW_SESSIONS)
    if not sources:
        print("error: no sources found. Run 'llmwiki sync' first.", file=_sys.stderr)
        return 2
    groups = group_by_project(sources)

    format_ = args.format
    if format_ == "all":
        paths = export_all(out_dir, groups, sources)
        for name, p in sorted(paths.items()):
            print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
        return 0

    topic = getattr(args, "topic", "") or ""
    mapping = {
        "llms-txt": lambda: write_llms_txt(out_dir, groups, len(sources)),
        "llms-full-txt": lambda: write_llms_full_txt(out_dir, sources),
        "jsonld": lambda: write_graph_jsonld(out_dir, groups, sources),
        "sitemap": lambda: write_sitemap(out_dir, groups, sources),
        "rss": lambda: write_rss(out_dir, sources),
        "robots": lambda: write_robots_txt(out_dir),
        "ai-readme": lambda: write_ai_readme(out_dir, groups, len(sources)),
        "marp": lambda: write_marp(out_dir, sources, topic=topic),
    }
    fn = mapping.get(format_)
    if not fn:
        print(f"error: unknown format {format_!r}. Valid: {sorted(mapping.keys())} or 'all'", file=_sys.stderr)
        return 2
    p = fn()
    print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Run every registered lint rule against the wiki and print a report."""
    from llmwiki.lint import REGISTRY, load_pages, run_all, summarize  # noqa: F401

    wiki_dir = args.wiki_dir or (REPO_ROOT / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    pages = load_pages(wiki_dir)
    if not pages:
        print(f"  no pages found in {wiki_dir}")
        return 0

    selected = args.rules.split(",") if args.rules else None
    issues = run_all(
        pages,
        include_llm=args.include_llm,
        selected=selected,
    )

    summary = summarize(issues)

    if args.json:
        import json as _json
        print(_json.dumps({
            "summary": summary,
            "issues": issues,
            "total_pages": len(pages),
        }, indent=2))
    else:
        print(f"  scanned {len(pages)} pages")
        print(f"  {sum(summary.values())} issues: "
              f"{summary.get('error', 0)} errors, "
              f"{summary.get('warning', 0)} warnings, "
              f"{summary.get('info', 0)} info")
        print()
        if issues:
            by_rule: dict[str, list[dict[str, str]]] = {}
            for i in issues:
                by_rule.setdefault(i["rule"], []).append(i)
            for rule, rule_issues in sorted(by_rule.items()):
                print(f"## {rule} ({len(rule_issues)})")
                for i in rule_issues[:20]:
                    print(f"  [{i['severity']}] {i['page']}: {i['message']}")
                if len(rule_issues) > 20:
                    print(f"  ... and {len(rule_issues) - 20} more")
                print()

    if args.fail_on_errors and summary.get("error", 0) > 0:
        return 1
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize wiki source pages from raw sessions (v1.1.0 · #35).

    Uses the backend selected via ``synthesis.backend`` in
    ``sessions_config.json`` (dummy | ollama). ``--check`` prints backend
    availability without running synthesis — useful for diagnosing Ollama
    connectivity before a long sync. ``--estimate`` prints a cached-vs-fresh
    token + dollar breakdown before spending money (#50).
    """
    import json as _json
    from llmwiki.synth.pipeline import resolve_backend, synthesize_new_sessions

    config: dict = {}
    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    if config_path.is_file():
        try:
            config = _json.loads(config_path.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            config = {}

    if args.estimate:
        return _synthesize_estimate()

    # #316: agent-delegate operations that don't need a backend.
    if args.list_pending:
        return _synthesize_list_pending()
    if args.complete:
        return _synthesize_complete(args)

    backend = resolve_backend(config)
    print(f"Backend: {backend.name}")

    if args.check:
        available = backend.is_available()
        print(f"Available: {available}")
        return 0 if available else 1

    if not backend.is_available():
        print(
            f"error: backend {backend.name} is not available. "
            "Start the server or change synthesis.backend in config.",
            file=sys.stderr,
        )
        return 1

    summary = synthesize_new_sessions(
        backend=backend,
        force=args.force,
    )
    print(
        f"Scanned {summary['total_scanned']}, new {summary['new_files']}, "
        f"synthesized {summary['synthesized']}, skipped {summary['skipped']}"
    )
    if summary["errors"]:
        for err in summary["errors"]:
            print(f"  ! {err}", file=sys.stderr)
        return 1
    return 0


# ─── #316 agent-delegate CLI helpers ─────────────────────────────────


def _synthesize_list_pending() -> int:
    """Print the pending-prompts table for ``--list-pending``.

    Two-column layout: uuid │ slug · project · date · prompt-path.
    Exit 0 even when empty — the slash-command layer treats "nothing
    pending" as a success signal.
    """
    from llmwiki.synth.agent_delegate import list_pending

    rows = list_pending()
    if not rows:
        print("No pending prompts.")
        return 0
    # Max-width uuid column for alignment.
    uuid_w = max(len(r["uuid"]) for r in rows)
    print(f"{'UUID':<{uuid_w}}  SLUG · PROJECT · DATE")
    print(f"{'-' * uuid_w}  " + "-" * 40)
    for r in rows:
        meta = " · ".join(
            part for part in (r["slug"], r["project"], r["date"]) if part
        )
        print(f"{r['uuid']:<{uuid_w}}  {meta}")
    print(f"\n{len(rows)} pending prompt(s).")
    return 0


def _synthesize_complete(args: argparse.Namespace) -> int:
    """Rewrite a placeholder wiki page with the agent's synthesis.

    Reads the synthesized body from ``args.body`` (file) or stdin, calls
    :func:`llmwiki.synth.agent_delegate.complete_pending` to replace the
    sentinel + prompt-file pair with the real content.  Exit codes:

    * ``0`` — success
    * ``1`` — missing --page, uuid mismatch, missing sentinel, or I/O
      error
    """
    from llmwiki.synth.agent_delegate import complete_pending

    if not args.page:
        print("error: --complete requires --page <path>", file=sys.stderr)
        return 1

    page_path = Path(args.page)
    if not page_path.is_absolute():
        page_path = REPO_ROOT / page_path

    if args.body:
        body_path = Path(args.body)
        if not body_path.is_absolute():
            body_path = REPO_ROOT / body_path
        try:
            body = body_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"error: reading --body {body_path}: {e}", file=sys.stderr)
            return 1
    else:
        body = sys.stdin.read()
        if not body:
            print(
                "error: --complete expects a body on stdin or via --body",
                file=sys.stderr,
            )
            return 1

    try:
        complete_pending(args.complete, body, page_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"completed: {page_path}")
    return 0


def synthesize_estimate_report(
    *,
    raw_sessions: Optional[list[tuple[Any, dict, str]]] = None,
    state_keys: Optional[set[str]] = None,
    prefix_tokens: Optional[int] = None,
    output_tokens_per_call: int = 1000,
    model: Optional[str] = None,
) -> dict:
    """Compute the incremental vs full-force cost report (G-07 · #293).

    Returns a plain dict so the CLI can render it AND tests can inspect
    the numbers without parsing stdout.  Keys:

    * ``corpus`` — total raw sessions discovered under ``raw/sessions/``
    * ``synthesized`` — count already synthesized (from state file)
    * ``new`` — ``corpus - synthesized``
    * ``incremental_usd`` — dollars to synthesize the ``new`` bucket
    * ``full_force_usd`` — dollars to re-synthesize the **whole** corpus
      with ``--force`` (one cache write + N-1 cache hits)
    * ``prefix_tokens`` — tokens in the stable CLAUDE.md + index.md +
      overview.md prefix
    * ``model`` — model id used for pricing
    * ``warnings`` — list of human-readable warnings (e.g. prefix too
      small to be cached)

    Any of the args can be injected for tests; the default reads from
    disk and is what the CLI invokes.
    """
    from llmwiki.cache import (
        DEFAULT_MODEL,
        estimate_cost,
        estimate_tokens,
        warn_prefix_too_small,
    )
    from llmwiki.synth.pipeline import _discover_raw_sessions, _load_state

    chosen_model = model or DEFAULT_MODEL
    warnings: list[str] = []

    if prefix_tokens is None:
        prefix_parts: list[str] = []
        for rel in ("CLAUDE.md", "wiki/index.md", "wiki/overview.md"):
            p = REPO_ROOT / rel
            if p.is_file():
                prefix_parts.append(p.read_text(encoding="utf-8"))
        prefix_tokens = estimate_tokens("\n".join(prefix_parts))
    prefix_warning = warn_prefix_too_small(prefix_tokens)
    if prefix_warning:
        warnings.append(prefix_warning)

    if raw_sessions is None:
        raw_sessions = _discover_raw_sessions()
    if state_keys is None:
        state_keys = set(_load_state().keys())

    corpus = len(raw_sessions)

    # The real synth state stores rel-paths under ``raw/sessions/``
    # (e.g. ``proj/2026-04-09-slug.md``).  Match against those first;
    # fall back to bare filename + suffix-endswith for tests that
    # inject simpler keys.  A session counts as "synthesized" if any
    # of those three keys already appears in state_keys.
    from llmwiki.synth.pipeline import RAW_SESSIONS as _RAW
    synthed = 0
    new_bodies: list[str] = []
    for p, _meta, body in raw_sessions:
        keys_to_try: set[str] = set()
        name = getattr(p, "name", str(p))
        keys_to_try.add(name)
        if hasattr(p, "relative_to"):
            try:
                keys_to_try.add(str(p.relative_to(_RAW)))
            except (ValueError, AttributeError):
                pass
        keys_to_try.add(str(p))
        matched = bool(keys_to_try & state_keys) or any(
            isinstance(k, str) and k.endswith(name) for k in state_keys
        )
        if matched:
            synthed += 1
        else:
            new_bodies.append(body)
    new = corpus - synthed

    def _bucket_usd(bodies: list[str]) -> float:
        if not bodies:
            return 0.0
        first = estimate_cost(
            cached_tokens=prefix_tokens,
            fresh_tokens=estimate_tokens(bodies[0]),
            output_tokens=output_tokens_per_call,
            model=chosen_model,
            cache_hit=False,
        )
        total = first.usd
        for body in bodies[1:]:
            est = estimate_cost(
                cached_tokens=prefix_tokens,
                fresh_tokens=estimate_tokens(body),
                output_tokens=output_tokens_per_call,
                model=chosen_model,
                cache_hit=True,
            )
            total += est.usd
        return total

    incremental_usd = _bucket_usd(new_bodies)
    full_force_bodies = [body for _p, _m, body in raw_sessions]
    full_force_usd = _bucket_usd(full_force_bodies)

    return {
        "corpus": corpus,
        "synthesized": synthed,
        "new": new,
        "incremental_usd": incremental_usd,
        "full_force_usd": full_force_usd,
        "prefix_tokens": prefix_tokens,
        "model": chosen_model,
        "warnings": warnings,
    }


def _synthesize_estimate() -> int:
    """Print the G-07 incremental-vs-full-force cost report (v1.1.0 · #50 · #293).

    Transparency over one-liner: reads the state file so the user sees
    exactly which bucket gets billed next. The old ``--estimate`` printed
    a single number without saying whether it covered the whole corpus
    or just the delta.
    """
    report = synthesize_estimate_report()

    for w in report["warnings"]:
        print(f"warning: {w}")

    print(f"Corpus:                {report['corpus']:>6} sessions in raw/sessions/")
    print(f"Already synthesized:   {report['synthesized']:>6} pages in wiki/sources/")
    print(f"New since last run:    {report['new']:>6}")
    print()
    print(f"Prefix: {report['prefix_tokens']:,} tok  Model: {report['model']}")
    print()
    if report["new"] == 0:
        print(f"Incremental sync:  $0.0000  (nothing new — this is a no-op)")
    else:
        print(
            f"Incremental sync:  ${report['incremental_usd']:.4f}  "
            f"(synthesize the {report['new']} new session(s))"
        )
    print(
        f"Full re-synth:     ${report['full_force_usd']:.4f}  "
        f"(--force — {report['corpus']} session(s), 1 cache write + {max(report['corpus'] - 1, 0)} hits)"
    )
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    """List / promote / merge / discard candidate pages (v1.1.0 · #51)."""
    import json as _json
    from llmwiki.candidates import (
        list_candidates,
        promote,
        merge as merge_candidate,
        discard,
        stale_candidates,
    )

    wiki_dir = args.wiki_dir or (REPO_ROOT / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    action = args.action

    if action == "list":
        items = (
            stale_candidates(wiki_dir, threshold_days=args.stale_days)
            if args.stale else list_candidates(wiki_dir)
        )
        if args.json:
            # Path isn't JSON-serializable — drop it for the output
            cleaned = [{k: v for k, v in c.items() if k != "abs_path"} for c in items]
            print(_json.dumps(cleaned, indent=2))
        else:
            label = "stale" if args.stale else "pending"
            print(f"  {len(items)} {label} candidate(s):")
            for c in items:
                age = f"{c['age_days']}d" if c["created"] else "unknown age"
                print(f"    [{c['kind']:9}] {c['slug']}  ({age})  — {c['title']}")
        return 0

    if action == "promote":
        if not args.slug:
            print("error: --slug is required for promote", file=sys.stderr)
            return 2
        path = promote(args.slug, wiki_dir, kind=args.kind)
        print(f"  promoted → {path.relative_to(wiki_dir)}")
        return 0

    if action == "merge":
        if not args.slug or not args.into:
            print("error: both --slug and --into are required for merge", file=sys.stderr)
            return 2
        path = merge_candidate(args.slug, wiki_dir, into_slug=args.into, kind=args.kind)
        print(f"  merged into → {path.relative_to(wiki_dir)}")
        return 0

    if action == "discard":
        if not args.slug:
            print("error: --slug is required for discard", file=sys.stderr)
            return 2
        path = discard(args.slug, wiki_dir, reason=args.reason, kind=args.kind)
        print(f"  discarded → {path.relative_to(wiki_dir)}")
        return 0

    print(f"error: unknown action {action!r}", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmwiki",
        description="LLM-powered knowledge base from Claude Code and Codex CLI sessions.",
    )
    p.add_argument("--version", action="version", version=f"llmwiki {__version__}")

    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    # init
    init = sub.add_parser("init", help="Scaffold raw/, wiki/, site/ directories")
    init.set_defaults(func=cmd_init)

    # sync
    sync = sub.add_parser("sync", help="Convert new .jsonl sessions to markdown")
    sync.add_argument("--adapter", nargs="*", default=None, help="Adapter(s) to run; default: all available")
    sync.add_argument("--since", type=str, help="Only sessions on or after YYYY-MM-DD")
    sync.add_argument("--project", type=str, help="Substring filter on project slug")
    sync.add_argument("--include-current", action="store_true", help="Don't skip live sessions (<60 min)")
    sync.add_argument("--force", action="store_true", help="Ignore state file, reconvert everything")
    sync.add_argument(
        "--auto-build", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, rebuild the site when sessions_config.json's "
             "schedule.build is 'on-sync' (default: on; pass --no-auto-build to skip)",
    )
    sync.add_argument(
        "--auto-lint", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, run lint when sessions_config.json's "
             "schedule.lint is 'on-sync' (default: on; pass --no-auto-lint to skip)",
    )
    sync.add_argument(
        "--vault", type=Path, default=None,
        help="Vault-overlay mode (#54): write new pages inside an existing "
             "Obsidian / Logseq vault instead of the repo's wiki/ directory",
    )
    sync.add_argument(
        "--allow-overwrite", action="store_true",
        help="With --vault: allow clobbering existing vault pages "
             "(default: refuse, append under ## Connections instead)",
    )
    sync.add_argument(
        "--status", action="store_true",
        help="Show last-sync time + per-adapter counters + quarantine "
             "(G-03 · #289). Does not run a sync.",
    )
    sync.add_argument(
        "--recent", type=int, default=0,
        help="With --status: also show last N recent log entries.",
    )
    sync.set_defaults(func=cmd_sync)

    # build
    build = sub.add_parser("build", help="Compile static HTML site from raw/ + wiki/")
    build.add_argument("--out", type=Path, default=REPO_ROOT / "site", help="Output dir (default: site/)")
    build.add_argument("--synthesize", action="store_true", help="Call claude CLI for overview synthesis")
    build.add_argument("--claude", type=str, default="/usr/local/bin/claude", help="Path to claude CLI")
    build.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode (#53): auto picks tree vs flat from heading depth",
    )
    build.add_argument(
        "--vault", type=Path, default=None,
        help="Vault-overlay mode (#54): build from an existing Obsidian / "
             "Logseq vault. Still writes site output to --out.",
    )
    build.add_argument(
        "--seed-project-stubs", action="store_true", dest="seed_project_stubs",
        help="(#414) Auto-create wiki/projects/<slug>.md stubs for any "
             "newly-discovered project that doesn't have a metadata file. "
             "Off by default — `build` is read-only on wiki/. Use `sync` "
             "(which already mutates wiki/) for routine seeding, or pass "
             "this flag to opt in from CI/scripts.",
    )
    build.set_defaults(func=cmd_build)

    # serve
    serve = sub.add_parser("serve", help="Start local HTTP server")
    serve.add_argument("--dir", type=Path, default=REPO_ROOT / "site", help="Directory to serve (default: site/)")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--host", type=str, default="127.0.0.1")
    serve.add_argument("--open", action="store_true", help="Open browser after starting")
    serve.set_defaults(func=cmd_serve)

    # adapters
    ads = sub.add_parser("adapters", help="List available adapters")
    ads.add_argument(
        "--wide",
        action="store_true",
        help="Show untruncated adapter descriptions (G-02 · #288).",
    )
    ads.set_defaults(func=cmd_adapters)

    # graph
    graph = sub.add_parser("graph", help="Build the knowledge graph (graph/graph.json + graph.html)")
    graph.add_argument("--format", choices=["json", "html", "both"], default="both")
    graph.add_argument(
        "--engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine: 'graphify' (AI-powered, default) or 'builtin' (stdlib wikilinks fallback)",
    )
    graph.set_defaults(func=cmd_graph)

    # export (v0.4)
    exp2 = sub.add_parser(
        "export",
        help="Export AI-consumable formats: llms-txt, llms-full-txt, jsonld, sitemap, rss, robots, ai-readme, marp (or 'all')",
    )
    exp2.add_argument(
        "format",
        choices=["llms-txt", "llms-full-txt", "jsonld", "sitemap", "rss", "robots", "ai-readme", "marp", "all"],
        help="Export format",
    )
    exp2.add_argument("--out", type=Path, default=None, help="Output directory (default: site/)")
    exp2.add_argument("--topic", type=str, default="", help="Topic filter for marp slide generation")
    exp2.set_defaults(func=cmd_export)

    # lint (v1.0, #155) — live count via the rule registry (currently 15)
    from llmwiki.lint import REGISTRY as _LINT_REG
    from llmwiki.lint import rules as _lint_rules  # noqa: F401 — force registration
    lint = sub.add_parser(
        "lint",
        help=f"Run all {len(_LINT_REG)} lint rules against the wiki",
    )
    lint.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    lint.add_argument("--rules", type=str, default=None,
                      help="Comma-separated rule names (default: all applicable)")
    lint.add_argument("--include-llm", action="store_true",
                      help="Also run LLM-powered rules (requires --llm-callback)")
    lint.add_argument("--json", action="store_true", help="JSON output")
    lint.add_argument("--fail-on-errors", action="store_true",
                      help="Exit non-zero if any error-severity issues found")
    lint.set_defaults(func=cmd_lint)

    # candidates (v1.1, #51) — approval workflow
    cand = sub.add_parser(
        "candidates",
        help="List / promote / merge / discard candidate wiki pages (approval workflow)",
    )
    cand.add_argument(
        "action", choices=["list", "promote", "merge", "discard"],
        help="What to do with candidates",
    )
    cand.add_argument("--slug", type=str, default=None,
                      help="Candidate slug (required for promote/merge/discard)")
    cand.add_argument("--into", type=str, default=None,
                      help="For merge: slug of the page to merge into")
    cand.add_argument("--reason", type=str, default="",
                      help="For discard: why the candidate is being rejected")
    cand.add_argument("--kind", type=str, default=None,
                      choices=["entities", "concepts", "sources", "syntheses"],
                      help="Subtree (auto-detected if omitted)")
    cand.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    cand.add_argument("--stale", action="store_true",
                      help="For list: only show stale candidates")
    cand.add_argument("--stale-days", type=int, default=30,
                      help="Staleness threshold in days (default 30)")
    cand.add_argument("--json", action="store_true", help="JSON output for list")
    cand.set_defaults(func=cmd_candidates)

    # synthesize (v1.1, #35) — LLM-backed wiki page synthesis
    syn = sub.add_parser(
        "synthesize",
        help="Synthesize wiki source pages from raw sessions via LLM backend",
    )
    syn.add_argument(
        "--check", action="store_true",
        help="Probe backend availability and exit (exit 0 if reachable)",
    )
    syn.add_argument(
        "--force", action="store_true",
        help="Ignore state file, re-synthesize all sessions",
    )
    syn.add_argument(
        "--estimate", action="store_true",
        help="Print cached-vs-fresh token + dollar estimate without calling a backend (#50)",
    )
    # #316 — agent-delegate backend helpers.
    syn.add_argument(
        "--list-pending", action="store_true",
        help="List pending prompts awaiting agent synthesis (agent-delegate backend, #316)",
    )
    syn.add_argument(
        "--complete", metavar="UUID", default=None,
        help="Complete a pending synthesis: read body from --body or stdin, rewrite --page in place (#316)",
    )
    syn.add_argument(
        "--page", metavar="PATH", default=None,
        help="Target wiki source page for --complete (path relative to repo root or absolute)",
    )
    syn.add_argument(
        "--body", metavar="PATH", default=None,
        help="Read synthesized body from this file for --complete (default: stdin)",
    )
    syn.set_defaults(func=cmd_synthesize)

    # query — natural-language graph query
    qry = sub.add_parser("query", help="Query the knowledge graph with a question")
    qry.add_argument("question", nargs="+", help="The question to ask")
    qry.add_argument("--depth", type=int, default=3, help="BFS traversal depth (default: 3)")
    qry.add_argument("--budget", type=int, default=2000, help="Max output tokens (default: 2000)")
    qry.set_defaults(func=cmd_query)

    # version
    ver = sub.add_parser("version", help="Print version")
    ver.set_defaults(func=cmd_version)

    # all — run build + graph + export all + lint in sequence
    all_p = sub.add_parser(
        "all",
        help="Run the full pipeline: build → graph → export all → lint",
    )
    all_p.add_argument(
        "--out", type=Path, default=REPO_ROOT / "site",
        help="Output dir for build + export (default: site/)",
    )
    all_p.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode passed through to build (default: auto)",
    )
    all_p.add_argument(
        "--graph-engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine passed through to graph (default: graphify)",
    )
    all_p.add_argument(
        "--skip-graph", action="store_true",
        help="Skip the graph step (useful when graphify is not installed)",
    )
    all_p.add_argument(
        "--fail-fast", action="store_true",
        help="Stop at the first non-zero step (default: continue, report worst exit code)",
    )
    all_p.add_argument(
        "--strict", action="store_true",
        help="Exit 2 if lint reports any errors/warnings",
    )
    all_p.set_defaults(func=cmd_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
