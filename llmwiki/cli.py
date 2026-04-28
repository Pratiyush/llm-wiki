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
# #v1378-review (#691 follow-up): hoist these re-exports from mid-module
# to here so the file passes E402 cleanly. They re-export business
# logic that lives in the proper domain modules now (#611) — kept here
# for any caller still importing from llmwiki.cli.
from llmwiki.adapters.status import adapter_status as _adapter_status  # noqa: F401
from llmwiki.synth.estimate import synthesize_estimate_report  # noqa: F401
# #691 / #arch-h8: extracted business logic moves out of cli.py.
# cli.py keeps thin re-export wrappers for back-compat with anyone
# doing `from llmwiki.cli import cmd_all, cmd_sync_status, ...`.
from llmwiki.config_schedule import (  # noqa: F401
    load_schedule_config as _load_schedule_config,
    should_run_after_sync as _should_run_after_sync,
)
from llmwiki.pipeline import run_pipeline as _run_pipeline
from llmwiki.sync.status import (  # noqa: F401
    cmd_sync_status,
    resolve_key_exists as _resolve_key_exists,
)
from llmwiki.synth.cli_helpers import (  # noqa: F401
    complete as _synthesize_complete,
    list_pending as _synthesize_list_pending,
)


def cmd_version(args: argparse.Namespace) -> int:
    print(f"llmwiki {__version__}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline end-to-end: build → graph → export all → lint.

    Thin shim — the implementation lives in ``llmwiki.pipeline`` (#691).
    """
    return _run_pipeline(args)


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

    from llmwiki.convert import convert_all, DEFAULT_OUT_DIR, DEFAULT_STATE_FILE

    # v1.2 (#54): vault-overlay mode — resolve the vault early so bad
    # paths fail before we spend time converting sessions.
    # #470: actually wire the resolved vault root through to convert_all.
    # Previously this block printed a banner and then called convert_all
    # with no vault/out_dir argument, so all 500+ sessions wrote to the
    # repo's raw/sessions/ instead of the vault. The summary line said
    # "507 converted" but the vault directory was empty.
    vault_path = getattr(args, "vault", None)
    out_dir = DEFAULT_OUT_DIR
    state_file = DEFAULT_STATE_FILE
    if vault_path:
        from llmwiki.vault import describe_vault, resolve_vault
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")
        if args.allow_overwrite:
            print("  --allow-overwrite: existing vault pages may be clobbered")
        # Route writes into the vault so a vault-mode sync actually
        # populates the vault. State file co-located with the vault so
        # two different vaults don't share idempotency state (same
        # principle as #420 for synth state).
        out_dir = vault.root / "raw" / "sessions"
        state_file = vault.root / ".llmwiki-state.json"

    rc = convert_all(
        adapters=args.adapter,
        out_dir=out_dir,
        state_file=state_file,
        since=args.since,
        project=args.project,
        include_current=args.include_current,
        force=args.force,
    )

    # v1.0 (#157): auto-build and auto-lint after sync.
    # --no-build and --no-lint let users opt out.
    # #470: when --vault was given, point the auto-build at the vault's
    # site/ tree too — otherwise the build silently writes to the
    # repo's site/ and the user's vault stays empty.
    if rc == 0:
        schedule = _load_schedule_config()
        site_root = (vault.root / "site") if vault_path else (REPO_ROOT / "site")
        if args.auto_build and _should_run_after_sync(schedule.get("build", "on-sync")):
            print("  auto-build: regenerating site/...")
            from llmwiki.build import build_site
            # #414: sync has explicit user opt-in to mutate wiki/, so it's
            # the right place to seed project stubs.
            build_site(out_dir=site_root, seed_project_stubs=True)
        if args.auto_lint and _should_run_after_sync(schedule.get("lint", "manual")):
            print("  auto-lint: running wiki lint...")
            from llmwiki.lint import load_pages, run_all, summarize
            # #470: lint the vault's wiki/, not the repo's, when in
            # vault-overlay mode.
            wiki_dir = (vault.root / "wiki") if vault_path else None
            pages = load_pages(wiki_dir) if wiki_dir else load_pages()
            issues = run_all(pages)
            summary = summarize(issues)
            print(f"  lint: {sum(summary.values())} issues "
                  f"({summary.get('error', 0)} errors, "
                  f"{summary.get('warning', 0)} warnings)")
    return rc


# _load_schedule_config + _should_run_after_sync moved to
# llmwiki/config_schedule.py and re-exported at top of file (#691).


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
    """Build the knowledge graph from wiki/ wikilinks.

    #488: graphify-engine failures (uninstalled, crashes, empty
    result) ALL fall back to the builtin engine so the user always
    gets *some* graph. Only the builtin engine's exit code is
    authoritative for the CLI return value.
    """
    engine = getattr(args, "engine", "graphify")
    if engine == "graphify":
        from llmwiki.graphify_bridge import is_available, build_graphify_graph
        if not is_available():
            print("  graphify not installed — falling back to builtin engine", file=sys.stderr)
            print("  install with: pip install llmwiki[graph]", file=sys.stderr)
            engine = "builtin"
        else:
            try:
                result = build_graphify_graph()
            except Exception as e:
                # #488: uncaught graphify exception used to surface as a
                # bare stack trace + non-zero exit. Now we log a warning
                # and fall through to the builtin engine.
                print(f"  graphify engine crashed ({type(e).__name__}: {e}) — "
                      f"falling back to builtin", file=sys.stderr)
                engine = "builtin"
            else:
                if result.get("graph") is not None:
                    return 0
                # #488: empty-result early-return used to fail with rc=1
                # without trying builtin. graphify can legitimately
                # return None for tiny corpora (no edges); the builtin
                # engine handles the same input gracefully.
                print("  graphify returned no graph — falling back to builtin",
                      file=sys.stderr)
                engine = "builtin"

    from llmwiki.graph import build_and_report
    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(write_json_flag=write_json, write_html_flag=write_html)


# cmd_sync_status + _resolve_key_exists moved to llmwiki/sync/status.py
# and re-exported at top of file (#691).


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

    # #420: vault-overlay mode isolates raw/wiki/state to the vault root.
    vault_path = getattr(args, "vault", None)
    raw_dir = wiki_sources_dir = state_file = None
    if vault_path:
        from llmwiki.vault import resolve_vault
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        # Post-final-review: Vault is a frozen dataclass with no
        # __truediv__ — `vault / "raw"` raises TypeError. cmd_sync at
        # line 205 correctly uses `vault.root / "raw"`; this site was
        # the missed copy. Caught by the multi-agent code review.
        raw_dir = vault.root / "raw" / "sessions"
        wiki_sources_dir = vault.root / "wiki" / "sources"
        state_file = vault.root / ".llmwiki-synth-state.json"

    summary = synthesize_new_sessions(
        backend=backend,
        force=args.force,
        raw_dir=raw_dir,
        wiki_sources_dir=wiki_sources_dir,
        state_file=state_file,
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
# _synthesize_list_pending + _synthesize_complete moved to
# llmwiki/synth/cli_helpers.py and re-exported at top of file (#691).


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


def _add_vault_arg(parser: argparse.ArgumentParser, *, role: str) -> None:
    """#arch-m8 (#620): single source of truth for the ``--vault`` flag.

    All three subcommands that accept ``--vault`` (sync, build, synthesize)
    used to declare it independently with subtly different help text and
    behaviour. The semantics differ legitimately by subcommand (sync
    WRITES into the vault; build READS from it; synthesize isolates the
    state file under it), so we keep the role-specific help string per
    site, but the flag spelling, type, default, and metavar are unified
    here so a future refactor changes them in one place.
    """
    parser.add_argument(
        "--vault", type=Path, default=None, metavar="PATH",
        help={
            "sync": "Vault-overlay mode (#54): write new pages inside an "
                    "existing Obsidian / Logseq vault instead of the "
                    "repo's wiki/ directory.",
            "build": "Vault-overlay mode (#54): build from an existing "
                     "Obsidian / Logseq vault. Still writes site output to "
                     "--out.",
            "synthesize": "(#420) Vault-overlay mode: read raw/ + write "
                          "wiki/sources/ under the vault root, and isolate "
                          "the synth state file to the vault. Without this "
                          "flag the state file lives at the repo root, so "
                          "two vaults synthesised against the same repo "
                          "silently share idempotency state.",
        }[role],
    )


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
    _add_vault_arg(sync, role="sync")
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
    build.add_argument(
        "--claude", type=str, default="",
        help="Path to claude CLI (#421: defaults to `shutil.which('claude')` "
             "so PATH-based / brew / nvm / Windows installs all work)",
    )
    build.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode (#53): auto picks tree vs flat from heading depth",
    )
    _add_vault_arg(build, role="build")
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
    # #arch-h7 (#610): the four "what should this invocation do?" flags
    # used to be independently set-able. argparse silently honoured the
    # first one in `cmd_synthesize`'s if/elif chain, so e.g.
    # `synthesize --check --estimate` ran --check and silently dropped
    # --estimate. Use a mutually-exclusive group so the parser rejects
    # the combination loudly with a useful error.
    syn_mode = syn.add_mutually_exclusive_group()
    syn_mode.add_argument(
        "--check", action="store_true",
        help="Probe backend availability and exit (exit 0 if reachable)",
    )
    syn_mode.add_argument(
        "--estimate", action="store_true",
        help="Print cached-vs-fresh token + dollar estimate without calling a backend (#50)",
    )
    # #316 — agent-delegate backend helpers (mutually-exclusive with the
    # default synthesize-all flow + with --check / --estimate above).
    syn_mode.add_argument(
        "--list-pending", action="store_true",
        help="List pending prompts awaiting agent synthesis (agent-delegate backend, #316)",
    )
    syn_mode.add_argument(
        "--complete", metavar="UUID", default=None,
        help="Complete a pending synthesis: read body from --body or stdin, rewrite --page in place (#316)",
    )
    # --force is orthogonal (modifies the default re-synthesize-all flow)
    # and stays outside the exclusion group so callers can pass
    # `synthesize --force` for a forced full re-run.
    syn.add_argument(
        "--force", action="store_true",
        help="Ignore state file, re-synthesize all sessions",
    )
    syn.add_argument(
        "--page", metavar="PATH", default=None,
        help="Target wiki source page for --complete (path relative to repo root or absolute)",
    )
    syn.add_argument(
        "--body", metavar="PATH", default=None,
        help="Read synthesized body from this file for --complete (default: stdin)",
    )
    _add_vault_arg(syn, role="synthesize")
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
