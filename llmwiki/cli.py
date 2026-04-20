"""llmwiki CLI.

Usage:
    python3 -m llmwiki <subcommand> [options]

Subcommands:
    init              Scaffold raw/, wiki/, site/ directories
    sync              Convert new .jsonl sessions to markdown
    build             Compile static HTML site from raw/ + wiki/
    serve             Start local HTTP server
    graph             Build the knowledge graph (graph/graph.json + graph.html)
    watch             Watch agent session stores and auto-sync on change
    export-obsidian   Export the compiled wiki into an Obsidian vault
    export-qmd        Export the wiki as a self-contained qmd collection
    adapters          List available session-store adapters
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
        "wiki/index.md": "# Wiki Index\n\n## Overview\n- [Overview](overview.md)\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n",
        "wiki/overview.md": '---\ntitle: "Overview"\ntype: synthesis\nsources: []\nlast_updated: ""\n---\n\n# Overview\n\n*This page is maintained by your coding agent.*\n',
        "wiki/log.md": "# Wiki Log\n\nAppend-only chronological record of all operations.\n\nFormat: `## [YYYY-MM-DD] <operation> | <title>`\n\n---\n",
        "wiki/hints.md": '---\ntitle: "Navigation Hints"\ntype: navigation\nlast_updated: ""\n---\n\n# Hints\n\nWriting conventions, entity naming rules, and navigation guidance.\nCustomize this file for your project.\n',
        "wiki/hot.md": '---\ntitle: "Hot Cache"\ntype: navigation\nlast_updated: ""\nauto_maintained: true\n---\n\n# Hot Cache\n\n*Auto-maintained. Last 10 session summaries.*\n',
        "wiki/MEMORY.md": '---\ntitle: "Cross-Session Memory"\ntype: navigation\nlast_updated: ""\nmax_lines: 200\n---\n\n# MEMORY\n\n*200-line cap. Auto-consolidated by Auto Dream.*\n\n## User\n\n## Feedback\n\n## Project\n\n## Reference\n',
        "wiki/SOUL.md": '---\ntitle: "Wiki Identity"\ntype: navigation\nlast_updated: ""\n---\n\n# SOUL\n\nThis wiki compiles raw session transcripts into structured, interlinked pages.\nCustomize this file to set your wiki\'s voice and purpose.\n',
        "wiki/CRITICAL_FACTS.md": '---\ntitle: "Critical Facts"\ntype: navigation\nlast_updated: ""\n---\n\n# Critical Facts\n\n- raw/ is immutable — never modify files under raw/\n- Wiki uses [[wikilinks]] for cross-references\n- Confidence: 0.0-1.0, 4-factor formula\n- Lifecycle: draft > reviewed > verified > stale > archived\n',
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
        dry_run=args.dry_run,
    )
    # v0.7 (#96): optionally download remote images after conversion.
    if args.download_images:
        from llmwiki.image_pipeline import process_markdown_images
        from llmwiki import REPO_ROOT
        raw_sessions = REPO_ROOT / "raw" / "sessions"
        assets_dir = REPO_ROOT / "raw" / "assets"
        total_dl = total_fail = total_skip = 0
        if raw_sessions.exists():
            for md_file in sorted(raw_sessions.rglob("*.md")):
                dl, fail, skip = process_markdown_images(
                    md_file, assets_dir, dry_run=args.dry_run,
                )
                total_dl += dl
                total_fail += fail
                total_skip += skip
        print(
            f"  images: {total_dl} downloaded, {total_fail} failed, "
            f"{total_skip} skipped (cached)"
        )

    # v1.0 (#157): auto-build and auto-lint after sync.
    # --no-build and --no-lint let users opt out.
    if rc == 0 and not args.dry_run:
        schedule = _load_schedule_config()
        if args.auto_build and _should_run_after_sync(schedule.get("build", "on-sync")):
            print("  auto-build: regenerating site/...")
            from llmwiki.build import build_site
            build_site(out_dir=REPO_ROOT / "site")
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
    will_fire = "yes" if available and configured != "off" else "no"
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
    wide = bool(getattr(args, "wide", False))
    if wide:
        desc_width: Optional[int] = None  # no cap
    else:
        term_cols = _shutil.get_terminal_size(fallback=(80, 24)).columns
        # Layout: "  name(16)  default(8)  configured(10)  will_fire(9)  desc" — fixed overhead ~55.
        desc_width = max(30, term_cols - 57)

    print("Registered adapters:")
    dash = "-"
    header = (
        f"  {'name':<16}  {'default':<8}  {'configured':<10}  "
        f"{'will_fire':<9}  description"
    )
    print(header)
    sep_desc = "-" * (desc_width if desc_width is not None else len("description"))
    print(
        f"  {dash * 16}  {dash * 8}  {dash * 10}  {dash * 9}  {sep_desc}"
    )
    for name, adapter_cls in sorted(REGISTRY.items()):
        default_avail = "yes" if adapter_cls.is_available() else "no"
        configured, will_fire = _adapter_status(name, adapter_cls, config)
        desc = adapter_cls.description()
        if desc_width is not None and len(desc) > desc_width:
            desc = desc[: max(desc_width - 3, 1)] + "..."
        print(
            f"  {name:<16}  {default_avail:<8}  {configured:<10}  "
            f"{will_fire:<9}  {desc}"
        )

    print()
    print("Columns:")
    print("  default    — is the adapter's session store present on disk?")
    print("  configured — auto (default), explicit (enabled:true in config), off (enabled:false)")
    print("  will_fire  — will `sync` pick this adapter up on its next run?")
    if not wide:
        print()
        print("Pass --wide to see untruncated descriptions.")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Build the knowledge graph from wiki/ wikilinks."""
    from llmwiki.graph import build_and_report
    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(write_json_flag=write_json, write_html_flag=write_html)


