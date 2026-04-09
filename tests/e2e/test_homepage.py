"""Binder: turns every scenario in `features/homepage.feature` into
a pytest test. Step definitions live in `steps/ui_steps.py` — the
wildcard import registers every `@given` / `@when` / `@then` in this
module's namespace, which is where pytest-bdd 8.x looks for them."""

from pytest_bdd import scenarios

from tests.e2e.steps.ui_steps import *  # noqa: F401,F403

scenarios("features/homepage.feature")
