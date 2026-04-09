"""Binder for `features/command_palette.feature`."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/command_palette.feature")
