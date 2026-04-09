"""Binder for `features/responsive.feature` — 4 breakpoints × 9 widths."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/responsive.feature")
