"""Shell completion generators (v1.1.0 · #216).

Emit hand-rolled completion scripts for bash, zsh, and fish. Stdlib
only — no argcomplete dep. Each generator enumerates the argparse
subparsers at runtime and builds a shell function that completes
subcommand names + their top-level flags.

Not perfect (doesn't complete values for --out paths, etc.) but
covers the 80% case of "which subcommand?" and "what flags?".

Usage::

    llmwiki completion bash  > ~/.bash_completion.d/llmwiki
    llmwiki completion zsh   > ~/.zsh/completions/_llmwiki
    llmwiki completion fish  > ~/.config/fish/completions/llmwiki.fish
"""

from __future__ import annotations

from argparse import ArgumentParser
from typing import Any


def _collect(parser: ArgumentParser) -> tuple[list[str], dict[str, list[str]]]:
    """Walk the argparse tree → (subcommand_list, {sub: [flags]})."""
    subcommands: list[str] = []
    flags_by_sub: dict[str, list[str]] = {}
    top_flags: list[str] = []

    # Top-level flags (like --version, --help)
    for action in parser._actions:
        for opt in action.option_strings:
            if opt.startswith("--"):
                top_flags.append(opt)
    flags_by_sub[""] = sorted(set(top_flags))

    # Subparsers
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            for name, sub_parser in action.choices.items():
                subcommands.append(name)
                sub_flags: list[str] = []
                for a in sub_parser._actions:
                    for opt in a.option_strings:
                        if opt.startswith("--"):
                            sub_flags.append(opt)
                flags_by_sub[name] = sorted(set(sub_flags))

    return sorted(subcommands), flags_by_sub


def _get_parser() -> ArgumentParser:
    """Lazy import to avoid circular deps during completion generation."""
    from llmwiki.cli import build_parser
    return build_parser()


# ─── bash ─────────────────────────────────────────────────────────────

def bash_script() -> str:
    """Generate a bash completion script."""
    subs, flags = _collect(_get_parser())
    subs_str = " ".join(subs)

    # Per-subcommand flag cases
    case_lines = []
    for sub in subs:
        sub_flags = " ".join(flags.get(sub, []))
        if sub_flags:
            case_lines.append(f"    {sub}) COMPREPLY=($(compgen -W \"{sub_flags}\" -- \"$cur\")) ;;")

    case_block = "\n".join(case_lines) if case_lines else "    *) ;;"

    return f"""# bash completion for llmwiki — source this file or drop it into
# /usr/local/etc/bash_completion.d/llmwiki (Homebrew) or
# /etc/bash_completion.d/llmwiki (Linux).

_llmwiki() {{
  local cur prev cword
  _init_completion -s || return

  if [ "$cword" -eq 1 ]; then
    COMPREPLY=($(compgen -W "{subs_str}" -- "$cur"))
    return 0
  fi

  case "${{COMP_WORDS[1]}}" in
{case_block}
  esac
  return 0
}}

complete -F _llmwiki llmwiki
"""


# ─── zsh ─────────────────────────────────────────────────────────────

def zsh_script() -> str:
    """Generate a zsh completion function. File should be named _llmwiki."""
    subs, flags = _collect(_get_parser())

    # Per-sub case for flag completion
    case_lines = []
    for sub in subs:
        sub_flags = flags.get(sub, [])
        flag_list = " ".join(f"'{f}[--{f.lstrip('-')}]'" for f in sub_flags)
        if flag_list:
            case_lines.append(f"    {sub}) _arguments {flag_list} ;;")

    case_block = "\n".join(case_lines) if case_lines else "    *) ;;"

    sub_descriptions = "\n".join(f"    '{s}:{s}'" for s in subs)

    return f"""#compdef llmwiki
# zsh completion for llmwiki — drop into ~/.zsh/completions/_llmwiki
# and ensure fpath contains ~/.zsh/completions.

_llmwiki() {{
  local state
  local -a subcommands

  _arguments -C \\
    '1: :->subcmd' \\
    '*::arg:->args'

  case "$state" in
    subcmd)
      subcommands=(
{sub_descriptions}
      )
      _describe 'subcommand' subcommands
      ;;
    args)
      case "$words[1]" in
{case_block}
      esac
      ;;
  esac
}}

_llmwiki "$@"
"""


# ─── fish ────────────────────────────────────────────────────────────

def fish_script() -> str:
    """Generate a fish completion script."""
    subs, flags = _collect(_get_parser())

    lines = [
        "# fish completion for llmwiki — drop into ~/.config/fish/completions/llmwiki.fish",
        "",
        "# subcommands",
    ]
    for sub in subs:
        lines.append(
            f"complete -c llmwiki -n '__fish_use_subcommand' "
            f"-a '{sub}' -d '{sub}'"
        )
    lines.append("")
    lines.append("# per-subcommand flags")
    for sub in subs:
        for flag in flags.get(sub, []):
            # fish wants long-option without leading --
            opt = flag.lstrip("-")
            lines.append(
                f"complete -c llmwiki -n '__fish_seen_subcommand_from {sub}' "
                f"-l {opt} -d '{flag} option'"
            )

    return "\n".join(lines) + "\n"


# ─── dispatch ────────────────────────────────────────────────────────

GENERATORS = {
    "bash": bash_script,
    "zsh": zsh_script,
    "fish": fish_script,
}


def generate(shell: str) -> str:
    """Dispatch by shell name. Raises ValueError for unknown shells."""
    if shell not in GENERATORS:
        raise ValueError(
            f"unknown shell {shell!r}; supported: {sorted(GENERATORS)}"
        )
    return GENERATORS[shell]()
