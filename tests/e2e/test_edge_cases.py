"""Binder for `features/edge_cases.feature` — the weird-content scenarios."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/edge_cases.feature")
