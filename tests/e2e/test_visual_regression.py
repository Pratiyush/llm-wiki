"""Binder for `features/visual_regression.feature` — screenshots
captured per breakpoint × theme combo. Output goes to
``tests/e2e/screenshots/`` (gitignored so CI artifacts aren't committed).
"""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/visual_regression.feature")
