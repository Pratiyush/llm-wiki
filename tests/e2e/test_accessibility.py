"""Binder for `features/accessibility.feature` — a11y + keyboard-only flows."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/accessibility.feature")
