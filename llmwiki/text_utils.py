"""Shared text utilities for frontmatter parsing and wikilink handling.

Centralises BOM-stripping (so both lint and web code use the same logic)
and wikilink paren normalisation (half-width → fullwidth for Chinese docs).
"""

from __future__ import annotations

import re

BOM = "﻿"

# Match [[Foo(Bar)]] or [[Foo（Bar）]] — wikilinks with parenthesised disambiguation
WIKILINK_PAREN_RE = re.compile(r"\[\[([^\]|]+?)([\(（])([^\)）]*)([\)）])\]\]")


def strip_bom(text: str) -> str:
    """Remove UTF-8 BOM if present."""
    if text.startswith(BOM):
        return text[1:]
    return text


def normalize_wikilink_parens(text: str) -> tuple[str, list[str]]:
    """Replace half-width parens with fullwidth in wikilinks targeting Chinese-named pages.

    Returns (normalized_text, list_of_warnings).
    """
    warnings: list[str] = []

    def _replacer(m: re.Match) -> str:
        target = m.group(1)
        left = m.group(2)
        inner = m.group(3)
        right = m.group(4)

        # Only flag half-width parens
        if left == "(" and right == ")":
            # Check if the target looks Chinese (contains CJK chars)
            if re.search(r"[一-鿿]", target + inner):
                fixed = f"[[{target}（{inner}）]]"
                warnings.append(
                    f"wikilink uses half-width parens: [[{target}({inner})]] "
                    f"→ should be [[{target}（{inner}）]]"
                )
                return fixed
            return m.group(0)

        # Already fullwidth — keep as-is
        return m.group(0)

    result = WIKILINK_PAREN_RE.sub(_replacer, text)
    return result, warnings
