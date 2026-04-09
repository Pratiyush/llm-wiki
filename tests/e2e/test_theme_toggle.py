"""Binder for `features/theme_toggle.feature`."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/theme_toggle.feature")
