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
    export-marp       Generate a Marp slide deck from wiki content
    adapters          List available session-store adapters
    version           Print version and exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

    # Seed index/log/overview if not present
    seeds = {
        "wiki/index.md": "# Wiki Index\n\n## Overview\n- [Overview](overview.md)\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n",
        "wiki/overview.md": '---\ntitle: "Overview"\ntype: synthesis\nsources: []\nlast_updated: ""\n---\n\n# Overview\n\n*This page is maintained by your coding agent.*\n',
        "wiki/log.md": "# Wiki Log\n\nAppend-only chronological record of all operations.\n\nFormat: `## [YYYY-MM-DD] <operation> | <title>`\n\n---\n",
    }
    for rel, content in seeds.items():
        p = REPO_ROOT / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            print(f"  seeded {p.relative_to(REPO_ROOT)}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Convert .jsonl sessions to markdown using the enabled adapters."""
    from llmwiki.convert import convert_all
    return convert_all(
        adapters=args.adapter,
        since=args.since,
        project=args.project,
        include_current=args.include_current,
        force=args.force,
        dry_run=args.dry_run,
    )


def cmd_build(args: argparse.Namespace) -> int:
    """Build the static HTML site."""
    from llmwiki.build import build_site
    return build_site(
        out_dir=args.out,
        synthesize=args.synthesize,
        claude_path=args.claude,
    )


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve the built site via a local HTTP server."""
    from llmwiki.serve import serve_site
    return serve_site(directory=args.dir, port=args.port, host=args.host, open_browser=args.open)


def cmd_adapters(args: argparse.Namespace) -> int:
    """List available adapters."""
    discover_adapters()
    if not REGISTRY:
        print("No adapters registered.")
        return 0
    print("Registered adapters:")
    for name, adapter_cls in sorted(REGISTRY.items()):
        present = "yes" if adapter_cls.is_available() else "no"
        print(f"  {name:<16}  available: {present}  ({adapter_cls.description()})")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Build the knowledge graph from wiki/ wikilinks."""
    from llmwiki.graph import build_and_report
    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(write_json_flag=write_json, write_html_flag=write_html)


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


def cmd_export_marp(args: argparse.Namespace) -> int:
    """Generate a Marp slide deck from wiki content (v0.7 · #95)."""
    from llmwiki.export_marp import export_marp

    wiki_dir = args.wiki or (REPO_ROOT / "wiki")
    out_path = args.out
    result = export_marp(
        topic=args.topic,
        wiki_dir=wiki_dir,
        out_path=out_path,
    )
    print(f"==> marp export complete: {result}")
    print("    render with: npx @marp-team/marp-cli " + str(result) + " --html")
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
    sync.set_defaults(func=cmd_sync)

    # build
    build = sub.add_parser("build", help="Compile static HTML site from raw/ + wiki/")
    build.add_argument("--out", type=Path, default=REPO_ROOT / "site", help="Output dir (default: site/)")
    build.add_argument("--synthesize", action="store_true", help="Call claude CLI for overview synthesis")
    build.add_argument("--claude", type=str, default="/usr/local/bin/claude", help="Path to claude CLI")
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
    ads.set_defaults(func=cmd_adapters)

    # graph
    graph = sub.add_parser("graph", help="Build the knowledge graph (graph/graph.json + graph.html)")
    graph.add_argument("--format", choices=["json", "html", "both"], default="both")
    graph.set_defaults(func=cmd_graph)

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

    # export-marp (v0.7, #95) — generate a Marp slide deck from wiki
    # content matching a topic. Stdlib-only, no Marp CLI dep.
    exp_marp = sub.add_parser(
        "export-marp",
        help="Generate a Marp slide deck from wiki content",
    )
    exp_marp.add_argument(
        "--topic", type=str, required=True,
        help="Topic to search for in the wiki (substring match)",
    )
    exp_marp.add_argument(
        "--out", type=Path, default=None,
        help="Output .marp.md file path (default: wiki/exports/<slug>.marp.md)",
    )
    exp_marp.add_argument(
        "--wiki", type=Path, default=None,
        help="Wiki directory (default: ./wiki)",
    )
    exp_marp.set_defaults(func=cmd_export_marp)

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
