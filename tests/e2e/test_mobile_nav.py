"""Binder for `features/mobile_nav.feature`."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/mobile_nav.feature")
