"""Notebook listing API."""

from __future__ import annotations

from fastapi import APIRouter

from llmwiki.notebooks import (
    DEFAULT_NOTEBOOK_SLUG,
    DEFAULT_NOTEBOOK_TITLE,
    NOTEBOOK_DESCRIPTION,
)

router = APIRouter()


@router.get("")
async def api_notebooks():
    return {
        "notebooks": [
            {
                "slug": DEFAULT_NOTEBOOK_SLUG,
                "title": DEFAULT_NOTEBOOK_TITLE,
                "description": NOTEBOOK_DESCRIPTION,
                "is_default": True,
                "visibility": "public",
            }
        ]
    }