def cmd_log(args: argparse.Namespace) -> int:
    """Query ``wiki/log.md`` structurally (G-13 · #299).

    Examples::

        llmwiki log                                 # last 10 of any op
        llmwiki log --since 2026-04-01
        llmwiki log --operation sync,synthesize
        llmwiki log --limit 50
        llmwiki log --format json
    """
    import json as _json
    from datetime import date as _date

    from llmwiki.log_reader import parse_log, recent_events

    log_path = REPO_ROOT / "wiki" / "log.md"
    if not log_path.is_file():
        print(f"no log at {log_path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    ops: Optional[set[str]] = None
    if args.operation:
        ops = {o.strip().lower() for o in args.operation.split(",") if o.strip()}

    events = recent_events(log_path, limit=max(args.limit, 0) or 10**9, operations=ops)

    if args.since:
        try:
            cutoff = _date.fromisoformat(args.since)
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD, got {args.since!r}", file=sys.stderr)
            return 2
        events = [e for e in events if e.date >= cutoff]

    if args.limit > 0:
        events = events[: args.limit]

    if args.format == "json":
        print(_json.dumps([
            {
                "date": e.date.isoformat(),
                "operation": e.operation,
                "title": e.title,
                "details": e.details,
            }
            for e in events
        ], indent=2))
        return 0

    if not events:
        print("No log entries match the filters.")
        return 0

    # Human-readable output.
    for e in events:
        print(f"[{e.date.isoformat()}] {e.operation:<12}  {e.title}")
        for key, value in e.details.items():
            print(f"    {key}: {value}")
    return 0


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


def cmd_quarantine(args: argparse.Namespace) -> int:
    """Inspect / clear the convert-error quarantine (G-14 · #300)."""
    from llmwiki import quarantine as q

    action = getattr(args, "action", None) or "list"

    if action == "list":
        entries = q.list_entries(adapter=args.adapter)
        print(q.format_table(entries))
        if entries and not args.adapter:
            counts = q.count_by_adapter()
            print()
            print(f"Total quarantined: {sum(counts.values())} across {len(counts)} adapter(s)")
        return 0

    if action == "clear":
        if args.all:
            removed = q.clear_all()
            print(f"Cleared {removed} quarantine entr{'y' if removed == 1 else 'ies'}.")
            return 0
        if not args.source:
            print("error: pass --all or a source path to clear", file=sys.stderr)
            return 2
        removed = q.clear_entry(args.source, adapter=args.adapter)
        print(f"Cleared {removed} quarantine entr{'y' if removed == 1 else 'ies'} for {args.source}")
        return 0

    if action == "retry":
        entries = q.list_entries(adapter=args.adapter)
        if not entries:
            print("No quarantined sources to retry.")
            return 0
        print(
            f"Retry plan — {len(entries)} source(s).  Clear the quarantine and re-run sync to retry:"
        )
        print()
        print(q.format_table(entries))
        print()
        print("Once your converter fix is in place:")
        print("  llmwiki quarantine clear --all")
        print("  llmwiki sync")
        return 0

    print(f"error: unknown quarantine action {action!r}", file=sys.stderr)
    return 2


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch agent session stores and auto-sync on change."""
    from llmwiki.watch import watch as run_watch
    return run_watch(
        adapters=args.adapter,
        interval=args.interval,
        debounce=args.debounce,
        dry_run=args.dry_run,
    )


def cmd_export_obsidian(args: argparse.Namespace) -> int:
    """Export the compiled wiki into an Obsidian vault."""
    from llmwiki.obsidian_output import export_to_vault
    return export_to_vault(
        vault=args.vault,
        subfolder=args.subfolder,
        dry_run=args.dry_run,
        clean=args.clean,
    )


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the structural eval battery over wiki/."""
    from llmwiki.eval import main as eval_main
    sub_argv: list[str] = []
    if args.check:
        sub_argv.extend(["--check"] + args.check)
    if args.json:
        sub_argv.append("--json")
    if args.out:
        sub_argv.extend(["--out", str(args.out)])
    if args.fail_below:
        sub_argv.extend(["--fail-below", str(args.fail_below)])
    return eval_main(sub_argv)


def cmd_export_marp(args: argparse.Namespace) -> int:
    """Export a Marp slide deck from wiki content matching a topic (v0.7 · #95)."""
    from llmwiki.export_marp import export_marp
    from llmwiki import REPO_ROOT

    wiki_dir = args.wiki or (REPO_ROOT / "wiki")
    out_path = args.out
    result = export_marp(topic=args.topic, wiki_dir=wiki_dir, out_path=out_path)
    if result:
        print(f"==> Marp deck written to {result}")
    else:
        print("  no matching pages found for the topic")
    return 0


def cmd_check_links(args: argparse.Namespace) -> int:
    """Verify every internal link in site/ resolves to an existing file."""
    from llmwiki.link_checker import main as link_main
    sub_argv: list[str] = []
    if args.site_dir:
        sub_argv.extend(["--site-dir", str(args.site_dir)])
    if args.fail_on_broken:
        sub_argv.append("--fail-on-broken")
    if args.limit:
        sub_argv.extend(["--limit", str(args.limit)])
    return link_main(sub_argv)


def cmd_export_qmd(args: argparse.Namespace) -> int:
    """Export the wiki as a self-contained qmd collection (v0.6 · #59)."""
    from llmwiki.export_qmd import export_qmd

    out_dir = args.out
    source_wiki = args.source_wiki or (REPO_ROOT / "wiki")
    summary = export_qmd(
        out_dir=out_dir,
        source_wiki=source_wiki,
        collection_name=args.collection,
    )
    print(
        f"==> qmd export complete: "
        f"{summary['files_copied']} files copied into {summary['out_dir']} "
        f"(collection: {summary['collection']})"
    )
    print(f"    next: cd {summary['out_dir']} && ./index.sh")
    return 0


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

    mapping = {
        "llms-txt": lambda: write_llms_txt(out_dir, groups, len(sources)),
        "llms-full-txt": lambda: write_llms_full_txt(out_dir, sources),
        "jsonld": lambda: write_graph_jsonld(out_dir, groups, sources),
        "sitemap": lambda: write_sitemap(out_dir, groups, sources),
        "rss": lambda: write_rss(out_dir, sources),
        "robots": lambda: write_robots_txt(out_dir),
        "ai-readme": lambda: write_ai_readme(out_dir, groups, len(sources)),
    }
    fn = mapping.get(format_)
    if not fn:
        print(f"error: unknown format {format_!r}. Valid: {sorted(mapping.keys())} or 'all'", file=_sys.stderr)
        return 2
    p = fn()
    print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    """Build a site/manifest.json with SHA-256 hashes + perf budget check."""
    from llmwiki.manifest import write_manifest
    site_dir = args.site_dir or (REPO_ROOT / "site")
    if not site_dir.exists():
        print(f"error: {site_dir} does not exist. Run 'llmwiki build' first.", file=sys.stderr)
        return 2
    p = write_manifest(site_dir)
    print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
    # Read back and show budget status
    import json as _json
    report = _json.loads(p.read_text(encoding="utf-8"))
    print(f"  {report['total_files']} files, {report['total_bytes'] / 1024 / 1024:.1f} MB")
    if report.get("budget_violations"):
        print("  ⚠ budget violations:")
        for v in report["budget_violations"]:
            print(f"    {v}")
        if args.fail_on_violations:
            return 1
    else:
        print("  ✓ all perf budget targets met")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Run all 11 lint rules against the wiki and print a report."""
    from llmwiki.lint import load_pages, run_all, summarize

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
        dry_run=args.dry_run,
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
    print(f"Synthesized (history): {report['synthesized']:>6} already in wiki/sources/")
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


def cmd_completion(args: argparse.Namespace) -> int:
    """Emit shell completion script for the requested shell (v1.1.0 · #216)."""
    from llmwiki.completion import generate
    try:
        script = generate(args.shell)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(script)
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    """Generate scheduled sync task files for the current platform (v1.0 · #162)."""
    import json as _json
    from llmwiki.scheduled_sync import (
        detect_platform,
        generate,
        install_instructions,
    )

    target_platform = args.platform or detect_platform()
    if target_platform == "unknown":
        print("error: could not detect platform. Pass --platform macos|linux|windows", file=sys.stderr)
        return 2

    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    config: dict = {}
    if config_path.is_file():
        try:
            config = _json.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    outputs = generate(target_platform, config)
    if not outputs:
        print(f"error: unsupported platform {target_platform!r}", file=sys.stderr)
        return 2

    out_dir = args.out or REPO_ROOT / "build" / "scheduled-sync"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")

    print()
    print(install_instructions(target_platform))
    return 0


def cmd_install_skills(args: argparse.Namespace) -> int:
    """Install llmwiki skills into multi-agent directories (v1.0 · #160)."""
    from llmwiki.skill_installer import install_all, list_installed

    count = install_all()
    print(f"  installed {count} skill/target combinations")
    print()
    print("Skills installed per target:")
    for target, skills in list_installed().items():
        p = Path(target)
        rel = p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p
        print(f"  {rel}/  ({len(skills)} skills)")
        for s in skills:
            print(f"    - {s}")
    return 0


def cmd_link_obsidian(args: argparse.Namespace) -> int:
    """Create a symlink from an Obsidian vault to the llm-wiki project root."""
    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        print(f"error: vault path does not exist: {vault}", file=sys.stderr)
        return 2

    link_path = vault / args.name
    target = REPO_ROOT

    if link_path.is_symlink():
        existing = link_path.resolve()
        if existing == target and not args.force:
            print(f"  ✓ symlink already exists: {link_path} → {target}")
            return 0
        if args.force:
            link_path.unlink()
            print(f"  removed existing symlink: {link_path}")
        else:
            print(
                f"error: {link_path} already exists (→ {existing}). "
                f"Use --force to overwrite.",
                file=sys.stderr,
            )
            return 1
    elif link_path.exists():
        print(
            f"error: {link_path} exists and is not a symlink. "
            f"Remove it manually first.",
            file=sys.stderr,
        )
        return 1

    link_path.symlink_to(target)
    print(f"  ✓ created symlink: {link_path} → {target}")
    print(f"  Obsidian will now show the llm-wiki project under '{args.name}/'")
    print(f"  wiki/ pages use [[wikilinks]] which Obsidian resolves natively.")
    return 0


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
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument(
        "--download-images", action="store_true",
        help="Download remote images in converted .md files to raw/assets/",
    )
    sync.add_argument(
        "--auto-build", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, auto-rebuild the static site if schedule allows (default: on)",
    )
    sync.add_argument(
        "--auto-lint", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, auto-run lint if schedule allows (default: on)",
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
    graph.set_defaults(func=cmd_graph)

    # quarantine (G-14 · #300)
    quar = sub.add_parser(
        "quarantine",
        help="Inspect / clear the convert-error quarantine",
    )
    quar_sub = quar.add_subparsers(dest="action")
    quar_list = quar_sub.add_parser("list", help="List quarantined sources")
    quar_list.add_argument("--adapter", help="Filter by adapter name")
    quar_clear = quar_sub.add_parser("clear", help="Clear quarantine entries")
    quar_clear.add_argument("source", nargs="?", help="Source path to clear")
    quar_clear.add_argument("--adapter", help="Restrict to one adapter")
    quar_clear.add_argument("--all", action="store_true", help="Clear every entry")
    quar_retry = quar_sub.add_parser("retry", help="Print retry plan")
    quar_retry.add_argument("--adapter", help="Filter by adapter name")
    quar.set_defaults(func=cmd_quarantine, action=None)

    # log (G-13 · #299)
    log_p = sub.add_parser(
        "log",
        help="Query wiki/log.md structurally (filter by operation / date)",
    )
    log_p.add_argument(
        "--since", type=str, default=None,
        help="Keep entries on or after YYYY-MM-DD",
    )
    log_p.add_argument(
        "--operation", type=str, default=None,
        help="Comma-separated operations to keep (sync,synthesize,lint,ingest,query,build)",
    )
    log_p.add_argument(
        "--limit", type=int, default=10,
        help="Max entries to show (default 10; 0 = unlimited)",
    )
    log_p.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (text for humans, json for scripts)",
    )
    log_p.set_defaults(func=cmd_log)

    # watch
    watch = sub.add_parser("watch", help="Watch agent session stores and auto-sync on change")
    watch.add_argument("--adapter", nargs="*", help="Adapter(s) to watch; default: all available")
    watch.add_argument("--interval", type=float, default=5.0, help="Polling interval seconds")
    watch.add_argument("--debounce", type=float, default=10.0, help="Debounce window seconds")
    watch.add_argument("--dry-run", action="store_true")
    watch.set_defaults(func=cmd_watch)

    # export-obsidian
    exp = sub.add_parser("export-obsidian", help="Export compiled wiki into an Obsidian vault")
    exp.add_argument("--vault", type=str, required=True, help="Path to the Obsidian vault root")
    exp.add_argument("--subfolder", type=str, default="LLM Wiki", help="Subfolder name inside the vault")
    exp.add_argument("--clean", action="store_true", help="Delete the target subfolder before copying")
    exp.add_argument("--dry-run", action="store_true")
    exp.set_defaults(func=cmd_export_obsidian)

    # export-marp (v0.7, #95) — Marp slide deck generation
    exp_marp = sub.add_parser(
        "export-marp",
        help="Generate a Marp slide deck from wiki content matching a topic",
    )
    exp_marp.add_argument(
        "--topic", type=str, required=True,
        help="Topic to search for in the wiki",
    )
    exp_marp.add_argument(
        "--out", type=Path, default=None,
        help="Output path (default: wiki/exports/<topic>.marp.md)",
    )
    exp_marp.add_argument(
        "--wiki", type=Path, default=None,
        help="Wiki directory (default: ./wiki)",
    )
    exp_marp.set_defaults(func=cmd_export_marp)

    # export-qmd (v0.6, #59) — emit a self-contained qmd collection so
    # the user can run tobi/qmd's hybrid-search stack over their wiki
    # without llmwiki shipping a TypeScript dep.
    exp_qmd = sub.add_parser(
        "export-qmd",
        help="Export the wiki as a self-contained qmd collection (tobi/qmd)",
    )
    exp_qmd.add_argument(
        "--out", type=Path, required=True,
        help="Output directory for the qmd collection",
    )
    exp_qmd.add_argument(
        "--source-wiki", type=Path, default=None,
        help="Source wiki directory (default: ./wiki)",
    )
    exp_qmd.add_argument(
        "--collection", type=str, default="llmwiki",
        help="Collection name written into qmd.yaml (default: llmwiki)",
    )
    exp_qmd.set_defaults(func=cmd_export_qmd)

    # eval
    ev = sub.add_parser("eval", help="Run structural eval checks over wiki/")
    ev.add_argument("--check", nargs="*", help="Run only these named checks")
    ev.add_argument("--json", action="store_true", help="Print JSON to stdout")
    ev.add_argument("--out", type=Path, default=None, help="Write JSON report to this path")
    ev.add_argument("--fail-below", type=int, default=0, help="Exit non-zero if score %% < this")
    ev.set_defaults(func=cmd_eval)

    # check-links (v0.4)
    cl = sub.add_parser("check-links", help="Verify every internal link in site/ resolves")
    cl.add_argument("--site-dir", type=Path, default=None)
    cl.add_argument("--fail-on-broken", action="store_true")
    cl.add_argument("--limit", type=int, default=20)
    cl.set_defaults(func=cmd_check_links)

    # export (v0.4)
    exp2 = sub.add_parser("export", help="Export AI-consumable formats (llms-txt, jsonld, sitemap, ...)")
    exp2.add_argument(
        "format",
        choices=["llms-txt", "llms-full-txt", "jsonld", "sitemap", "rss", "robots", "ai-readme", "all"],
        help="Export format",
    )
    exp2.add_argument("--out", type=Path, default=None, help="Output directory (default: site/)")
    exp2.set_defaults(func=cmd_export)

    # manifest (v0.4)
    mf = sub.add_parser("manifest", help="Build site/manifest.json with SHA-256 hashes + perf budget check")
    mf.add_argument("--site-dir", type=Path, default=None)
    mf.add_argument("--fail-on-violations", action="store_true")
    mf.set_defaults(func=cmd_manifest)

    # lint (v1.0, #155) — 11 lint rules
    lint = sub.add_parser(
        "lint",
        help="Run all 11 lint rules against the wiki (8 basic + 3 LLM-powered)",
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

    # install-skills (v1.0, #160) — multi-agent skill installer
    isk = sub.add_parser(
        "install-skills",
        help="Install llmwiki skills into .codex/skills/ and .agents/skills/ (multi-agent support)",
    )
    isk.set_defaults(func=cmd_install_skills)

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
        "--dry-run", action="store_true",
        help="List sessions that would be synthesized without writing",
    )
    syn.add_argument(
        "--force", action="store_true",
        help="Ignore state file, re-synthesize all sessions",
    )
    syn.add_argument(
        "--estimate", action="store_true",
        help="Print cached-vs-fresh token + dollar estimate without calling a backend (#50)",
    )
    syn.set_defaults(func=cmd_synthesize)

    # completion (v1.1, #216) — emit shell completion script
    comp = sub.add_parser(
        "completion",
        help="Emit shell completion script (bash/zsh/fish) — pipe to the shell's completion directory",
    )
    comp.add_argument(
        "shell", choices=["bash", "zsh", "fish"],
        help="Which shell to generate completion for",
    )
    comp.set_defaults(func=cmd_completion)

    # schedule (v1.0, #162) — generate scheduled sync task for the current OS
    sched = sub.add_parser(
        "schedule",
        help="Generate OS-specific scheduled sync task files (launchd/systemd/Task Scheduler)",
    )
    sched.add_argument(
        "--platform", choices=["macos", "linux", "windows"], default=None,
        help="Target platform (default: auto-detect).",
    )
    sched.add_argument(
        "--out", type=Path, default=None,
        help="Output directory (default: build/scheduled-sync/).",
    )
    sched.set_defaults(func=cmd_schedule)

    # link-obsidian (v1.0, Obsidian integration)
    lo = sub.add_parser(
        "link-obsidian",
        help="Symlink the llm-wiki project into an Obsidian vault for native viewing",
    )
    lo.add_argument(
        "--vault", type=str, required=True,
        help="Path to the Obsidian vault root (e.g. ~/Documents/Obsidian Vault)",
    )
    lo.add_argument(
        "--name", type=str, default="LLM Wiki",
        help="Name for the symlink inside the vault (default: 'LLM Wiki')",
    )
    lo.add_argument(
        "--force", action="store_true",
        help="Overwrite existing symlink if present",
    )
    lo.set_defaults(func=cmd_link_obsidian)

    # version
    ver = sub.add_parser("version", help="Print version")
    ver.set_defaults(func=cmd_version)

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
